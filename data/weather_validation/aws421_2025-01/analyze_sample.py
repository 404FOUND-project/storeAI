"""Parse the saved AWS 421 response and compare with ASOS 108 (read-only on the ASOS CSV)."""
import csv
import json
import statistics as st
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
raw = json.loads((OUT / "raw_response.txt").read_text(encoding="utf-8"))
body = raw["response"]["body"]
items = body["items"]["item"]
print("header", raw["response"]["header"], "totalCount", body.get("totalCount"), "numOfRows", body.get("numOfRows"),
      "n_items", len(items), "keys", [list(i.keys()) for i in items][:3])
info, stn = [], None
for it in items:
    a = it["awsmdays"]
    stn = (a.get("stn_id"), a.get("stn_ko"), a.get("stn_en"))
    info.extend(a["info"])
print("station", stn, "info rows", len(info), "fields", sorted({k for r in info for k in r}))


def num(s):
    s = (s or "").strip()
    return None if s == "" else float(s)


rows = []
period_rows = [r for r in info if not str(r["tm"]).strip().isdigit()]
info = [r for r in info if str(r["tm"]).strip().isdigit()]
print("non-day summary rows (tm label -> rn_day):", [(r["tm"], r["rn_day"].strip()) for r in period_rows])
for r in info:
    rows.append({
        "date": f"2025-01-{int(r['tm']):02d}",
        "aws_avg_temp_c": num(r.get("ta_day")),
        "aws_max_temp_c": num(r.get("ta_max")),
        "aws_min_temp_c": num(r.get("ta_min")),
        "aws_precipitation_mm": num(r.get("rn_day")),
        "raw_rn_day": r.get("rn_day"), "raw_ta_day": r.get("ta_day"),
    })
dates = [r["date"] for r in rows]
expected = [f"2025-01-{d:02d}" for d in range(1, 32)]
print("dup dates", len(dates) - len(set(dates)), "missing dates", sorted(set(expected) - set(dates)),
      "extra", sorted(set(dates) - set(expected)))
for c in ["aws_avg_temp_c", "aws_max_temp_c", "aws_min_temp_c", "aws_precipitation_mm"]:
    v = [r[c] for r in rows if r[c] is not None]
    print(c, "missing", len(rows) - len(v), "min", min(v), "max", max(v))
print("raw rn_day distinct strings", sorted({r["raw_rn_day"] for r in rows}))
sent = [r for r in rows if r["aws_precipitation_mm"] is not None and r["aws_precipitation_mm"] <= -9]
print("sentinel-like (<=-9) values", len(sent))
bad = [r["date"] for r in rows if None not in (r["aws_min_temp_c"], r["aws_avg_temp_c"], r["aws_max_temp_c"])
       and not (r["aws_min_temp_c"] <= r["aws_avg_temp_c"] <= r["aws_max_temp_c"])]
print("min<=avg<=max violations", bad)

asos = {}
with open(ROOT / "data/weather/404dabang_asos_daily_weather.csv", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["date"].startswith("2025-01"):
            asos[r["date"]] = r
print("asos jan rows", len(asos))

with open(OUT / "aws421_2025-01_clean.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["date", "station_id", "avg_temp_c", "max_temp_c", "min_temp_c", "precipitation_mm", "raw_rn_day"])
    for r in sorted(rows, key=lambda x: x["date"]):
        w.writerow([r["date"], stn[0], r["aws_avg_temp_c"], r["aws_max_temp_c"], r["aws_min_temp_c"],
                    r["aws_precipitation_mm"], r["raw_rn_day"].strip()])

comp = []
for r in sorted(rows, key=lambda x: x["date"]):
    a = asos.get(r["date"])
    def d(k1, k2):
        x, y = r[k1], num(a[k2]) if a else None
        return None if x is None or y is None else round(x - y, 2)
    comp.append({
        "date": r["date"],
        "aws_avg": r["aws_avg_temp_c"], "asos_avg": num(a["avg_temp_c"]), "d_avg": d("aws_avg_temp_c", "avg_temp_c"),
        "aws_max": r["aws_max_temp_c"], "asos_max": num(a["max_temp_c"]), "d_max": d("aws_max_temp_c", "max_temp_c"),
        "aws_min": r["aws_min_temp_c"], "asos_min": num(a["min_temp_c"]), "d_min": d("aws_min_temp_c", "min_temp_c"),
        "aws_rain": r["aws_precipitation_mm"], "asos_rain": num(a["precipitation_mm"]),
        "asos_rain_blank": a["precipitation_mm"] == "", "d_rain": d("aws_precipitation_mm", "precipitation_mm"),
    })
with open(OUT / "comparison_aws421_vs_asos108_2025-01.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(comp[0].keys()))
    w.writeheader()
    w.writerows(comp)


def stats(key):
    v = [c[key] for c in comp if c[key] is not None]
    return {"n": len(v), "mean_diff": round(st.mean(v), 2), "mean_abs_diff": round(st.mean(abs(x) for x in v), 2),
            "max_abs_diff": round(max(abs(x) for x in v), 2), "min_diff": min(v), "max_diff": max(v)}


summary = {"temp": {k: stats(k) for k in ["d_avg", "d_max", "d_min"]}}
both = [c for c in comp if c["aws_rain"] is not None and c["asos_rain"] is not None]
aws_rain_days = [c for c in comp if c["aws_rain"] is not None and c["aws_rain"] > 0]
asos_rain_days = [c for c in comp if c["asos_rain"] is not None and c["asos_rain"] > 0]
asos_blank = [c for c in comp if c["asos_rain_blank"]]
summary["rain"] = {
    "aws_days_with_value": sum(1 for c in comp if c["aws_rain"] is not None),
    "aws_zero_days": sum(1 for c in comp if c["aws_rain"] == 0.0),
    "aws_positive_days": len(aws_rain_days),
    "asos_blank_days": len(asos_blank),
    "asos_zero_days": sum(1 for c in comp if c["asos_rain"] == 0.0),
    "asos_positive_days": len(asos_rain_days),
    "aws_positive_dates": [(c["date"], c["aws_rain"]) for c in aws_rain_days],
    "asos_positive_dates": [(c["date"], c["asos_rain"]) for c in asos_rain_days],
    "aws_value_on_asos_blank_dates": [(c["date"], c["aws_rain"]) for c in asos_blank if c["aws_rain"] != 0.0],
    "n_asos_blank_where_aws_zero": sum(1 for c in asos_blank if c["aws_rain"] == 0.0),
    "n_both_values": len(both),
}
if both:
    summary["rain"]["diff_on_both"] = [(c["date"], c["aws_rain"], c["asos_rain"]) for c in both]
print(json.dumps(summary, ensure_ascii=False, indent=1))
(OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
