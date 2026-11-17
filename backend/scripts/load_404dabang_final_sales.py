"""Load the sales_dummy_v1_final CSV dataset into Sales / SalesItem.

Default mode is a READ-ONLY dry run: CSVs are validated and compared with the
database, nothing is written. Pass --apply to insert, in ONE transaction.

Design notes
- Menus are mapped by Menu.pos_code (store scoped), never by fixed integer PK.
- Orders are keyed by Sales.source_order_id (unique per store).
- payment_method / data_type / dataset_version are intentionally NOT loaded.
- Existing rows are never updated or deleted. --apply refuses to run if the
  target store already has any sales in the dataset period or any of the
  dataset's source_order_id values.
- SalesItem rows are bulk-inserted through the plain QuerySet.bulk_create to avoid
  ~90k per-row FK queries from full_clean(); every rule that SalesItem.clean()
  enforces (menu exists, temperature allowed for the menu) is checked here for
  all rows before any write, and re-verified in SQL after the write (inside the
  transaction, so a failure rolls everything back).

Usage (from the backend directory):
    python scripts/load_404dabang_final_sales.py              # dry run
    python scripts/load_404dabang_final_sales.py --apply      # real load
"""
import argparse
import collections
import csv
import os
import sys
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
DEFAULT_CSV_DIR = PROJECT_ROOT / "data" / "synthetic_sales" / "sales_dummy_v1_final"
DEFAULT_STORE_NAME = "404다방"
REQUIRED_MIGRATION = ("sales", "0003_sales_source_order_id")
EXPECTED_MENUS = {f"M{n:03d}" for n in range(1, 28)}
PERIOD_START, PERIOD_END = "2025-01-01", "2026-10-31"
EXPECTED_DAYS = 669
SALES_BATCH, ITEM_BATCH = 2000, 3000
ALLOWED_TEMPS = {
    "BOTH": {"HOT", "ICE"},
    "HOT": {"HOT"},
    "ICE": {"ICE"},
    "UNKNOWN": set(),
}


class LoadError(Exception):
    pass


def read_csv(path, required):
    try:
        with open(path, encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            missing = set(required) - set(reader.fieldnames or [])
            if missing:
                raise LoadError(f"{path.name}: missing columns {sorted(missing)}")
            return list(reader)
    except OSError as exc:
        raise LoadError(f"Cannot read {path}: {type(exc).__name__}") from exc


def to_int(value, label, minimum=0):
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise LoadError(f"{label}: not an integer: {value!r}")
    if number < minimum:
        raise LoadError(f"{label}: below {minimum}: {number}")
    return number


def load_and_validate_csv(csv_dir):
    """Pure-Python validation of the CSV set. Returns (orders, details, report)."""
    orders = read_csv(csv_dir / "orders.csv", [
        "order_id", "order_datetime", "order_date", "order_hour", "gross_amount",
        "discount_amount", "net_sales",
    ])
    details = read_csv(csv_dir / "order_details.csv", [
        "order_detail_id", "order_id", "menu_id", "quantity", "temperature",
        "unit_price", "discount_amount", "line_total", "menu_name", "category",
    ])
    daily = read_csv(csv_dir / "daily_sales.csv", ["sales_date", "actual_sales", "order_count"])
    hourly = read_csv(csv_dir / "hourly_sales.csv", ["sales_date", "hour", "order_count", "sales_amount"])

    errors = []
    order_ids = [row["order_id"] for row in orders]
    if len(set(order_ids)) != len(order_ids):
        errors.append("duplicate order_id in orders.csv")
    if len({row["order_detail_id"] for row in details}) != len(details):
        errors.append("duplicate order_detail_id in order_details.csv")
    too_long = [oid for oid in order_ids if not oid or len(oid) > 32]
    if too_long:
        errors.append(f"{len(too_long)} order_id empty or longer than 32 chars")

    order_set = set(order_ids)
    line_sum = collections.Counter()
    line_count = collections.Counter()
    orphan = 0
    bad_line = 0
    nonzero_discount = 0
    bad_temp_value = 0
    for row in details:
        if row["order_id"] not in order_set:
            orphan += 1
            continue
        qty = to_int(row["quantity"], "quantity", 1)
        price = to_int(row["unit_price"], "unit_price", 0)
        total = to_int(row["line_total"], "line_total", 0)
        if qty * price != total:
            bad_line += 1
        if to_int(row["discount_amount"], "detail discount", 0) != 0:
            nonzero_discount += 1
        if row["temperature"] not in ("", "HOT", "ICE"):
            bad_temp_value += 1
        line_sum[row["order_id"]] += total
        line_count[row["order_id"]] += 1
    if orphan:
        errors.append(f"{orphan} detail rows reference a missing order")
    if bad_line:
        errors.append(f"{bad_line} detail rows where quantity*unit_price != line_total")
    if nonzero_discount:
        errors.append(f"{nonzero_discount} detail rows have a discount (not representable in SalesItem)")
    if bad_temp_value:
        errors.append(f"{bad_temp_value} detail rows have a temperature other than HOT/ICE/blank")

    no_lines = bad_total = bad_dt = nonzero_order_discount = 0
    day_sales = collections.Counter()
    day_orders = collections.Counter()
    hour_sales = collections.Counter()
    hour_orders = collections.Counter()
    for row in orders:
        net = to_int(row["net_sales"], "net_sales", 0)
        if line_count[row["order_id"]] == 0:
            no_lines += 1
        if line_sum[row["order_id"]] != net or to_int(row["gross_amount"], "gross_amount") != net:
            bad_total += 1
        if to_int(row["discount_amount"], "order discount", 0) != 0:
            nonzero_order_discount += 1
        try:
            moment = datetime.strptime(row["order_datetime"], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            bad_dt += 1
            continue
        if moment.date().isoformat() != row["order_date"] or moment.hour != int(row["order_hour"]):
            bad_dt += 1
        day_sales[row["order_date"]] += net
        day_orders[row["order_date"]] += 1
        hour_sales[(row["order_date"], moment.hour)] += net
        hour_orders[(row["order_date"], moment.hour)] += 1
    if no_lines:
        errors.append(f"{no_lines} orders have no detail rows")
    if bad_total:
        errors.append(f"{bad_total} orders where detail sum != net_sales (or gross != net)")
    if bad_dt:
        errors.append(f"{bad_dt} orders with unparsable/inconsistent order_datetime/date/hour")
    if nonzero_order_discount:
        errors.append(f"{nonzero_order_discount} orders have a discount (not representable)")

    daily_bad = sum(
        1 for row in daily
        if day_sales[row["sales_date"]] != int(row["actual_sales"])
        or day_orders[row["sales_date"]] != int(row["order_count"])
    )
    hourly_bad = sum(
        1 for row in hourly
        if hour_sales[(row["sales_date"], int(row["hour"]))] != int(row["sales_amount"])
        or hour_orders[(row["sales_date"], int(row["hour"]))] != int(row["order_count"])
    )
    if len(daily) != EXPECTED_DAYS or daily_bad:
        errors.append(f"daily_sales.csv cross-check failed (rows={len(daily)}, mismatched days={daily_bad})")
    if hourly_bad or len(hourly) != len(hour_orders):
        errors.append(f"hourly_sales.csv cross-check failed (mismatched={hourly_bad})")
    dates = sorted(day_orders)
    if dates and (dates[0] != PERIOD_START or dates[-1] != PERIOD_END):
        errors.append(f"order dates {dates[0]}..{dates[-1]} differ from {PERIOD_START}..{PERIOD_END}")

    report = {
        "orders": len(orders),
        "order_details": len(details),
        "total_amount": sum(day_sales.values()),
        "total_quantity": sum(int(row["quantity"]) for row in details),
        "days": len(day_orders),
        "period": (dates[0], dates[-1]) if dates else None,
        "menu_codes": sorted({row["menu_id"] for row in details}),
        "details_with_temperature": sum(1 for row in details if row["temperature"]),
        "details_without_temperature": sum(1 for row in details if not row["temperature"]),
        "daily_sales_csv_mismatch_days": daily_bad,
        "hourly_sales_csv_mismatches": hourly_bad,
        "day_orders": day_orders,
        "day_sales": day_sales,
    }
    if errors:
        raise LoadError("CSV validation failed:\n  - " + "\n  - ".join(errors))
    return orders, details, report


def setup_django():
    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "analysis.config.settings")
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))
    django.setup()


def migration_applied(using):
    from django.db import connections
    from django.db.migrations.recorder import MigrationRecorder

    recorder = MigrationRecorder(connections[using])
    return recorder.has_table() and REQUIRED_MIGRATION in set(recorder.applied_migrations())


def map_menus(details, store, using):
    """pos_code -> Menu, plus DB-vs-CSV consistency (name, price, temperature rules)."""
    from store.models import Menu

    menus = {m.pos_code: m for m in Menu.objects.using(using).filter(store_id=store.pk, pos_code__in=EXPECTED_MENUS)}
    codes = {row["menu_id"] for row in details}
    errors = []
    if codes - set(menus):
        errors.append(f"CSV menu codes without a DB menu: {sorted(codes - set(menus))}")
    if len(menus) != len(EXPECTED_MENUS):
        errors.append(f"expected 27 DB menus for the store, found {len(menus)}")
    seen = {}
    for row in details:
        seen.setdefault(row["menu_id"], row)
    for code, row in seen.items():
        menu = menus.get(code)
        if menu is None:
            continue
        if menu.name != row["menu_name"]:
            errors.append(f"{code}: name differs (db={menu.name!r}, csv={row['menu_name']!r})")
        if menu.category != row["category"]:
            errors.append(f"{code}: category differs")
    price_bad = temp_bad = 0
    for row in details:
        menu = menus.get(row["menu_id"])
        if menu is None:
            continue
        if int(row["unit_price"]) != menu.price:
            price_bad += 1
        if row["temperature"] and row["temperature"] not in ALLOWED_TEMPS.get(menu.serving_temperature, set()):
            temp_bad += 1
    if price_bad:
        errors.append(f"{price_bad} detail rows with unit_price != Menu.price")
    if temp_bad:
        errors.append(f"{temp_bad} detail rows with a temperature the menu does not allow")
    if errors:
        raise LoadError("Menu mapping failed:\n  - " + "\n  - ".join(errors))
    return menus


def get_store(name, using, lock):
    from store.models import Store

    stores = list(Store.objects.using(using).filter(name=name))
    if len(stores) != 1:
        raise LoadError(f"Expected exactly one Store named {name!r}, found {len(stores)}")
    if lock:
        return Store.objects.using(using).select_for_update().get(pk=stores[0].pk)
    return stores[0]


def existing_state(store, orders, using, column_exists):
    """Rows already in the DB that could collide with this load (read-only)."""
    from datetime import time
    from zoneinfo import ZoneInfo

    from django.utils import timezone

    from sales.models import Sales

    tz = ZoneInfo("Asia/Seoul")
    start = datetime.combine(datetime.fromisoformat(PERIOD_START), time.min, tzinfo=tz)
    end = datetime.combine(datetime.fromisoformat(PERIOD_END), time.max, tzinfo=tz)
    qs = Sales.objects.using(using).filter(store_id=store.pk)
    state = {
        "store_sales_total": qs.count(),
        "store_sales_in_period": qs.filter(sold_at__range=(start, end)).count(),
        "same_source_order_id": None,
    }
    if column_exists:
        wanted = [row["order_id"] for row in orders]
        found = 0
        for i in range(0, len(wanted), 5000):
            found += qs.filter(source_order_id__in=wanted[i:i + 5000]).count()
        state["same_source_order_id"] = found
    return state


def build_objects(orders, details, menus, store):
    from zoneinfo import ZoneInfo

    from sales.models import Sales, SalesItem

    tz = ZoneInfo("Asia/Seoul")
    sales_objs = [
        Sales(
            store=store,
            sold_at=datetime.strptime(row["order_datetime"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz),
            total_amount=int(row["net_sales"]),
            source_order_id=row["order_id"],
        )
        for row in orders
    ]
    return sales_objs


def verify_after_write(store, report, menus, details, using):
    """Runs inside the transaction; raises (=> rollback) on any mismatch."""
    from zoneinfo import ZoneInfo

    from django.db.models import Count, F, Sum
    from django.db.models.functions import TruncDate

    from sales.models import Sales, SalesItem

    sales_qs = Sales.objects.using(using).filter(store_id=store.pk, source_order_id__startswith="F1-")
    items_qs = SalesItem.objects.using(using).filter(sales__in=sales_qs)
    checks = {
        "sales_count": sales_qs.count() == report["orders"],
        "item_count": items_qs.count() == report["order_details"],
        "total_amount": (sales_qs.aggregate(t=Sum("total_amount"))["t"] or 0) == report["total_amount"],
        "total_quantity": (items_qs.aggregate(t=Sum("quantity"))["t"] or 0) == report["total_quantity"],
        "item_amount": (items_qs.aggregate(t=Sum(F("quantity") * F("unit_price")))["t"] or 0) == report["total_amount"],
    }
    mismatched = (
        sales_qs.annotate(line=Sum(F("items__quantity") * F("items__unit_price")))
        .exclude(line=F("total_amount"))
        .count()
    )
    checks["each_sale_equals_its_items"] = mismatched == 0
    daily = {
        row["d"].isoformat(): (row["n"], row["t"])
        for row in sales_qs.annotate(d=TruncDate("sold_at", tzinfo=ZoneInfo("Asia/Seoul")))
        .values("d").annotate(n=Count("id"), t=Sum("total_amount"))
    }
    checks["per_day_orders_and_sales"] = daily == {
        d: (report["day_orders"][d], report["day_sales"][d]) for d in report["day_orders"]
    }
    csv_qty = collections.Counter()
    for row in details:
        csv_qty[(row["menu_id"], row["temperature"] or None)] += int(row["quantity"])
    db_qty = collections.Counter()
    for row in items_qs.values("menu__pos_code", "serving_temperature").annotate(q=Sum("quantity")):
        db_qty[(row["menu__pos_code"], row["serving_temperature"])] += row["q"]
    checks["per_menu_temperature_quantity"] = csv_qty == db_qty
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise LoadError(f"Post-write verification failed ({failed}); transaction rolled back.")
    return checks


def run(args):
    setup_django()
    from django.db import DEFAULT_DB_ALIAS, transaction
    from django.db.models.query import QuerySet

    from sales.models import Sales, SalesItem

    using = DEFAULT_DB_ALIAS
    csv_dir = Path(args.csv_dir)
    orders, details, report = load_and_validate_csv(csv_dir)
    column_exists = migration_applied(using)

    print("== CSV validation: OK ==")
    print(f"orders={report['orders']:,} order_details={report['order_details']:,} days={report['days']} "
          f"period={report['period'][0]}..{report['period'][1]}")
    print(f"total_amount={report['total_amount']:,} total_quantity={report['total_quantity']:,}")
    print(f"details with temperature={report['details_with_temperature']:,}, "
          f"blank (dessert, stored as NULL)={report['details_without_temperature']:,}")
    print("excluded columns (not loaded): payment_method, data_type, dataset_version "
          "(+ order_hour/line_total/menu_name/category/discount_amount are derivable or unrepresentable)")

    if not args.apply:
        store = get_store(args.store_name, using, lock=False)
        menus = map_menus(details, store, using)
        state = existing_state(store, orders, using, column_exists)
        print("== DB checks (read-only) ==")
        print(f"store: id={store.pk} name={store.name!r}")
        print(f"menu mapping by pos_code: {len(menus)} menus -> pk "
              f"{', '.join(f'{c}={menus[c].pk}' for c in sorted(menus)[:3])} ... "
              f"{sorted(menus)[-1]}={menus[sorted(menus)[-1]].pk}; used by CSV: {len(report['menu_codes'])}")
        print(f"menu name/category/price/temperature-rule check: OK (all {report['order_details']:,} detail rows)")
        print(f"existing sales for store: total={state['store_sales_total']}, in period={state['store_sales_in_period']}")
        if column_exists:
            print(f"existing rows with the same source_order_id: {state['same_source_order_id']}")
        else:
            print(f"migration {REQUIRED_MIGRATION[0]}.{REQUIRED_MIGRATION[1]} is NOT applied: "
                  "source_order_id column absent, so duplicate-by-id check skipped "
                  "(--apply will refuse to run until it is applied)")
        blockers = []
        if state["store_sales_in_period"]:
            blockers.append("store already has sales in the dataset period")
        if state["same_source_order_id"]:
            blockers.append("some source_order_id values already exist")
        print("expected inserts: "
              f"Sales={report['orders']:,}, SalesItem={report['order_details']:,}; "
              f"updates=0, deletes=0")
        print("DRY RUN RESULT:", "BLOCKED - " + "; ".join(blockers) if blockers else
              ("READY after migration is applied" if not column_exists else "READY to --apply"))
        print("No rows were written.")
        return 1 if blockers else 0

    if not column_exists:
        raise LoadError(f"Migration {REQUIRED_MIGRATION[0]}.{REQUIRED_MIGRATION[1]} must be applied first.")
    with transaction.atomic(using=using):
        store = get_store(args.store_name, using, lock=True)
        menus = map_menus(details, store, using)
        state = existing_state(store, orders, using, True)
        if state["store_sales_in_period"] or state["same_source_order_id"]:
            raise LoadError(f"Refusing to load: existing data conflicts {state}")

        sales_objs = build_objects(orders, details, menus, store)
        Sales.objects.using(using).bulk_create(sales_objs, batch_size=SALES_BATCH)
        pk_by_source = {}
        wanted = [row["order_id"] for row in orders]
        for i in range(0, len(wanted), 5000):
            pk_by_source.update(
                Sales.objects.using(using)
                .filter(store_id=store.pk, source_order_id__in=wanted[i:i + 5000])
                .values_list("source_order_id", "pk")
            )
        if len(pk_by_source) != len(orders):
            raise LoadError("Could not read back every inserted Sales row; rolled back.")

        item_objs = [
            SalesItem(
                sales_id=pk_by_source[row["order_id"]],
                menu_id=menus[row["menu_id"]].pk,
                quantity=int(row["quantity"]),
                unit_price=int(row["unit_price"]),
                serving_temperature=row["temperature"] or None,
            )
            for row in details
        ]
        # Plain QuerySet.bulk_create: rows were fully validated above (see module docstring).
        QuerySet.bulk_create(SalesItem.objects.using(using).all(), item_objs, batch_size=ITEM_BATCH)
        checks = verify_after_write(store, report, menus, details, using)

    print("== COMMITTED ==")
    print(f"Sales inserted={len(sales_objs):,}, SalesItem inserted={len(item_objs):,}")
    for name, ok in checks.items():
        print(f"  verify {name}: {'OK' if ok else 'FAIL'}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Load sales_dummy_v1_final into Sales/SalesItem (dry run by default).")
    parser.add_argument("--apply", action="store_true", help="Insert rows in one atomic transaction.")
    parser.add_argument("--csv-dir", default=str(DEFAULT_CSV_DIR))
    parser.add_argument("--store-name", default=DEFAULT_STORE_NAME)
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        sys.exit(run(args))
    except LoadError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
