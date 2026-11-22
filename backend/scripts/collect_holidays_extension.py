"""Collect Korean public holidays from KASI for a month range and write a NEW csv.

The original data/holidays/404dabang_holidays.csv (2025-01..2026-10) is never modified;
the extension is written next to it with the same columns. Months KASI has no data for
are reported as unavailable, not assumed to be holiday-free.

    python scripts/collect_holidays_extension.py --start 2026-11 --end 2027-12
"""
import argparse
import csv
import json
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))
from weatherdata.services.kma_http import KmaRequestError, get_json  # noqa: E402

ENDPOINT = "https://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo"
SOURCE = "KASI Special Day Information API (getRestDeInfo)"
COLUMNS = ["locdate", "dateName", "dateKind", "isHoliday", "source",
           "holiday_classification", "substitute_holiday_status"]


def env_key():
    if os.environ.get("KASI_SERVICE_KEY"):
        return os.environ["KASI_SERVICE_KEY"]
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("KASI_SERVICE_KEY="):
            return line.split("=", 1)[1].strip().strip("\"'")
    return ""


def months(start, end):
    y, m = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    while (y, m) <= (ey, em):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-11")
    ap.add_argument("--end", default="2027-12")
    ap.add_argument("--out-dir", default=str(ROOT / "data" / "holidays"))
    args = ap.parse_args()
    key = env_key()
    rows, report = [], []
    for y, m in months(args.start, args.end):
        try:
            items, _ = get_json(ENDPOINT, {"solYear": y, "solMonth": f"{m:02d}", "_type": "json",
                                           "numOfRows": 50}, key)
            status = "complete"
        except KmaRequestError as exc:
            items, status = [], f"unavailable:{exc.code}"
        for it in items:
            name = str(it["dateName"])
            rows.append({
                "locdate": str(it["locdate"]), "dateName": name, "dateKind": str(it["dateKind"]).zfill(2),
                "isHoliday": it["isHoliday"], "source": SOURCE, "holiday_classification": "public_holiday",
                "substitute_holiday_status": "confirmed" if "대체" in name else "not_indicated",
            })
        report.append({"year": y, "month": m, "status": status, "rows_received": len(items)})
    out = Path(args.out_dir)
    tag = f"{args.start}_{args.end}"
    with open(out / f"404dabang_holidays_{tag}.csv", "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: r["locdate"]))
    (out / f"404dabang_holiday_collection_report_{tag}.json").write_text(
        json.dumps({"source": SOURCE, "requested": [args.start, args.end], "monthly_results": report},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"holidays={len(rows)} incomplete_months={[r for r in report if r['status'] != 'complete']}")
    for r in sorted(rows, key=lambda r: r["locdate"]):
        print(r["locdate"], r["dateName"])


if __name__ == "__main__":
    main()
