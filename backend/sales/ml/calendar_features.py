"""Calendar, holiday and school-schedule features (pure pandas, no database).

Rules (kept from the validated analysis in data/weather_sales_validation):
- only events with verified_status in {verified, user_confirmed} become model inputs;
  estimated events (Hanyang high school 2025) are exposed as separate *_est_* columns
  and are NOT used as model features;
- a school flag is 1 only when a confirmed event covers the date, otherwise 0
  ("not confirmed" is never treated as a confirmed absence in the *_known columns);
- all features depend on the date only, so they are known for future dates.
"""
import csv
from pathlib import Path

import numpy as np
import pandas as pd

SCHOOLS = {"hanyang": "한양대학교 서울캠퍼스", "hywoman": "한양여자대학교", "hs": "한양대학교 사범대학 부속고등학교"}
CONFIRMED = {"verified", "user_confirmed"}
SEASONS = {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring", 5: "spring",
           6: "summer", 7: "summer", 8: "summer", 9: "autumn", 10: "autumn", 11: "autumn"}


def school_key(name: str) -> str:
    if "여자" in name:
        return "hywoman"
    if "부속" in name or "한대부고" in name:
        return "hs"
    return "hanyang"


def load_holidays(paths):
    """-> {date: [names]} from one or more holiday CSVs (same columns as 404dabang_holidays.csv)."""
    out = {}
    for path in paths:
        path = Path(path)
        if not path.exists():
            continue
        with open(path, encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                if row.get("isHoliday", "Y") != "Y":
                    continue
                day = pd.Timestamp(str(row["locdate"])).normalize()
                names = out.setdefault(day, [])
                if row["dateName"] not in names:
                    names.append(row["dateName"])
    return out


def load_events(path) -> pd.DataFrame:
    ev = pd.read_csv(path, encoding="utf-8")
    ev["school"] = ev.school_name.map(school_key)
    ev["start"] = pd.to_datetime(ev.start_date)
    ev["end"] = pd.to_datetime(ev.end_date)
    ev["confirmed"] = ev.verified_status.isin(CONFIRMED)
    return ev


def _mark(index, ev, school, event_type, confirmed):
    flag = pd.Series(0, index=index, dtype=int)
    sel = ev[(ev.school == school) & (ev.event_type == event_type) & (ev.confirmed == confirmed)]
    for r in sel.itertuples():
        flag[(index >= r.start) & (index <= r.end)] = 1
    return flag


def _semester(index, ev, school, confirmed):
    """1 inside [semester_start, next semester_end]; only complete pairs count."""
    flag = pd.Series(0, index=index, dtype=int)
    sel = ev[(ev.school == school) & (ev.confirmed == confirmed)]
    starts = sel[sel.event_type == "semester_start"].start.sort_values().tolist()
    ends = sel[sel.event_type == "semester_end"].end.sort_values().tolist()
    for s in starts:
        later = [e for e in ends if e >= s]
        if later:
            flag[(index >= s) & (index <= later[0])] = 1
    return flag


def academic_frame(index: pd.DatetimeIndex, ev: pd.DataFrame) -> pd.DataFrame:
    cols = {}
    for key in SCHOOLS:
        cols[f"{key}_exam"] = _mark(index, ev, key, "exam", True)
        cols[f"{key}_vacation"] = _mark(index, ev, key, "vacation", True)
        cols[f"{key}_semester"] = _semester(index, ev, key, True)
        cols[f"{key}_est_exam"] = _mark(index, ev, key, "exam", False)
        cols[f"{key}_est_vacation"] = _mark(index, ev, key, "vacation", False)
    df = pd.DataFrame(cols, index=index)
    df["exam_any"] = df[[f"{k}_exam" for k in SCHOOLS]].max(axis=1)
    df["vacation_any"] = df[[f"{k}_vacation" for k in SCHOOLS]].max(axis=1)
    return df


def calendar_frame(start, end, holidays: dict, events: pd.DataFrame, trend_origin="2025-01-01") -> pd.DataFrame:
    """One row per day in [start, end] with all date-derived features."""
    index = pd.date_range(start, end, freq="D")
    df = pd.DataFrame(index=index)
    df.index.name = "date"
    df["weekday"] = index.weekday
    df["is_weekend"] = (index.weekday >= 5).astype(int)
    df["month"] = index.month
    df["season"] = [SEASONS[m] for m in index.month]
    df["month_phase"] = np.where(index.day <= 10, 1, np.where(index.day <= 20, 2, 3))
    df["trend_days"] = (index - pd.Timestamp(trend_origin)).days
    df["hol"] = [int(d in holidays) for d in index]
    df["holiday_name"] = [", ".join(holidays.get(d, [])) for d in index]
    nonwork = ((df.weekday >= 5) | (df.hol == 1)).astype(int).to_numpy()
    run = np.zeros(len(df), int)
    i = 0
    while i < len(df):
        if nonwork[i]:
            j = i
            while j < len(df) and nonwork[j]:
                j += 1
            run[i:j] = j - i
            i = j
        else:
            i += 1
    n = len(df)
    df["long_break"] = (run >= 3).astype(int)
    df["pre_long_break"] = [int(k + 1 < n and run[k + 1] >= 3 and not nonwork[k]) for k in range(n)]
    df["post_long_break"] = [int(k > 0 and run[k - 1] >= 3 and not nonwork[k]) for k in range(n)]
    df = df.join(academic_frame(index, events))
    return df
