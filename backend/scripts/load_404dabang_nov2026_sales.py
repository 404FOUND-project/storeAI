"""Load sales_dummy_nov2026_v1 (2026-11-01..2026-11-30) into Sales / SalesItem.

Thin wrapper over load_404dabang_final_sales: same validation, same dry-run
default, same insert-only/atomic behaviour. Only the period, order-id prefix and
the order_details column name (serving_temperature) differ.

    python scripts/load_404dabang_nov2026_sales.py            # dry run
    python scripts/load_404dabang_nov2026_sales.py --apply    # real load
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import load_404dabang_final_sales as base  # noqa: E402

base.PERIOD_START, base.PERIOD_END, base.EXPECTED_DAYS = "2026-11-01", "2026-11-30", 30
base.SOURCE_PREFIX = "N26-"
base.DEFAULT_CSV_DIR = base.PROJECT_ROOT / "data" / "synthetic_sales" / "sales_dummy_nov2026_v1"

_read_csv = base.read_csv


def read_csv(path, required):
    if path.name == "order_details.csv":
        required = ["temperature" if c == "temperature" else c for c in required]
        required = [c for c in required if c != "temperature"] + ["serving_temperature"]
    rows = _read_csv(path, required)
    if path.name == "order_details.csv":
        for row in rows:
            # UNKNOWN = dessert menus; the existing dataset stores these as NULL.
            t = row["serving_temperature"]
            row["temperature"] = "" if t == "UNKNOWN" else t
    return rows


base.read_csv = read_csv

if __name__ == "__main__":
    sys.argv = [sys.argv[0]] + sys.argv[1:] + (
        [] if "--csv-dir" in sys.argv else ["--csv-dir", str(base.DEFAULT_CSV_DIR)])
    base.main()
