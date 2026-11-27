from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from sales.models import Sales, SalesItem
from sales.services import analytics, forecasting, queries
from store.models import Menu, Store

KST = ZoneInfo("Asia/Seoul")


def kst(y, m, d, hh=12, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=KST)


class AnalyticsPureTests(SimpleTestCase):
    def test_average_ticket_rounds_half_up_and_handles_zero_orders(self):
        self.assertEqual(analytics.average_ticket(100, 3), 33)
        self.assertEqual(analytics.average_ticket(101, 2), 51)  # 50.5 -> 51
        self.assertIsNone(analytics.average_ticket(0, 0))

    def test_rollup_week_month_and_partial_flags(self):
        daily = {date(2025, 1, 5): {"sales": 100, "orders": 1},   # Sunday, week of Dec 30
                 date(2025, 1, 6): {"sales": 200, "orders": 2},   # Monday, new week
                 date(2025, 2, 1): {"sales": 300, "orders": 3}}
        weeks = analytics.rollup(daily, "week", date(2025, 1, 1), date(2025, 2, 28))
        self.assertEqual([w["period_start"] for w in weeks], ["2024-12-30", "2025-01-06", "2025-01-27"])
        self.assertTrue(weeks[0]["is_partial"])  # starts before the requested window
        months = analytics.rollup(daily, "month", date(2025, 1, 1), date(2025, 2, 28))
        self.assertEqual([(m["period_start"], m["sales"], m["order_count"], m["average_ticket"]) for m in months],
                         [("2025-01-01", 300, 3, 100), ("2025-02-01", 300, 3, 100)])
        self.assertFalse(months[0]["is_partial"])

    def test_compare_blocks_and_missing_base(self):
        daily = {date(2025, 3, 10): {"sales": 150, "orders": 3},
                 date(2025, 3, 9): {"sales": 100, "orders": 2},
                 date(2025, 3, 3): {"sales": 300, "orders": 4},
                 date(2025, 2, 10): {"sales": 50, "orders": 1}}
        out = analytics.compare(daily, date(2025, 3, 10))
        dod = out["day_vs_previous_day"]
        self.assertEqual(dod["sales"], {"current": 150, "base": 100, "change": 50, "change_pct": 50.0})
        wow = out["day_vs_same_weekday_last_week"]  # 3/3
        self.assertEqual(wow["sales"]["change"], -150)
        self.assertEqual(wow["sales"]["change_pct"], -50.0)
        mtd = out["month_to_date_vs_previous_month"]
        self.assertEqual(mtd["current_period"], ["2025-03-01", "2025-03-10"])
        self.assertEqual(mtd["base_period"], ["2025-02-01", "2025-02-10"])
        self.assertEqual(mtd["sales"]["current"], 550)
        self.assertEqual(mtd["sales"]["base"], 50)
        empty = analytics.compare({date(2025, 3, 10): {"sales": 10, "orders": 1}}, date(2025, 3, 10))
        self.assertIsNone(empty["day_vs_previous_day"]["sales"]["change_pct"])
        self.assertIn("데이터가 없어", empty["day_vs_previous_day"]["note"])

    def test_month_to_date_clamps_to_short_previous_month(self):
        daily = {date(2025, 2, 28): {"sales": 10, "orders": 1}, date(2025, 3, 31): {"sales": 20, "orders": 1}}
        out = analytics.compare(daily, date(2025, 3, 31))["month_to_date_vs_previous_month"]
        self.assertEqual(out["base_period"], ["2025-02-01", "2025-02-28"])
        self.assertEqual(out["sales"]["base"], 10)

    def test_weekday_pattern_averages_only_days_with_data(self):
        daily = {date(2025, 1, 6): {"sales": 100, "orders": 1}, date(2025, 1, 13): {"sales": 300, "orders": 3}}
        mon = analytics.weekday_pattern(daily)[0]
        self.assertEqual((mon["days_with_data"], mon["avg_daily_sales"], mon["average_ticket"]), (2, 200, 100))
        self.assertIsNone(analytics.weekday_pattern(daily)[1]["avg_daily_sales"])


def weekday_series(days, weekday_levels, level=1.0, start=date(2025, 1, 1)):
    return {start + timedelta(days=i): weekday_levels[(start + timedelta(days=i)).weekday()] * level
            for i in range(days)}


class ForecastPureTests(SimpleTestCase):
    LEVELS = [100, 100, 100, 100, 150, 200, 50]  # Mon..Sun

    def test_pure_weekday_pattern_is_recovered_exactly(self):
        series = weekday_series(100, self.LEVELS)
        target = date(2025, 1, 1) + timedelta(days=100)
        self.assertAlmostEqual(forecasting.predict_value(series, target), self.LEVELS[target.weekday()], places=6)

    def test_level_shift_is_tracked(self):
        series = weekday_series(100, self.LEVELS)
        shifted = {d: (v * 1.2 if d >= date(2025, 1, 1) + timedelta(days=80) else v) for d, v in series.items()}
        target = date(2025, 1, 1) + timedelta(days=100)
        pred = forecasting.predict_value(shifted, target)
        self.assertGreater(pred, self.LEVELS[target.weekday()] * 1.05)

    def test_no_leakage_from_target_day_or_later(self):
        series = weekday_series(100, self.LEVELS)
        target = date(2025, 1, 1) + timedelta(days=100)
        base = forecasting.predict_value(series, target)
        tampered = dict(series)
        for k in range(0, 20):
            tampered[target + timedelta(days=k)] = 9_999_999.0  # target day and the future
        self.assertEqual(forecasting.predict_value(tampered, target), base)

    def test_forecast_next_day_ignores_rows_after_as_of(self):
        daily = {d: {"sales": int(v * 100), "orders": int(v)} for d, v in weekday_series(130, self.LEVELS).items()}
        as_of = date(2025, 1, 1) + timedelta(days=119)
        clean = forecasting.forecast_next_day({d: r for d, r in daily.items() if d <= as_of}, as_of)
        full = forecasting.forecast_next_day(daily, as_of)  # contains days after as_of
        self.assertEqual(clean, full)
        self.assertEqual(clean["target_date"], (as_of + timedelta(days=1)).isoformat())

    def test_insufficient_history(self):
        with self.assertRaises(forecasting.InsufficientHistory):
            forecasting.predict_value(weekday_series(20, self.LEVELS), date(2025, 1, 21))
        stale = weekday_series(60, self.LEVELS)  # data ends 2025-03-01, target far away -> no recent days
        with self.assertRaises(forecasting.InsufficientHistory):
            forecasting.predict_value(stale, date(2025, 4, 20))

    def test_menu_quantities_split_total_by_recent_share(self):
        start = date(2025, 1, 1)
        a = {start + timedelta(days=i): 6 for i in range(100)}
        b = {start + timedelta(days=i): 2 for i in range(100)}
        as_of = start + timedelta(days=99)
        out = forecasting.forecast_menu_quantities({1: a, 2: b}, {1: "A", 2: "B"}, as_of)
        self.assertEqual([m["menu_id"] for m in out["menus"]], [1, 2])
        self.assertAlmostEqual(out["menus"][0]["expected_quantity"], 6.0, places=2)
        self.assertAlmostEqual(out["menus"][1]["expected_quantity"], 2.0, places=2)
        self.assertAlmostEqual(out["total_expected_quantity"], 8.0, places=2)
        self.assertEqual(out["backtest"]["pooled_menu_wape_pct"], 0.0)


class SalesApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user(username="owner")
        cls.other = User.objects.create_user(username="other")
        cls.staff = User.objects.create_user(username="staff", is_staff=True)
        cls.store = Store.objects.create(owner=cls.owner, name="s")
        cls.empty_store = Store.objects.create(owner=cls.owner, name="empty")
        cls.menu_a = Menu.objects.create(store=cls.store, name="A", category="c", price=1000)
        cls.menu_b = Menu.objects.create(store=cls.store, name="B", category="c", price=2000)
        start = date(2025, 1, 1)
        for i in range(120):
            d = start + timedelta(days=i)
            n = 3 + (d.weekday() % 3)
            for j in range(n):
                sale = Sales.objects.create(store=cls.store, sold_at=kst(d.year, d.month, d.day, 9 + j),
                                            total_amount=1000 + 2000)
                SalesItem.objects.create(sales=sale, menu=cls.menu_a, quantity=1, unit_price=1000)
                SalesItem.objects.create(sales=sale, menu=cls.menu_b, quantity=1, unit_price=2000)
        # KST boundary: 23:30 KST on 2025-05-01 is still May 1 (it is 14:30 UTC), 00:10 KST is May 2.
        late = Sales.objects.create(store=cls.store, sold_at=kst(2025, 5, 1, 23, 30), total_amount=500)
        early = Sales.objects.create(store=cls.store, sold_at=kst(2025, 5, 2, 0, 10), total_amount=700)
        cls.late_id, cls.early_id = late.pk, early.pk

    def client_for(self, user):
        client = APIClient()
        if user is not None:
            client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.get_or_create(user=user)[0].key}")
        return client

    def url(self, name, store=None):
        return reverse(f"sales:{name}", args=[(store or self.store).pk])

    def test_requires_authentication_and_hides_other_owners_stores(self):
        self.assertEqual(self.client_for(None).get(self.url("analysis-sales")).status_code, 401)
        self.assertEqual(self.client_for(self.other).get(self.url("analysis-sales")).status_code, 404)
        self.assertEqual(self.client_for(self.staff).get(self.url("analysis-sales")).status_code, 200)
        self.assertEqual(self.client_for(self.owner).get(self.url("analysis-sales")).status_code, 200)

    def test_daily_rollup_uses_local_dates_and_matches_totals(self):
        res = self.client_for(self.owner).get(self.url("analysis-sales"),
                                               {"granularity": "day", "start": "2025-05-01", "end": "2025-05-02"})
        self.assertEqual(res.status_code, 200)
        by_day = {r["period_start"]: r for r in res.data["series"]}
        # Only the two boundary orders exist on these dates (regular fixtures end 2025-04-30).
        self.assertEqual((by_day["2025-05-01"]["order_count"], by_day["2025-05-01"]["sales"]), (1, 500))
        self.assertEqual((by_day["2025-05-02"]["order_count"], by_day["2025-05-02"]["sales"]), (1, 700))
        self.assertEqual(res.data["summary"]["sales"], sum(r["sales"] for r in res.data["series"]))

    def test_monthly_total_equals_order_table_total(self):
        res = self.client_for(self.owner).get(self.url("analysis-sales"),
                                               {"granularity": "month", "start": "2025-01-01", "end": "2025-04-30"})
        expected = sum(Sales.objects.filter(store=self.store, sold_at__lt=kst(2025, 5, 1, 0, 0))
                       .values_list("total_amount", flat=True))
        self.assertEqual(res.data["summary"]["sales"], expected)
        self.assertEqual(len(res.data["series"]), 4)

    def test_patterns_weekday_and_hourly(self):
        res = self.client_for(self.owner).get(self.url("analysis-patterns"),
                                               {"start": "2025-01-01", "end": "2025-04-30"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["weekday"]), 7)
        self.assertEqual(sum(w["total_orders"] for w in res.data["weekday"]),
                         sum(h["total_orders"] for h in res.data["hourly"]))
        self.assertAlmostEqual(sum(h["sales_share_pct"] for h in res.data["hourly"]), 100, delta=0.1)
        self.assertEqual({h["hour"] for h in res.data["hourly"]}, {9, 10, 11, 12, 13})

    def test_comparison_defaults_to_latest_date(self):
        res = self.client_for(self.owner).get(self.url("analysis-comparison"))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["as_of"], "2025-05-02")
        self.assertEqual(self.client_for(self.owner).get(self.url("analysis-comparison", self.empty_store)).status_code, 404)

    def test_validation_errors(self):
        c = self.client_for(self.owner)
        self.assertEqual(c.get(self.url("analysis-sales"), {"start": "2025-02-01", "end": "2025-01-01"}).status_code, 400)
        self.assertEqual(c.get(self.url("analysis-sales"), {"granularity": "year"}).status_code, 400)
        self.assertEqual(c.get(self.url("analysis-sales"), {"start": "2000-01-01", "end": "2025-01-01"}).status_code, 400)
        self.assertEqual(c.get(self.url("forecast-next-day"), {"as_of": "not-a-date"}).status_code, 400)

    def test_forecasts_and_leakage_guard(self):
        c = self.client_for(self.owner)
        res = c.get(self.url("forecast-next-day"), {"as_of": "2025-04-15"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["target_date"], "2025-04-16")
        self.assertGreater(res.data["predicted_sales"], 0)
        # later days exist in the DB (up to 2025-05-02); they must not change an earlier as_of forecast
        Sales.objects.create(store=self.store, sold_at=kst(2025, 4, 16, 10), total_amount=9_000_000)
        again = c.get(self.url("forecast-next-day"), {"as_of": "2025-04-15"})
        self.assertEqual(res.data, again.data)
        menu = c.get(self.url("forecast-menu-quantity"), {"as_of": "2025-04-15"})
        self.assertEqual(menu.status_code, 200)
        self.assertEqual({m["menu_name"] for m in menu.data["menus"]}, {"A", "B"})

    def test_forecast_needs_enough_history(self):
        c = self.client_for(self.owner)
        self.assertEqual(c.get(self.url("forecast-next-day"), {"as_of": "2025-01-10"}).status_code, 422)
        self.assertEqual(c.get(self.url("forecast-next-day"), {}, **{}).status_code, 200)
        self.assertEqual(c.get(self.url("forecast-next-day", self.empty_store)).status_code, 422)

    def test_queries_are_read_only(self):
        before = (Sales.objects.count(), SalesItem.objects.count())
        queries.daily_totals(self.store)
        queries.hourly_totals(self.store)
        queries.menu_daily_quantities(self.store)
        self.assertEqual(before, (Sales.objects.count(), SalesItem.objects.count()))
