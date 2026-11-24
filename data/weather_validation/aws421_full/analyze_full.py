"""Parse saved AWS 421 raw responses, validate, compare with ASOS 108 (read-only)."""
import csv, json, statistics as st, calendar
from datetime import date, timedelta
from pathlib import Path
from collections import defaultdict

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
months = [(2025, m) for m in range(1, 13)] + [(2026, m) for m in range(1, 11)]


TOKENS = ("null", "x", "")


def num(s):
    s = (s if s is not None else "").strip()
    return None if s in TOKENS else float(s)


rows, mrep, summ_rows = [], [], []
for y, m in months:
    raw = json.loads((OUT / "raw" / f"raw_{y}-{m:02d}.json").read_text(encoding="utf-8"))
    h = raw["response"]["header"]
    b = raw["response"].get("body")
    rec = {"month": f"{y}-{m:02d}", "resultCode": h["resultCode"], "resultMsg": h["resultMsg"]}
    if h["resultCode"] != "00" or not b:
        rec.update(status="NO_DATA", day_rows=0, summary_rows=0, expected_days=calendar.monthrange(y, m)[1])
        mrep.append(rec)
        continue
    items = b["items"]["item"]
    info = []
    for it in items:
        a = it["awsmdays"]
        stn = a["stn_id"]
        info += a["info"]
    day = [r for r in info if str(r["tm"]).strip().isdigit()]
    summ = [r for r in info if not str(r["tm"]).strip().isdigit()]
    for lab, r in zip(("상순", "중순", "하순", "월합계"), summ):
        summ_rows.append((f"{y}-{m:02d}", lab, r["rn_day"].strip()))
    for r in day:
        d = date(y, m, int(r["tm"]))
        rows.append(dict(
            date=d.isoformat(), station_id=stn,
            avg_temp_c=num(r.get("ta_day")), max_temp_c=num(r.get("ta_max")), min_temp_c=num(r.get("ta_min")),
            precipitation_mm=num(r.get("rn_day")), rain_token=(r.get("rn_day") or "").strip() if (r.get("rn_day") or "").strip() in ("null", "x") else "value", wind_speed_avg_ms=num(r.get("ws_day")),
            wind_speed_max_ins_ms=num(r.get("ws_ins_max")), wind_dir_max_ins_deg=num(r.get("wd_ins_max")),
            raw_rn_day=(r.get("rn_day") or "").strip()))
    rec.update(status="OK", totalCount=b.get("totalCount"), n_items=len(items), day_rows=len(day),
               summary_rows=len(summ), summary_labels_note="raw labels garbled; positional: 상순,중순,하순,월합계",
               expected_days=calendar.monthrange(y, m)[1], fields=sorted({k for r in info for k in r}))
    mrep.append(rec)

rows.sort(key=lambda r: r["date"])
VARS = ["avg_temp_c", "max_temp_c", "min_temp_c", "precipitation_mm", "wind_speed_avg_ms",
        "wind_speed_max_ins_ms", "wind_dir_max_ins_deg"]
cols = ["date", "station_id"] + VARS + ["rain_token", "raw_rn_day"]
with open(OUT / "aws421_daily_2025-01_2026-10.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(rows)

exp = []
d = date(2025, 1, 1)
while d <= date(2026, 10, 31):
    exp.append(d.isoformat())
    d += timedelta(1)
got = [r["date"] for r in rows]
dups = sorted({x for x in got if got.count(x) > 1})
missing = sorted(set(exp) - set(got))
extra = sorted(set(got) - set(exp))
unpub_missing = [x for x in missing if x.startswith("2026-10")]
other_missing = [x for x in missing if not x.startswith("2026-10")]


def rate(sub):
    return {v: {"n": len(sub), "missing": sum(1 for r in sub if r[v] is None)} for v in VARS}


def season(mo):
    return "봄(3-5)" if mo in (3, 4, 5) else "여름(6-8)" if mo in (6, 7, 8) else "가을(9-11)" if mo in (9, 10, 11) else "겨울(12-2)"


by_m, by_s = defaultdict(list), defaultdict(list)
for r in rows:
    by_m[r["date"][:7]].append(r)
    by_s[season(int(r["date"][5:7]))].append(r)
miss_m = {k: rate(v) for k, v in sorted(by_m.items())}
miss_s = {k: rate(v) for k, v in by_s.items()}
SENT = (-9, -99, -999, -9.9, -99.9, -999.0)
sent = {v: sum(1 for r in rows if r[v] is not None and r[v] in SENT) for v in VARS}
rng = {}
for v in VARS:
    vals = [x[v] for x in rows if x[v] is not None]
    rng[v] = (min(vals), max(vals)) if vals else None
viol, partial = [], []
for r in rows:
    t = [r["min_temp_c"], r["avg_temp_c"], r["max_temp_c"]]
    if None in t:
        if any(x is not None for x in t):
            partial.append(r["date"])
        continue
    if not (t[0] <= t[1] <= t[2]):
        viol.append((r["date"], *t))
negrain = [r["date"] for r in rows if r["precipitation_mm"] is not None and r["precipitation_mm"] < 0]

by_label = defaultdict(dict)
for mo, lab, v in summ_rows:
    by_label[mo][lab] = v
sumchk = []
for mo, labs in by_label.items():
    ds = [r["precipitation_mm"] for r in by_m[mo] if r["precipitation_mm"] is not None]
    sumchk.append({"month": mo, "labels": labs, "daily_sum": round(sum(ds), 2), "n_daily_with_rain_value": len(ds)})

asos = {}
with open(ROOT / "data/weather/404dabang_asos_daily_weather.csv", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        asos[r["date"]] = r
comp = []
for r in rows:
    a = asos.get(r["date"])
    o = {"date": r["date"], "in_asos": a is not None}
    for k, ak in (("avg", "avg_temp_c"), ("max", "max_temp_c"), ("min", "min_temp_c")):
        x = r[f"{k}_temp_c"]
        y = num(a[ak]) if a else None
        o[f"aws_{k}"] = x
        o[f"asos_{k}"] = y
        o[f"d_{k}"] = None if x is None or y is None else round(x - y, 2)
    x = r["precipitation_mm"]
    ar = a["precipitation_mm"].strip() if a else None
    y = num(ar) if a else None
    o["aws_rain"] = x
    o["asos_rain"] = y
    o["asos_rain_blank"] = (ar == "") if a else None
    o["asos_is_rain"] = a["is_rain"] if a else None
    o["asos_observation_received"] = a["observation_received"] if a else None
    o["d_rain"] = None if x is None or y is None else round(x - y, 2)
    comp.append(o)
with open(OUT / "comparison_with_asos108.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(comp[0].keys()))
    w.writeheader()
    w.writerows(comp)


def stats(key):
    d = [c[key] for c in comp if c[key] is not None]
    return {"n": len(d), "mean_diff": round(st.mean(d), 3), "MAE": round(st.mean(abs(x) for x in d), 3),
            "RMSE": round((st.mean(x * x for x in d)) ** .5, 3), "max_abs": max(abs(x) for x in d),
            "min": min(d), "max": max(d), "median_diff": round(st.median(d), 3)}


T = {k: stats(f"d_{k}") for k in ("avg", "max", "min")}


def tstats(sub):
    out = {}
    for k in ("avg", "max", "min"):
        d = [c[f"d_{k}"] for c in sub if c[f"d_{k}"] is not None]
        out[k] = {"n": len(d), "mean_diff": round(st.mean(d), 2), "MAE": round(st.mean(abs(x) for x in d), 2)} if d else None
    return out


tm, ts = defaultdict(list), defaultdict(list)
for c in comp:
    tm[c["date"][:7]].append(c)
    ts[season(int(c["date"][5:7]))].append(c)
T_month = {k: tstats(v) for k, v in sorted(tm.items())}
T_season = {k: tstats(v) for k, v in ts.items()}

both = [c for c in comp if c["aws_rain"] is not None and c["asos_rain"] is not None]
ablank = [c for c in comp if c["asos_rain_blank"]]
rain = {
    "asos_rows_matched": sum(c["in_asos"] for c in comp),
    "aws_rain_valid": sum(c["aws_rain"] is not None for c in comp),
    "asos_rain_blank_days": len(ablank),
    "asos_rain_value_days": sum(c["asos_rain"] is not None for c in comp),
    "both_value_days": len(both),
    "rain_diff_on_both": stats("d_rain") if both else None,
    "aws_zero_on_asos_blank": sum(c["aws_rain"] == 0 for c in ablank),
    "aws_positive_on_asos_blank": [(c["date"], c["aws_rain"]) for c in ablank if c["aws_rain"] and c["aws_rain"] > 0],
    "aws_missing_on_asos_blank": sum(c["aws_rain"] is None for c in ablank),
    "asos_value_on_aws_missing": sum(c["aws_rain"] is None and c["asos_rain"] is not None for c in comp),
}
rain["rain_day_thresholds"] = {}
for th in (0.1, 0.5, 1.0):
    def rd(v):
        return v is not None and v >= th
    a_pos = {c["date"] for c in comp if rd(c["aws_rain"])}
    s_pos = {c["date"] for c in comp if rd(c["asos_rain"])}
    agree = sum(rd(c["aws_rain"]) == rd(c["asos_rain"]) for c in both)
    rain["rain_day_thresholds"][str(th)] = {
        "aws_days": len(a_pos), "asos_days": len(s_pos), "both": len(a_pos & s_pos),
        "aws_only": len(a_pos - s_pos), "asos_only": len(s_pos - a_pos),
        "agree_on_both_value_days": agree, "n_both_value_days": len(both)}
rain["asos_is_rain_counts"] = {k: sum(1 for c in comp if c["asos_is_rain"] == k) for k in ("true", "false", "")}
rain["aws_positive_days"] = sum(1 for c in comp if c["aws_rain"] and c["aws_rain"] > 0)
rain["aws_total_mm"] = round(sum(c["aws_rain"] for c in comp if c["aws_rain"] is not None), 1)
rain["asos_total_mm_on_both"] = round(sum(c["asos_rain"] for c in both), 1)
rain["aws_total_mm_on_both"] = round(sum(c["aws_rain"] for c in both), 1)
rain["aws_nonmultiple_of_0.5"] = sum(1 for c in comp if c["aws_rain"] is not None and round(c["aws_rain"] * 10) % 5 != 0)
rain["monthly"] = {k: {
    "aws_mm": round(sum(c["aws_rain"] for c in v if c["aws_rain"] is not None), 1),
    "asos_mm": round(sum(c["asos_rain"] for c in v if c["asos_rain"] is not None), 1),
    "aws_pos_days": sum(1 for c in v if c["aws_rain"] and c["aws_rain"] > 0),
    "asos_pos_days": sum(1 for c in v if c["asos_rain"] and c["asos_rain"] > 0),
    "asos_blank": sum(bool(c["asos_rain_blank"]) for c in v)} for k, v in sorted(tm.items())}
asos_dates = sorted(asos)
def asos_cat(c):
    if not c["in_asos"]: return "no_asos_row"
    if c["asos_rain_blank"]: return "asos_blank"
    return "asos_zero" if c["asos_rain"] == 0 else "asos_positive"
tok = {r["date"]: r["rain_token"] for r in rows}
rain["aws_token_counts"] = {t: sum(1 for v in tok.values() if t == v) for t in ("value", "null", "x")}
rain["asos_category_by_aws_token"] = {t: {k: sum(1 for c in comp if tok[c["date"]] == t and asos_cat(c) == k) for k in ("asos_blank", "asos_zero", "asos_positive", "no_asos_row")} for t in ("value", "null", "x")}
rain["asos_category_when_aws_value"] = {}
for lab, f in (("aws_zero", lambda c: c["aws_rain"] == 0), ("aws_positive", lambda c: c["aws_rain"] is not None and c["aws_rain"] > 0)):
    rain["asos_category_when_aws_value"][lab] = {k: sum(1 for c in comp if f(c) and asos_cat(c) == k) for k in ("asos_blank", "asos_zero", "asos_positive")}
rain["asos_positive_on_aws_null_or_x"] = [(c["date"], tok[c["date"]], c["asos_rain"]) for c in comp if tok[c["date"]] != "value" and c["asos_rain"] and c["asos_rain"] > 0]
rain["asos_positive_sum_on_aws_null_or_x"] = round(sum(x[2] for x in rain["asos_positive_on_aws_null_or_x"]), 1)
rain["aws_null_by_month"] = {k: {"value": sum(1 for r in v if r["rain_token"] == "value"), "null": sum(1 for r in v if r["rain_token"] == "null"), "x": sum(1 for r in v if r["rain_token"] == "x")} for k, v in sorted(by_m.items())}
# ten-day summary vs daily sums
def seg(day):
    return "상순" if day <= 10 else "중순" if day <= 20 else "하순"
tenchk = []
for mo, labs in by_label.items():
    for lab in ("상순", "중순", "하순", "월합계"):
        ds = [r for r in by_m[mo] if lab == "월합계" or seg(int(r["date"][8:])) == lab]
        vals = [r["precipitation_mm"] for r in ds if r["precipitation_mm"] is not None]
        nn = sum(1 for r in ds if r["precipitation_mm"] is None)
        tenchk.append({"month": mo, "period": lab, "summary": labs.get(lab), "sum_of_daily_values": round(sum(vals), 2), "n_daily_null_or_x": nn})
rain["ten_day_check"] = tenchk
report = {
    "station": 421, "endpoint": "https://apis.data.go.kr/1360000/AwsMtlyInfoService/getDailyAwsData",
    "requested_period": ["2025-01-01", "2026-10-31"], "requested_days": len(exp), "calls": len(months),
    "months": mrep, "daily_rows_collected": len(rows),
    "date_coverage": {"duplicates": dups, "missing_total": len(missing),
                      "missing_in_2026-10_unpublished": len(unpub_missing), "missing_other": other_missing,
                      "unexpected_dates": extra, "first": got[0], "last": got[-1]},
    "asos108_csv": {"rows": len(asos), "first": asos_dates[0], "last": asos_dates[-1],
                    "n_dates_not_in_aws": len(set(asos) - set(got)), "dates_not_in_aws_sample": sorted(set(asos) - set(got))[:3]},
    "missing_by_variable_total": {v: sum(1 for r in rows if r[v] is None) for v in VARS},
    "sentinel_like_values": sent, "ranges": rng,
    "temp_logic": {"min<=avg<=max_violations": viol, "partially_missing_temp_days": partial, "negative_rain": negrain},
    "summary_rows_check": sumchk, "ten_day_check": rain["ten_day_check"], "missing_by_month": miss_m, "missing_by_season": miss_s,
    "raw_rn_day_blank_strings": sum(1 for r in rows if r["raw_rn_day"] == ""),
}
(OUT / "collection_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
(OUT / "_comparison_stats.json").write_text(json.dumps(
    {"temp": T, "temp_by_month": T_month, "temp_by_season": T_season, "rain": rain}, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: report[k] for k in ("daily_rows_collected", "date_coverage", "asos108_csv", "missing_by_variable_total",
                                         "sentinel_like_values", "ranges", "temp_logic", "raw_rn_day_blank_strings")},
                 ensure_ascii=False, indent=1))
print({m["month"]: (m["day_rows"], m["expected_days"], m.get("summary_labels")) for m in mrep if m["day_rows"] != m["expected_days"] or m["month"] == "2025-01"})
print(json.dumps(sumchk[:2], ensure_ascii=False))
print(json.dumps({"temp": T, "season": T_season}, ensure_ascii=False, indent=1))
print(json.dumps({k: v for k, v in rain.items() if k not in ("monthly", "ten_day_check", "aws_null_by_month")}, ensure_ascii=False, indent=1))
