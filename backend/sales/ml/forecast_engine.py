
"""Operational forecast engine for daily, hourly and menu-level series."""

from decimal import Decimal, ROUND_HALF_UP

import numpy as np
import pandas as pd

from django.db import transaction
from django.utils import timezone

from sales.models import ForecastRun, ForecastValue
from store.models import Menu, Store
from weatherdata.models import WeatherLocation

from sales.ml.dataset import build_daily_frame, weather_for_targets
from sales.ml.boundary import clamp_as_of, default_as_of
from sales.ml.daily_models import (
    MODEL_VERSION,
    TARGETS,
    rolling_cv,
    summarize_cv,
    select_model,
    fit_predict,
    feature_columns,
    interval_ratios,
    MIN_TRAIN_DAYS,
    NO_TEMP_FALLBACK,
    TEMP_COL,
)


HORIZON_DAYS = 7
OPENING_HOUR = 8
CLOSING_HOUR = 21

# Daily operational candidates without weather.
OPERATIONAL_CANDIDATES = (
    "weekday_index",
    "weekday_mean_8w",
    "glm_cal",
    "glm_schools",
    "hgb_cal",
    "prophet_cal",
)

# Weather-aware daily candidates.
DAILY_WEATHER_CANDIDATES = (
    "glm_cal_temp",
    "glm_schools_temp",
    "prophet_cal_temp",
)

HOURLY_MODEL = "glm_cal"
HOURLY_TARGETS = ("sales", "orders")
MENU_MODEL = "weekday_index"
WEATHER_MENU_MODEL = "glm_cal_temp"

MAX_DECIMAL_VALUE = Decimal("9999999999999999.99")


def _decimal(value):
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise ValueError(
            f"Invalid forecast numeric value: {value!r}"
        ) from exc

    if not result.is_finite():
        raise ValueError(
            f"Forecast value must be finite: {value!r}"
        )

    result = max(result, Decimal("0")).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

    if result > MAX_DECIMAL_VALUE:
        raise ValueError(
            f"Forecast value exceeds database DecimalField range: {value!r}"
        )

    return result


def _future_dates(as_of):
    return pd.date_range(
        start=pd.Timestamp(as_of) + pd.Timedelta(days=1),
        periods=HORIZON_DAYS,
        freq="D",
    )


def _calendar_test(cal, targets):
    future = cal.reindex(pd.DatetimeIndex(targets)).copy()

    if future.empty:
        raise ValueError(
            "No calendar data is available for forecast dates."
        )

    if future.isna().all(axis=1).any():
        missing = future.index[
            future.isna().all(axis=1)
        ].strftime("%Y-%m-%d").tolist()

        raise ValueError(
            f"Calendar features are missing for forecast dates: {missing}"
        )

    return future


def _json_number(value):
    if value is None:
        return None

    if isinstance(value, np.generic):
        value = value.item()

    if pd.isna(value):
        return None

    if isinstance(value, (int, float, str, bool)):
        return value

    return value


def _evaluate_and_predict(
    frame,
    target_col,
    targets,
    future_features,
    fixed_model=None,
    candidate_models=None,
):
    """Evaluate models with expanding-window CV, then refit for future dates."""
    frame = frame.sort_index().copy()
    frame = frame[~frame.index.duplicated(keep="last")]

    if frame.empty:
        raise ValueError("Training data is empty.")

    if len(frame) < MIN_TRAIN_DAYS:
        raise ValueError(
            f"Insufficient training history: {len(frame)} days; "
            f"at least {MIN_TRAIN_DAYS} days are required."
        )

    if target_col not in frame.columns:
        raise ValueError(
            f"Training target column is missing: {target_col}"
        )

    frame[target_col] = (
        pd.to_numeric(frame[target_col], errors="coerce")
        .fillna(0)
        .clip(lower=0)
    )

    targets = pd.DatetimeIndex(targets)

    if targets.empty:
        raise ValueError("Forecast target dates are empty.")

    if frame.index.max() >= targets.min():
        raise ValueError(
            "Temporal leakage detected: training data overlaps "
            "the forecast period."
        )

    if candidate_models is not None:
        candidates = tuple(candidate_models)
    elif fixed_model is not None:
        candidates = (fixed_model,)
    else:
        candidates = OPERATIONAL_CANDIDATES

    if not candidates:
        raise ValueError("No candidate models were specified.")

    if fixed_model is not None and fixed_model not in candidates:
        raise ValueError(
            f"Fixed model {fixed_model} is not in the candidate list."
        )

    cv = rolling_cv(frame, target_col, list(candidates))

    if cv.empty:
        raise ValueError(
            "Rolling cross-validation returned no results."
        )

    overall, _, _ = summarize_cv(cv)

    if overall.empty:
        raise ValueError(
            "Model evaluation returned no summary."
        )

    selected = (
        select_model(overall)
        if fixed_model is None
        else fixed_model
    )
    selection_reason = "standard_cv_selection"

    # Total sales is the primary business forecast. When a weather-aware
    # candidate demonstrates a measurable WAPE improvement over the best
    # calendar-only candidate on the same paired validation dates, use it.
    # Orders and quantity continue to use the general model-selection rule.
    if fixed_model is None and target_col == "sales":
        eligible = overall[
            (overall["fallback_rows"] == 0)
            & overall["wape_pct"].notna()
        ].copy()
        weather_rows = eligible[
            eligible["model"].astype(str).str.endswith("_temp")
        ]
        calendar_rows = eligible[
            ~eligible["model"].astype(str).str.endswith("_temp")
        ]
        if not weather_rows.empty and not calendar_rows.empty:
            best_weather = weather_rows.sort_values("wape_pct").iloc[0]
            best_calendar = calendar_rows.sort_values("wape_pct").iloc[0]
            improvement_pp = float(best_calendar["wape_pct"] - best_weather["wape_pct"])
            if improvement_pp >= 0.05:
                selected = str(best_weather["model"])
                selection_reason = (
                    "weather_model_selected_for_sales: paired_cv_wape_improved_"
                    f"{improvement_pp:.4f}_pp"
                )

    if not selected:
        raise ValueError(
            "No forecast model could be selected."
        )

    selected_rows = overall[
        overall.model == selected
    ]

    if selected_rows.empty:
        raise ValueError(
            f"No validation result exists for selected model: {selected}"
        )

    selected_metrics = selected_rows.iloc[0].to_dict()

    if int(selected_metrics["fallback_rows"]) > 0:
        raise ValueError(
            f"Model {selected} required fallback during validation "
            "and cannot be used as the operational model."
        )

    test = pd.DataFrame(
        index=targets,
        columns=frame.columns,
    )

    for column in frame.columns:
        test[column] = 0.0

    future_features = future_features.reindex(targets)

    for column in future_features.columns:
        if column in test.columns:
            test[column] = future_features[column]

    test[target_col] = 0.0

    required = feature_columns(selected)
    missing_columns = [
        column for column in required if column not in test.columns
    ]
    if missing_columns:
        raise ValueError(
            f"Required future features are missing: {missing_columns}"
        )

    prediction = np.zeros(len(targets), dtype=float)
    intervals = [(None, None) for _ in targets]
    forecast_models = [selected] * len(targets)
    weather_fallback_dates = []

    missing_weather_mask = (
        test[TEMP_COL].isna().to_numpy()
        if selected in NO_TEMP_FALLBACK and TEMP_COL in required
        else np.zeros(len(targets), dtype=bool)
    )

    if missing_weather_mask.any():
        # Use the weather model only where KMA supplied a valid temperature.
        # For missing forecast temperatures, use its calendar-only counterpart.
        weather_mask = ~missing_weather_mask
        fallback_model = NO_TEMP_FALLBACK[selected]

        if weather_mask.any():
            weather_test = test.iloc[np.flatnonzero(weather_mask)]
            weather_prediction = np.asarray(
                fit_predict(selected, frame, weather_test, target_col),
                dtype=float,
            )
            prediction[weather_mask] = weather_prediction
            weather_ratios = interval_ratios(cv, selected)
            for idx, value in zip(np.flatnonzero(weather_mask), weather_prediction):
                if weather_ratios:
                    intervals[idx] = (
                        max(0.0, value * weather_ratios["low_ratio"]),
                        max(value, value * weather_ratios["high_ratio"]),
                    )

        fallback_mask = missing_weather_mask
        fallback_test = test.iloc[np.flatnonzero(fallback_mask)]
        fallback_prediction = np.asarray(
            fit_predict(fallback_model, frame, fallback_test, target_col),
            dtype=float,
        )
        prediction[fallback_mask] = fallback_prediction
        fallback_models = [fallback_model] * int(fallback_mask.sum())
        fallback_ratios = interval_ratios(cv, fallback_model)
        for idx, value in zip(np.flatnonzero(fallback_mask), fallback_prediction):
            if fallback_ratios:
                intervals[idx] = (
                    max(0.0, value * fallback_ratios["low_ratio"]),
                    max(value, value * fallback_ratios["high_ratio"]),
                )
        for idx in np.flatnonzero(fallback_mask):
            forecast_models[idx] = fallback_model
            weather_fallback_dates.append(pd.Timestamp(targets[idx]).strftime("%Y-%m-%d"))
    else:
        prediction = np.asarray(
            fit_predict(selected, frame, test, target_col),
            dtype=float,
        )
        ratios = interval_ratios(cv, selected)
        for idx, value in enumerate(prediction):
            if ratios:
                intervals[idx] = (
                    max(0.0, value * ratios["low_ratio"]),
                    max(value, value * ratios["high_ratio"]),
                )

    if len(prediction) != len(targets):
        raise ValueError("Prediction count does not match forecast date count.")
    if not np.isfinite(prediction).all():
        raise ValueError("Prediction contains invalid numeric values.")
    prediction = np.clip(prediction, 0, None)

    metrics = {
        key: _json_number(value)
        for key, value in selected_metrics.items()
        if key != "model"
    }

    return {
        "model": selected,
        "prediction": prediction,
        "intervals": intervals,
        "metrics": {
            "selected_model": selected,
            "cv": metrics,
            "interval_ratios": interval_ratios(cv, selected),
            "cv_rows": int(len(cv)),
            "selection_reason": selection_reason,
            "candidate_comparison": [
                {
                    key: _json_number(value)
                    for key, value in row.items()
                }
                for row in overall.to_dict(orient="records")
            ],
            "forecast_models_by_date": {
                pd.Timestamp(day).strftime("%Y-%m-%d"): model
                for day, model in zip(targets, forecast_models)
            },
            "weather_fallback_dates": weather_fallback_dates,
        },
    }


def _get_forecast_temperatures(store_id, dates, weather_obs):
    """
    Get KMA short/mid-term temperatures only.
    Climatology and missing values are deliberately excluded.
    """
    location = WeatherLocation.objects.filter(
        store_id=store_id
    ).first()

    if location is None:
        return {}, {
            "status": "unavailable",
            "reason": "weather_location_not_registered",
            "forecast_dates": [],
        }

    forecast_data = weather_for_targets(
        location=location,
        targets=dates,
        issued_at=timezone.now(),
        weather_obs=weather_obs,
    )

    temperatures = {}
    bases = {}

    for target_date, item in forecast_data.items():
        basis = item.get("basis")

        if basis not in {"short_forecast", "mid_forecast"}:
            continue

        value = item.get("temp_avg")

        if value is None:
            continue

        value = float(value)

        if not np.isfinite(value):
            continue

        day = pd.Timestamp(target_date).normalize()
        temperatures[day] = value
        bases[day] = basis

    return temperatures, {
        "status": "available" if temperatures else "unavailable",
        "forecast_dates": [
            day.strftime("%Y-%m-%d")
            for day in sorted(temperatures)
        ],
        "short_forecast_days": sum(
            basis == "short_forecast"
            for basis in bases.values()
        ),
        "mid_forecast_days": sum(
            basis == "mid_forecast"
            for basis in bases.values()
        ),
    }


def _save_values(
    rows,
    series_key,
    granularity,
    metric,
    dates,
    result,
    target_hour=None,
    menu=None,
    serving_temperature=None,
):
    """Build ForecastValue objects in memory; does not write to the database."""
    predictions = result["prediction"]
    intervals = result["intervals"]

    if len(predictions) != len(dates) or len(intervals) != len(dates):
        raise ValueError(
            f"{series_key}: prediction count does not match date count."
        )

    for index, target_date in enumerate(dates):
        low, high = intervals[index]

        predicted = _decimal(predictions[index])
        lower = _decimal(low) if low is not None else None
        upper = _decimal(high) if high is not None else None

        if (lower is None) != (upper is None):
            raise ValueError(
                f"{series_key}: incomplete prediction interval."
            )

        if lower is not None:
            if lower > upper:
                raise ValueError(
                    f"{series_key}: lower bound exceeds upper bound."
                )

            if not lower <= predicted <= upper:
                raise ValueError(
                    f"{series_key}: prediction is outside its interval."
                )

        rows.append(ForecastValue(
            series_key=series_key,
            granularity=granularity,
            metric=metric,
            target_date=pd.Timestamp(target_date).date(),
            target_hour=target_hour,
            menu=menu,
            serving_temperature=serving_temperature,
            predicted_value=predicted,
            lower_bound=lower,
            upper_bound=upper,
        ))

    return len(dates)


def _daily_forecasts(
    daily,
    cal,
    dates,
    forecast_rows,
    forecast_temperatures=None,
):
    """
    Evaluate calendar-only and weather-aware models for daily forecasts.

    Historical temperature comes from observed ASOS data already joined
    into the daily training frame.

    Future temperature comes only from KMA short/mid-term forecasts.
    Weather candidates are evaluated on paired historical dates with observed
    temperature. KMA temperatures are applied date-by-date; dates without a
    valid KMA temperature use the selected model's calendar-only counterpart.
    """
    results = {}
    future = _calendar_test(cal, dates)

    forecast_temperatures = forecast_temperatures or {}
    target_dates = pd.DatetimeIndex(dates).normalize()

    normalized_temperatures = {}

    for day, value in forecast_temperatures.items():
        if value is None:
            continue

        try:
            temperature = float(value)
        except (TypeError, ValueError):
            continue

        if np.isfinite(temperature):
            normalized_temperatures[
                pd.Timestamp(day).normalize()
            ] = temperature

    has_any_weather = (
        "temp_avg" in daily.columns
        and any(day in normalized_temperatures for day in target_dates)
    )

    candidates = list(OPERATIONAL_CANDIDATES)

    if has_any_weather:
        future["temp_avg"] = [
            normalized_temperatures.get(day, np.nan)
            for day in target_dates
        ]
        candidates.extend(DAILY_WEATHER_CANDIDATES)

    for target in TARGETS:
        result = _evaluate_and_predict(
            daily,
            target,
            dates,
            future,
            candidate_models=candidates,
        )

        _save_values(
            forecast_rows,
            f"daily:{target}",
            "DAILY",
            target.upper(),
            dates,
            result,
        )

        results[target] = result["metrics"]

    return results


def _hourly_confidence(wape_pct):
    if wape_pct is None or pd.isna(wape_pct):
        return "unavailable"

    if wape_pct <= 40:
        return "medium"

    if wape_pct <= 60:
        return "low"

    return "very_low"


def _hourly_forecasts(hourly, cal, dates, forecast_rows):
    """Generate independent hourly sales and order forecasts."""
    required = {"date", "hour", "sales", "orders"}
    missing = required - set(hourly.columns)

    if missing:
        raise ValueError(
            f"Hourly data columns are missing: {sorted(missing)}"
        )

    data = hourly.copy()
    data["date"] = pd.to_datetime(
        data["date"],
        errors="coerce",
    ).dt.normalize()

    data["hour"] = pd.to_numeric(
        data["hour"],
        errors="coerce",
    )

    if data[["date", "hour"]].isna().any().any():
        raise ValueError(
            "Hourly data contains missing dates or hours."
        )

    if not np.equal(
        data["hour"],
        np.floor(data["hour"]),
    ).all():
        raise ValueError(
            "Hourly data contains non-integer hour values."
        )

    data["hour"] = data["hour"].astype(int)

    if data.duplicated(["date", "hour"]).any():
        raise ValueError(
            "Duplicate date/hour rows exist in hourly data."
        )

    hours = list(range(OPENING_HOUR, CLOSING_HOUR + 1))

    unexpected = sorted(
        set(data["hour"].unique()) - set(hours)
    )

    if unexpected:
        raise ValueError(
            f"Unexpected operating hours found: {unexpected}"
        )

    expected_dates = pd.DatetimeIndex(
        sorted(data["date"].unique())
    )

    if expected_dates.empty:
        raise ValueError(
            "Hourly training dates are empty."
        )

    calendar_history = cal.reindex(expected_dates)

    if calendar_history.isna().all(axis=1).any():
        raise ValueError(
            "Calendar features are missing for some hourly training dates."
        )

    future = _calendar_test(cal, dates)
    results = {}

    for hour in hours:
        hour_data = data[data["hour"] == hour].copy()

        if hour_data.empty:
            raise ValueError(
                f"No training data exists for hour {hour}."
            )

        frame = (
            hour_data.set_index("date")[["sales", "orders"]]
            .sort_index()
            .join(calendar_history, how="left")
        )

        if not frame.index.equals(expected_dates):
            raise ValueError(
                f"Hour {hour}: training dates do not match "
                "the complete historical date index."
            )

        if frame.index.has_duplicates:
            raise ValueError(
                f"Hour {hour}: duplicate training dates exist."
            )

        if frame[["sales", "orders"]].isna().any().any():
            raise ValueError(
                f"Hour {hour}: sales or orders contain missing values."
            )

        for target in HOURLY_TARGETS:
            result = _evaluate_and_predict(
                frame,
                target,
                dates,
                future,
                fixed_model=HOURLY_MODEL,
                candidate_models=(HOURLY_MODEL,),
            )

            _save_values(
                forecast_rows,
                f"hourly:{target}:{hour:02d}",
                "HOURLY",
                target.upper(),
                dates,
                result,
                target_hour=hour,
            )

            cv = result["metrics"]["cv"]

            results[f"{target}:{hour:02d}"] = {
                **result["metrics"],
                "confidence": _hourly_confidence(
                    cv.get("wape_pct")
                ),
            }

    return results


def _menu_forecasts(
    menu_data,
    cal,
    dates,
    store_id,
    forecast_rows,
    weather_obs=None,
    forecast_temperatures=None,
):
    """
    Keep weekday_index as the production menu forecast.
    Calculate glm_cal_temp separately as a weather-aware shadow forecast.
    """
    results = {}
    weather_shadow = {}
    skipped_inactive = 0

    forecast_temperatures = forecast_temperatures or {}

    required = {
        "date",
        "menu_id",
        "serving_temperature",
        "qty",
    }

    missing = required - set(menu_data.columns)

    if missing:
        raise ValueError(
            f"Menu data columns are missing: {sorted(missing)}"
        )

    if menu_data.empty:
        raise ValueError(
            "Menu training data is empty."
        )

    data = menu_data.copy()

    data["date"] = pd.to_datetime(
        data["date"],
        errors="coerce",
    ).dt.normalize()

    data["menu_id"] = pd.to_numeric(
        data["menu_id"],
        errors="coerce",
    )

    data["qty"] = pd.to_numeric(
        data["qty"],
        errors="coerce",
    )

    if data[["date", "menu_id", "qty"]].isna().any().any():
        raise ValueError(
            "Menu training data contains missing date, menu ID or quantity."
        )

    data["menu_id"] = data["menu_id"].astype(int)

    if (data["qty"] < 0).any():
        raise ValueError(
            "Negative menu quantities exist."
        )

    menu_master = {
        menu.id: menu
        for menu in Menu.objects.filter(store_id=store_id)
    }

    unknown = set(data["menu_id"].unique()) - set(menu_master)

    if unknown:
        raise ValueError(
            "Training data contains menu IDs outside the requested store: "
            f"{sorted(unknown)}"
        )

    future_calendar = _calendar_test(cal, dates)

    historical_temperature = None

    if (
        weather_obs is not None
        and not weather_obs.empty
        and "temp_avg" in weather_obs.columns
    ):
        historical_temperature = pd.to_numeric(
            weather_obs["temp_avg"],
            errors="coerce",
        ).copy()

        historical_temperature.index = pd.to_datetime(
            historical_temperature.index
        ).normalize()

    grouped = data.groupby(
        ["menu_id", "serving_temperature"],
        dropna=False,
        sort=True,
    )

    for (menu_id, raw_temperature), series in grouped:
        menu_id = int(menu_id)
        menu_object = menu_master[menu_id]

        if not menu_object.is_active:
            skipped_inactive += 1
            continue

        if pd.isna(raw_temperature):
            temperature = None
            temperature_key = "UNKNOWN"
        else:
            temperature = str(raw_temperature).strip().upper()

            if temperature not in {"HOT", "ICE"}:
                raise ValueError(
                    f"Menu {menu_id}: unsupported historical serving "
                    f"temperature {temperature!r}."
                )

            temperature_key = temperature

        series = series.sort_values("date").copy()

        if series["date"].duplicated().any():
            raise ValueError(
                f"Menu {menu_id}/{temperature_key}: duplicate dates exist."
            )

        series_dates = pd.DatetimeIndex(series["date"])

        if series_dates.max() >= pd.Timestamp(dates[0]):
            raise ValueError(
                f"Menu {menu_id}/{temperature_key}: training data overlaps "
                "the forecast period."
            )

        calendar_history = cal.reindex(series_dates)

        if calendar_history.isna().all(axis=1).any():
            raise ValueError(
                f"Menu {menu_id}/{temperature_key}: calendar features are "
                "missing from training history."
            )

        frame = (
            series.set_index("date")[["qty"]]
            .sort_index()
            .join(calendar_history, how="left")
        )

        if frame.index.has_duplicates:
            raise ValueError(
                f"Menu {menu_id}/{temperature_key}: duplicate index exists."
            )

        if frame["qty"].isna().any():
            raise ValueError(
                f"Menu {menu_id}/{temperature_key}: missing quantities exist."
            )

        # Calendar baseline is always generated first. KMA-aware predictions
        # replace it only on dates with a valid short/mid-range forecast.
        baseline = _evaluate_and_predict(
            frame,
            "qty",
            dates,
            future_calendar,
            fixed_model=MENU_MODEL,
            candidate_models=(MENU_MODEL,),
        )

        series_key = f"menu:{menu_id}:{temperature_key}"
        combined = {
            **baseline,
            "prediction": np.asarray(baseline["prediction"], dtype=float).copy(),
            "intervals": list(baseline["intervals"]),
        }

        if temperature_key not in {"HOT", "ICE"}:
            weather_shadow[series_key] = {
                "status": "skipped",
                "reason": "unknown_serving_temperature",
            }
        elif historical_temperature is None:
            weather_shadow[series_key] = {
                "status": "skipped",
                "reason": "historical_temperature_unavailable",
            }
        else:
            weather_dates = pd.DatetimeIndex([
                day for day in dates
                if pd.Timestamp(day).normalize() in forecast_temperatures
            ])

            if weather_dates.empty:
                weather_shadow[series_key] = {
                    "status": "skipped",
                    "reason": "kma_forecast_unavailable",
                }
            else:
                try:
                    weather_frame = frame.copy()
                    weather_frame["temp_avg"] = historical_temperature.reindex(
                        weather_frame.index
                    )
                    weather_frame = weather_frame.dropna(subset=["temp_avg"])

                    if len(weather_frame) < MIN_TRAIN_DAYS:
                        raise ValueError(
                            "Insufficient historical rows with valid temperature: "
                            f"{len(weather_frame)}; at least {MIN_TRAIN_DAYS} required."
                        )

                    weather_future = _calendar_test(cal, weather_dates).copy()
                    weather_future["temp_avg"] = [
                        forecast_temperatures[pd.Timestamp(day).normalize()]
                        for day in weather_dates
                    ]

                    weather_result = _evaluate_and_predict(
                        weather_frame,
                        "qty",
                        weather_dates,
                        weather_future,
                        fixed_model=WEATHER_MENU_MODEL,
                        candidate_models=(WEATHER_MENU_MODEL,),
                    )

                    date_positions = {
                        pd.Timestamp(day).normalize(): idx
                        for idx, day in enumerate(pd.DatetimeIndex(dates))
                    }
                    for day, value, interval in zip(
                        weather_dates,
                        weather_result["prediction"],
                        weather_result["intervals"],
                    ):
                        idx = date_positions[pd.Timestamp(day).normalize()]
                        combined["prediction"][idx] = float(value)
                        combined["intervals"][idx] = interval

                    weather_shadow[series_key] = {
                        "status": "applied",
                        "model": WEATHER_MENU_MODEL,
                        "validation_basis": (
                            "observed_target_day_temperature_optimistic_cv"
                        ),
                        "metrics": weather_result["metrics"],
                        "applied_dates": [
                            pd.Timestamp(day).strftime("%Y-%m-%d")
                            for day in weather_dates
                        ],
                        "baseline_dates": [
                            pd.Timestamp(day).strftime("%Y-%m-%d")
                            for day in dates
                            if pd.Timestamp(day).normalize()
                            not in set(weather_dates.normalize())
                        ],
                        "predictions": [
                            {
                                "target_date": pd.Timestamp(day).strftime("%Y-%m-%d"),
                                "predicted_quantity": float(value),
                                "forecast_temperature": float(
                                    forecast_temperatures[pd.Timestamp(day).normalize()]
                                ),
                            }
                            for day, value in zip(
                                weather_dates,
                                weather_result["prediction"],
                            )
                        ],
                    }
                except Exception as exc:
                    # If the weather model cannot run, keep the valid baseline.
                    weather_shadow[series_key] = {
                        "status": "failed",
                        "reason": str(exc)[:500],
                    }

        _save_values(
            forecast_rows,
            series_key,
            "MENU",
            "QUANTITY",
            dates,
            combined,
            menu=menu_object,
            serving_temperature=temperature,
        )

        applied_dates = weather_shadow.get(series_key, {}).get("applied_dates", [])
        results[series_key] = {
            "menu_id": menu_id,
            "serving_temperature": temperature,
            **baseline["metrics"],
            "production_model": (
                f"{MENU_MODEL}+{WEATHER_MENU_MODEL}"
                if applied_dates else MENU_MODEL
            ),
            "weather_applied_dates": applied_dates,
        }

    return {
        "series": results,
        "weather_shadow": weather_shadow,
        "series_count": len(results),
        "skipped_inactive_series": skipped_inactive,
    }


def _validate_forecast_rows(rows, dates):
    if not rows:
        raise ValueError(
            "No forecast values were generated."
        )

    expected_dates = {
        pd.Timestamp(day).date()
        for day in dates
    }

    seen = set()
    series_dates = {}

    for row in rows:
        if row.target_date not in expected_dates:
            raise ValueError(
                f"Unexpected forecast date: {row.target_date}"
            )

        key = (row.series_key, row.target_date)

        if key in seen:
            raise ValueError(
                f"Duplicate forecast value: {key}"
            )

        seen.add(key)

        series_dates.setdefault(
            row.series_key,
            set(),
        ).add(row.target_date)

        if (
            row.predicted_value is None
            or not row.predicted_value.is_finite()
        ):
            raise ValueError(
                f"{row.series_key}: predicted value is missing or invalid."
            )

        if (
            row.predicted_value < 0
            or row.predicted_value > MAX_DECIMAL_VALUE
        ):
            raise ValueError(
                f"{row.series_key}: predicted value is outside DB range."
            )

        if (row.lower_bound is None) != (row.upper_bound is None):
            raise ValueError(
                f"{row.series_key}: incomplete prediction interval."
            )

        if row.lower_bound is not None:
            if (
                not row.lower_bound.is_finite()
                or not row.upper_bound.is_finite()
            ):
                raise ValueError(
                    f"{row.series_key}: prediction interval is invalid."
                )

            if (
                row.lower_bound < 0
                or row.lower_bound > row.upper_bound
            ):
                raise ValueError(
                    f"{row.series_key}: prediction interval bounds are invalid."
                )

            if not (
                row.lower_bound
                <= row.predicted_value
                <= row.upper_bound
            ):
                raise ValueError(
                    f"{row.series_key}: prediction is outside its interval."
                )

        if row.granularity == ForecastValue.Granularity.HOURLY:
            if row.target_hour not in range(
                OPENING_HOUR,
                CLOSING_HOUR + 1,
            ):
                raise ValueError(
                    f"{row.series_key}: invalid target hour."
                )

        elif row.target_hour is not None:
            raise ValueError(
                f"{row.series_key}: target hour is only valid for hourly data."
            )

        if row.granularity == ForecastValue.Granularity.MENU:
            if row.menu_id is None:
                raise ValueError(
                    f"{row.series_key}: menu reference is missing."
                )

            if row.metric != ForecastValue.Metric.QUANTITY:
                raise ValueError(
                    f"{row.series_key}: menu forecast metric must be QUANTITY."
                )

            if row.serving_temperature not in (None, "HOT", "ICE"):
                raise ValueError(
                    f"{row.series_key}: invalid serving temperature."
                )

        elif (
            row.menu_id is not None
            or row.serving_temperature is not None
        ):
            raise ValueError(
                f"{row.series_key}: non-menu forecast has menu attributes."
            )

    for key, actual_dates in series_dates.items():
        if actual_dates != expected_dates:
            missing = sorted(expected_dates - actual_dates)
            extra = sorted(actual_dates - expected_dates)

            raise ValueError(
                f"{key}: incomplete forecast dates. "
                f"Missing={missing}, extra={extra}"
            )

    return {
        "value_count": len(rows),
        "series_count": len(series_dates),
        "dates_per_series": len(expected_dates),
    }


def _persist_forecast(store_id, as_of, rows, metrics, metadata):
    """Persist the run and all forecast values atomically."""
    with transaction.atomic():
        run = ForecastRun.objects.create(
            store_id=store_id,
            as_of=as_of,
            model_version=MODEL_VERSION,
            status=ForecastRun.Status.RUNNING,
            metrics={},
            metadata=metadata,
        )

        for row in rows:
            row.run = run

        ForecastValue.objects.bulk_create(
            rows,
            batch_size=1000,
        )

        run.metrics = metrics
        run.metadata = metadata
        run.status = ForecastRun.Status.COMPLETED

        run.save(
            update_fields=[
                "metrics",
                "metadata",
                "status",
            ]
        )

    return run


def _record_failed_run(store_id, as_of, error, metadata):
    """Record a failed attempt after the forecast transaction rolls back."""
    failed_metadata = {
        **metadata,
        "persist": True,
        "error": str(error)[:2000],
    }

    try:
        with transaction.atomic():
            return ForecastRun.objects.create(
                store_id=store_id,
                as_of=as_of,
                model_version=MODEL_VERSION,
                status=ForecastRun.Status.FAILED,
                metrics={},
                metadata=failed_metadata,
            )

    except Exception:
        return None


def _forecast_value_payload(rows):
    return [
        {
            "series_key": row.series_key,
            "granularity": row.granularity,
            "metric": row.metric,
            "target_date": row.target_date.isoformat(),
            "target_hour": row.target_hour,
            "menu_id": row.menu_id,
            "menu_name": row.menu.name if row.menu_id else None,
            "serving_temperature": row.serving_temperature,
            "predicted_value": float(row.predicted_value),
            "lower_bound": (
                float(row.lower_bound)
                if row.lower_bound is not None
                else None
            ),
            "upper_bound": (
                float(row.upper_bound)
                if row.upper_bound is not None
                else None
            ),
        }
        for row in rows
    ]


def generate_forecasts(store_id, as_of=None, *, persist=False):
    """
    Run the complete operational forecast pipeline.

    persist=False: generate and validate without writing forecast records.
    persist=True: persist the validated run and values atomically.
    """
    if not Store.objects.filter(pk=store_id).exists():
        raise ValueError(
            f"Store does not exist: {store_id}"
        )

    effective_as_of = clamp_as_of(
        as_of if as_of is not None else default_as_of()
    )

    dates = _future_dates(effective_as_of)
    forecast_rows = []

    base_metadata = {
        "horizon_days": HORIZON_DAYS,
        "target_dates": [
            day.strftime("%Y-%m-%d")
            for day in dates
        ],
        "as_of_policy": "KST last complete day; future rows excluded",
        "menu_model": MENU_MODEL,
        "hourly_model": HOURLY_MODEL,
        "weather_menu_model": WEATHER_MENU_MODEL,
        "weather_shadow_model": WEATHER_MENU_MODEL,  # compatibility for existing consumers
        "daily_weather_enabled": False,
        "weather_shadow_only": False,
        "persist": bool(persist),
    }

    try:
        daily, hourly, menu_data, cal, weather = build_daily_frame(
            store_id,
            as_of=effective_as_of,
        )

        # Weather collection failures must not stop the baseline forecast.
        try:
            (
                forecast_temperatures,
                weather_status,
            ) = _get_forecast_temperatures(
                store_id=store_id,
                dates=dates,
                weather_obs=weather,
            )

        except Exception as exc:
            forecast_temperatures = {}

            weather_status = {
                "status": "unavailable",
                "reason": "weather_forecast_error",
                "error": type(exc).__name__,
                "forecast_dates": [],
            }

        daily_results = _daily_forecasts(
            daily,
            cal,
            dates,
            forecast_rows,
            forecast_temperatures=forecast_temperatures,
        )

        hourly_results = _hourly_forecasts(
            hourly,
            cal,
            dates,
            forecast_rows,
        )

        menu_results = _menu_forecasts(
            menu_data=menu_data,
            cal=cal,
            dates=dates,
            store_id=store_id,
            forecast_rows=forecast_rows,
            weather_obs=weather,
            forecast_temperatures=forecast_temperatures,
        )

        metrics = {
            "daily": daily_results,
            "hourly": hourly_results,
            "menu": menu_results["series"],
            "menu_weather_shadow": menu_results["weather_shadow"],
        }

        validation = _validate_forecast_rows(
            forecast_rows,
            dates,
        )

        metadata = {
            **base_metadata,
            "daily_series_count": len(daily_results),
            "hourly_series_count": len(hourly_results),
            "menu_series_count": menu_results["series_count"],
            "inactive_menu_series_skipped": (
                menu_results["skipped_inactive_series"]
            ),
            "total_series_count": validation["series_count"],
            "forecast_value_count": validation["value_count"],
            "dates_per_series": validation["dates_per_series"],
            "weather_forecast": weather_status,
            "daily_weather_enabled": any(
                any(
                    model.endswith("_temp")
                    for model in result.get("forecast_models_by_date", {}).values()
                )
                for result in daily_results.values()
            ),
            "daily_weather_applied_dates": sorted({
                day
                for result in daily_results.values()
                for day, model in result.get("forecast_models_by_date", {}).items()
                if model.endswith("_temp")
            }),
            "menu_weather_applied_series": [
                key for key, value in menu_results["weather_shadow"].items()
                if value.get("status") == "applied"
            ],
        }

        if persist:
            run = _persist_forecast(
                store_id,
                effective_as_of,
                forecast_rows,
                metrics,
                metadata,
            )

            return {
                "run_id": run.pk,
                "status": ForecastRun.Status.COMPLETED,
                "store_id": store_id,
                "as_of": effective_as_of.isoformat(),
                "target_dates": metadata["target_dates"],
                "metadata": metadata,
                "metrics": metrics,
                "values": _forecast_value_payload(forecast_rows),
            }

        return {
            "run_id": None,
            "status": "DRY_RUN_COMPLETED",
            "store_id": store_id,
            "as_of": effective_as_of.isoformat(),
            "target_dates": metadata["target_dates"],
            "metadata": metadata,
            "metrics": metrics,
            "values": _forecast_value_payload(forecast_rows),
        }

    except Exception as exc:
        if persist:
            _record_failed_run(
                store_id=store_id,
                as_of=effective_as_of,
                error=exc,
                metadata=base_metadata,
            )

        raise
