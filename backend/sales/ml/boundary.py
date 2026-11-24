"""Data boundary between real operating data and synthetic scenario data.

The DB has no origin column on Sales, and every sales row is synthetic dummy data
(order ids F1-... and N26-...). Rows dated after the last COMPLETE local day
(yesterday, KST) are future scenario rows (e.g. 2026-11-23..30): they are never
treated as actuals, never used to train operating models, and never used to
back-test operating forecasts. Experiments that want them must opt in explicitly
(allow_future=True) and must never write operating artifacts.
"""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
SYNTHETIC_ORDER_PREFIXES = ("F1-", "N26-")
SALES_DATA_TYPE = "synthetic_dummy"
SALES_DATA_NOTE = "실제 POS가 아닌 합성 데이터로 학습·검증한 결과입니다. 실제 매장 예측 정확도가 아닙니다."


def local_today(now=None) -> date:
    now = now or datetime.now(KST)
    if now.tzinfo is None:
        now = now.replace(tzinfo=KST)
    return now.astimezone(KST).date()


def last_complete_day(now=None) -> date:
    """Yesterday in KST: today is still in progress, so it has no 'actual' yet."""
    return local_today(now) - timedelta(days=1)


def default_as_of(now=None) -> date:
    return last_complete_day(now)


def clamp_as_of(as_of=None, now=None, allow_future=False) -> date:
    """as_of defaults to the last complete KST day and can never exceed it unless allow_future."""
    limit = last_complete_day(now)
    if as_of is None:
        return limit
    if hasattr(as_of, "date") and not isinstance(as_of, date):
        as_of = as_of.date()
    if isinstance(as_of, datetime):
        as_of = as_of.date()
    return as_of if allow_future else min(as_of, limit)


def is_synthetic_order_id(source_order_id) -> bool:
    return bool(source_order_id) and str(source_order_id).startswith(SYNTHETIC_ORDER_PREFIXES)
