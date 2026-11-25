"""Tests for the ShopImpact engine, badges, turtle pen and API.

Run with:  python -m unittest discover tests
"""

import os
import tempfile

os.environ.setdefault("SHOPIMPACT_LIVE_RATES", "0")
os.environ.setdefault("SHOPIMPACT_LOGOS", "0")  # no network in tests  # tests never call the rates API
import unittest
from datetime import date

from shopimpact import drawings, sample_data
from shopimpact.badges import evaluate_badges
from shopimpact.brands import BRANDS, brand_card, greener_names, is_ethical_brand, lookup
from shopimpact.catalog import CURRENCIES, PRODUCT_TYPES, tier_for
from shopimpact.logos import monogram_svg
from shopimpact.world import COUNTRIES, COUNTRY_BY_CODE, POPULAR
from shopimpact.engine import (calculate_impact, eco_score, enrich, grade_for, monthly_summary,
                               purchases_in_month, shift_month, swap_details, to_gbp)
from shopimpact.turtle_svg import SvgTurtle

SETTINGS = {"currency": "GBP", "co2_budget": 200, "spend_budget": 600}


def purchase(ptype, price, day=5, brand="", month="2026-11", pid=1, swapped_from=None):
    return {"id": pid, "product_type": ptype, "brand": brand, "price": price, "currency": "GBP",
            "date": f"{month}-{day:02d}", "note": "", "swapped_from": swapped_from}


class ImpactTests(unittest.TestCase):
    def test_price_times_multiplier(self):
        self.assertEqual(calculate_impact("fast_fashion", 40), 36.0)
        self.assertEqual(calculate_impact("second_hand_clothing", 40), 3.2)

    def test_currency_is_converted_before_multiplying(self):
        self.assertAlmostEqual(to_gbp(100, "USD"), 100 * CURRENCIES["USD"]["to_gbp"])
        self.assertLess(calculate_impact("beef_lamb", 1000, "INR"), calculate_impact("beef_lamb", 1000, "GBP"))

    def test_unknown_type_or_negative_price_is_zero(self):
        self.assertEqual(calculate_impact("spaceship", 10), 0.0)
        self.assertEqual(calculate_impact("fast_fashion", -5), 0.0)

    def test_tiers(self):
        self.assertEqual(tier_for(0.08), "low")
        self.assertEqual(tier_for(0.6), "medium")
        self.assertEqual(tier_for(2.6), "high")

    def test_every_swap_is_greener(self):
        for type_id, info in PRODUCT_TYPES.items():
            if info["swap_to"]:
                self.assertIn(info["swap_to"], PRODUCT_TYPES, type_id)
                self.assertLess(PRODUCT_TYPES[info["swap_to"]]["multiplier"], info["multiplier"], type_id)
            self.assertTrue(greener_names(type_id), f"{type_id} needs greener options")

    def test_swap_saving(self):
        swap = swap_details("beef_lamb", 20)
        self.assertEqual(swap["to"], "plant_protein")
        self.assertEqual(swap["saving"], 47.0)
        self.assertIsNone(swap_details("train", 20))

    def test_eco_score_and_grades(self):
        self.assertIsNone(eco_score(0, 0))
        self.assertEqual(eco_score(0, 100), 100)
        self.assertEqual(eco_score(120, 100), 0)
        self.assertEqual(grade_for(85)["letter"], "A")
        self.assertEqual(grade_for(10)["letter"], "E")

    def test_ethical_brand_matching(self):
        self.assertTrue(is_ethical_brand("Veja"))
        self.assertTrue(is_ethical_brand("patagonia worn wear jacket"))
        self.assertFalse(is_ethical_brand(""))
        self.assertFalse(is_ethical_brand("Generic Mart"))

    def test_shift_month(self):
        self.assertEqual(shift_month("2026-01", -1), "2025-12")
        self.assertEqual(shift_month("2026-12", 1), "2027-01")


class BrandTests(unittest.TestCase):
    def test_every_brand_points_at_real_product_types(self):
        for brand in BRANDS:
            self.assertTrue(brand["types"], brand["name"])
            for type_id in brand["types"]:
                self.assertIn(type_id, PRODUCT_TYPES, brand["name"])

    def test_names_and_domains_are_unique(self):
        names = [b["name"].lower() for b in BRANDS]
        domains = [b["domain"] for b in BRANDS]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(len(domains), len(set(domains)))

    def test_four_countries_are_well_covered(self):
        for country in ("IN", "SG", "CH", "US"):
            self.assertGreater(sum(country in b["countries"] for b in BRANDS), 100, country)

    def test_every_product_type_has_a_brand(self):
        for type_id in PRODUCT_TYPES:
            self.assertTrue(any(type_id in b["types"] for b in BRANDS), type_id)

    def test_lookup_and_logo_card(self):
        self.assertEqual(lookup("zudio")["name"], "Zudio")
        self.assertEqual(lookup("Veja trainers")["name"], "Veja")
        self.assertIsNone(lookup("Corner shop"))
        self.assertEqual(brand_card("Migros")["logo"], "/api/logo/migros.ch")

    def test_monogram_fallback(self):
        svg = monogram_svg("Bare Necessities").decode()
        self.assertIn(">BN<", svg)

    def test_every_currency_has_a_slider(self):
        for code, info in CURRENCIES.items():
            maximum, step = info["slider"]
            self.assertGreater(maximum, step, code)


class WorldTests(unittest.TestCase):
    def test_every_country_has_a_known_currency(self):
        self.assertGreater(len(COUNTRIES), 220)
        for country in COUNTRIES:
            self.assertIn(country["currency"], CURRENCIES, country["name"])
        for code in POPULAR:
            self.assertIn(code, COUNTRY_BY_CODE)

    def test_small_unit_currencies_get_sensible_price_tags(self):
        maximum, step = CURRENCIES["IDR"]["slider"]
        self.assertGreaterEqual(step, 100)                       # no tuck per single rupiah
        self.assertAlmostEqual(maximum * CURRENCIES["IDR"]["to_gbp"], 1000, delta=1000)
        self.assertEqual(CURRENCIES["GBP"]["slider"], (1000, 1))  # £0–1,000, every pound

    def test_live_rates_update_in_place(self):
        from shopimpact import catalog
        before = CURRENCIES["INR"]["to_gbp"]
        catalog.update_rates({"GBP": 0.75, "INR": 90.0})
        self.assertAlmostEqual(CURRENCIES["INR"]["to_gbp"], 0.75 / 90.0)
        catalog.update_rates({})  # back to the built-in table
        self.assertAlmostEqual(CURRENCIES["INR"]["to_gbp"], before)


class SummaryTests(unittest.TestCase):
    def setUp(self):
        raw = [purchase("fast_fashion", 40, 2, pid=1), purchase("second_hand_clothing", 20, 3, pid=2),
               purchase("beef_lamb", 10, 10, pid=3), purchase("train", 30, 10, pid=4)]
        self.items = [enrich(p) for p in raw]
        self.summary = monthly_summary(self.items, "2026-11", SETTINGS)

    def test_totals(self):
        self.assertEqual(self.summary["count"], 4)
        self.assertEqual(self.summary["spend"], 100.0)
        self.assertAlmostEqual(self.summary["co2"], 36 + 1.6 + 26 + 3.6, places=2)

    def test_daily_series_is_cumulative(self):
        daily = self.summary["daily"]
        self.assertEqual(len(daily), 30)
        self.assertEqual(daily[-1]["cum"], self.summary["co2"])
        self.assertEqual(daily[9]["count"], 2)

    def test_groups_sorted_by_footprint(self):
        names = [g["id"] for g in self.summary["groups"]]
        self.assertEqual(names[0], "fashion")
        self.assertAlmostEqual(sum(g["share"] for g in self.summary["groups"]), 1.0, places=2)

    def test_tier_counts(self):
        self.assertEqual(self.summary["tiers"]["high"]["count"], 2)
        self.assertEqual(self.summary["tiers"]["low"]["count"], 2)


MID_MONTH = date(2026, 11, 15)    # November still in progress
AFTER_MONTH = date(2026, 12, 3)   # November finished


class BadgeTests(unittest.TestCase):
    def evaluate(self, raw, prev_raw=None, today=AFTER_MONTH, settings=SETTINGS):
        items = [enrich(p) for p in raw]
        summary = monthly_summary(items, "2026-11", settings, today)
        prev = None
        if prev_raw:
            prev_items = [enrich(p) for p in prev_raw]
            prev = monthly_summary(prev_items, "2026-10", settings, today)
        return {b["id"]: b for b in evaluate_badges(items, items + (prev_raw and [enrich(p) for p in prev_raw] or []),
                                                    summary, prev)}

    def test_green_streak_and_second_life(self):
        raw = [purchase("second_hand_clothing", 10, d, pid=d) for d in range(1, 6)]
        badges = self.evaluate(raw)
        self.assertTrue(badges["green_streak"]["earned"])
        self.assertTrue(badges["second_life"]["earned"])
        self.assertTrue(badges["eco_saver"]["earned"])
        self.assertTrue(badges["low_impact"]["earned"])

    def test_month_badges_lock_in_only_when_the_month_ends(self):
        raw = [purchase("second_hand_clothing", 10, d, pid=d) for d in range(1, 6)]
        during = self.evaluate(raw, today=MID_MONTH)["eco_saver"]
        self.assertFalse(during["earned"])
        self.assertTrue(during["on_track"])
        self.assertTrue(self.evaluate(raw, today=AFTER_MONTH)["eco_saver"]["earned"])

    def test_penny_purchases_cannot_farm_badges(self):
        raw = [purchase("second_hand_clothing", 0.01, d, pid=d) for d in range(1, 6)]
        earned = {k for k, b in self.evaluate(raw).items() if b["earned"]}
        self.assertEqual(earned, {"first_step"})

    def test_first_step_is_a_lifetime_badge(self):
        raw = [purchase("train", 10, 5, pid=1)]
        items = [enrich(p) for p in raw]
        empty_later = monthly_summary([], "2027-01", SETTINGS, date(2027, 1, 20))
        empty_earlier = monthly_summary([], "2026-09", SETTINGS, date(2027, 1, 20))
        later = {b["id"]: b for b in evaluate_badges([], items, empty_later, None)}["first_step"]
        earlier = {b["id"]: b for b in evaluate_badges([], items, empty_earlier, None)}["first_step"]
        self.assertTrue(later["earned"])
        self.assertIn("Lifetime", later["hint"])
        self.assertFalse(earlier["earned"])

    def test_heavy_month_earns_no_eco_badges(self):
        raw = [purchase("flight", 200, d, pid=d) for d in range(1, 6)]
        badges = self.evaluate(raw)
        self.assertFalse(badges["eco_saver"]["earned"])
        self.assertFalse(badges["low_impact"]["earned"])
        self.assertLess(badges["eco_saver"]["progress"], 1)

    def test_ethical_brand_and_swap_master(self):
        raw = [purchase("second_hand_clothing", 10, 1, "Vinted", pid=1, swapped_from="fast_fashion"),
               purchase("plant_dairy", 5, 2, "Oatly", pid=2, swapped_from="dairy"),
               purchase("train", 30, 3, "", pid=3, swapped_from="flight")]
        badges = self.evaluate(raw)
        self.assertTrue(badges["ethical_ally"]["earned"])
        self.assertTrue(badges["swap_master"]["earned"])

    def test_carbon_cutter_needs_a_20_percent_drop(self):
        prev = [purchase("flight", 100, 3, month="2026-10", pid=9)]
        now = [purchase("train", 20, d, pid=d) for d in range(1, 6)]
        self.assertTrue(self.evaluate(now, prev)["carbon_cutter"]["earned"])
        self.assertFalse(self.evaluate(now)["carbon_cutter"]["earned"])

    def test_carbon_cutter_compares_like_for_like(self):
        # Last month's big flight was on the 28th; by the 15th it had only 12 kg.
        prev = [purchase("train", 100, 2, month="2026-10", pid=8), purchase("flight", 300, 28, month="2026-10", pid=9)]
        now = [purchase("train", 30, d, pid=d) for d in range(1, 6)]   # 18 kg by the 15th
        mid = self.evaluate(now, prev, today=MID_MONTH)["carbon_cutter"]
        self.assertFalse(mid["earned"])
        self.assertFalse(mid["on_track"])   # 18 kg is not 20% below 12 kg at the same point


class EcoScoreTests(unittest.TestCase):
    def test_spending_more_never_hides_an_over_budget_month(self):
        over = [enrich(purchase("refurbished_electronics", 2500, 2, pid=1))]   # 375 kg vs 200 budget
        summary = monthly_summary(over, "2026-11", SETTINGS, AFTER_MONTH)
        self.assertLess(summary["score"], 50)
        self.assertNotEqual(summary["grade"]["letter"], "A")

    def test_buying_more_low_impact_cannot_rescue_a_huge_footprint(self):
        huge = [enrich(purchase("train", 1_000_000, 2, pid=1))]
        self.assertLess(monthly_summary(huge, "2026-11", SETTINGS, AFTER_MONTH)["score"], 5)

    def test_whatif_comes_from_python(self):
        items = [enrich(purchase("beef_lamb", 20, 2, pid=1))]
        summary = monthly_summary(items, "2026-11", SETTINGS, AFTER_MONTH)
        full = summary["whatif"][-1]
        self.assertEqual(full["pct"], 100)
        self.assertAlmostEqual(full["saved"], 47.0)
        self.assertAlmostEqual(full["after"], 5.0)


class ValidationTests(unittest.TestCase):
    TODAY = date(2026, 11, 24)

    def check(self, **data):
        from shopimpact.service import ValidationError, validate_purchase
        base = {"product_type": "train", "price": 10, "date": "2026-11-20"}
        base.update(data)
        try:
            validate_purchase(base, {"currency": "GBP"}, self.TODAY)
            return None
        except ValidationError as err:
            return str(err)

    def test_numbers(self):
        for bad in ("NaN", "nan", "Infinity", "-inf", "abc", "", None, 0, -5):
            self.assertIsNotNone(self.check(price=bad), bad)
        self.assertIsNone(self.check(price="12.5"))

    def test_strict_dates(self):
        for bad in ("2026-W48-2", "20261124", "2026-02-30", "26-11-20", "2026-11-20T10:00", "1999-12-31"):
            self.assertIsNotNone(self.check(date=bad), bad)

    def test_future_dates_are_refused(self):
        self.assertIsNotNone(self.check(date="2026-12-05"))
        self.assertIsNone(self.check(date="2026-11-25"))   # one day of time-zone slack

    def test_long_text_is_refused_not_cut(self):
        self.assertIsNotNone(self.check(brand="B" * 61))
        self.assertIsNotNone(self.check(note="N" * 121))

    def test_frozen_values(self):
        from shopimpact.service import validate_purchase
        clean = validate_purchase({"product_type": "fast_fashion", "price": 40}, {"currency": "GBP"}, self.TODAY)
        self.assertEqual(clean["price_gbp"], 40.0)
        self.assertEqual(clean["co2"], 36.0)

    def test_csv_cells_are_defused(self):
        from shopimpact.service import csv_safe
        self.assertEqual(csv_safe('=HYPERLINK("x")'), '\'=HYPERLINK("x")')
        self.assertEqual(csv_safe("Zara"), "Zara")

    def test_backup_and_restore_round_trip(self):
        from shopimpact.service import Service, ValidationError
        from shopimpact.store import Store
        with tempfile.TemporaryDirectory() as tmp:
            service = Service(Store(os.path.join(tmp, "backup.db")))
            service.update_settings("a" * 32, {"country": "IN"}, self.TODAY)
            service.add("a" * 32, {"product_type": "fast_fashion", "price": 2000, "date": "2026-11-20",
                                    "brand": "Zudio"}, self.TODAY)
            backup = service.backup("a" * 32)
            restored = service.restore_backup("b" * 32, backup, self.TODAY)
            self.assertEqual(restored, 1)
            original = service.store.purchases("a" * 32)[0]
            copy = service.store.purchases("b" * 32)[0]
            self.assertEqual((copy["brand"], copy["price"], copy["co2"]), (original["brand"], original["price"], original["co2"]))
            self.assertEqual(service.store.settings("b" * 32)["currency"], "INR")
            with self.assertRaises(ValidationError):
                service.restore_backup("c" * 32, "not a backup", self.TODAY)


class TurtleTests(unittest.TestCase):
    def test_square_path(self):
        t = SvgTurtle()
        for _ in range(4):
            t.forward(100)
            t.left(90)
        self.assertAlmostEqual(t.xcor(), 0, places=6)
        self.assertAlmostEqual(t.ycor(), 0, places=6)
        self.assertEqual(t.to_svg().count('class="t-stroke"'), 1)

    def test_circle_returns_home(self):
        t = SvgTurtle()
        t.circle(50)
        self.assertAlmostEqual(t.xcor(), 0, places=4)
        self.assertAlmostEqual(t.ycor(), 0, places=4)
        self.assertAlmostEqual(t.heading() % 360, 0, places=4)

    def test_fill_is_revealed_after_its_outline(self):
        t = SvgTurtle()
        t.begin_fill()
        t.circle(20)
        t.end_fill()
        svg = t.to_svg()
        self.assertIn('class="t-fill"', svg)
        self.assertIn('data-at="1"', svg)

    def test_all_drawings_render(self):
        for kind in ("sprig", "steps", "deep_step"):
            self.assertTrue(drawings.render(kind).startswith("<svg"))
        for emblem in drawings.EMBLEMS:
            self.assertIn("t-fill", drawings.render("badge", emblem=emblem))
        self.assertIn("t-dot", drawings.render("tree", score=80, low=5, medium=2, high=1))


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ["SHOPIMPACT_DB"] = os.path.join(cls.tmp.name, "test.db")
        import importlib
        import web_app as app_module
        importlib.reload(app_module)
        cls.client = app_module.app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_add_purchase_returns_reward_and_state(self):
        res = self.client.post("/api/purchases", json={"product_type": "fast_fashion", "price": 40, "brand": "Zara"})
        data = res.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["purchase"]["co2"], 36.0)
        self.assertEqual(data["reward"]["kind"], "deep_step")
        self.assertTrue(data["tip"])
        self.assertGreaterEqual(data["state"]["summary"]["count"], 1)

    def test_validation_messages(self):
        bad = self.client.post("/api/purchases", json={"product_type": "nope", "price": 4}).get_json()
        self.assertFalse(bad["ok"])
        bad = self.client.post("/api/purchases", json={"product_type": "train", "price": "abc"}).get_json()
        self.assertIn("number", bad["error"])

    def test_swap_and_delete(self):
        added = self.client.post("/api/purchases", json={"product_type": "beef_lamb", "price": 10}).get_json()
        pid = added["purchase"]["id"]
        swapped = self.client.post(f"/api/purchases/{pid}/swap", json={}).get_json()
        self.assertEqual(swapped["purchase"]["product_type"], "plant_protein")
        self.assertEqual(swapped["purchase"]["swap_saved"], 23.5)
        deleted = self.client.delete(f"/api/purchases/{pid}").get_json()
        self.assertTrue(deleted["ok"])

    def test_logo_endpoint_only_serves_known_brands(self):
        self.assertEqual(self.client.get("/api/logo/example.org").status_code, 404)

    def test_catalog_lists_brands_without_countries(self):
        data = self.client.get("/api/catalog").get_json()
        self.assertGreater(len(data["brands"]), 400)
        self.assertNotIn("countries", data["brands"][0])

    def test_currency_change_keeps_budget_value(self):
        self.client.post("/api/settings", json={"currency": "GBP", "spend_budget": 600})
        state = self.client.post("/api/settings", json={"currency": "INR"}).get_json()
        self.assertGreater(state["settings"]["spend_budget"], 50000)
        self.client.post("/api/settings", json={"currency": "GBP", "spend_budget": 600})

    def test_country_sets_currency(self):
        state = self.client.post("/api/settings", json={"country": "JP"}).get_json()
        self.assertEqual(state["settings"]["currency"], "JPY")
        self.assertEqual(state["currency"]["code"], "JPY")
        ignored = self.client.post("/api/settings", json={"country": "ZZ"}).get_json()
        self.assertEqual(ignored["settings"]["country"], "JP")
        self.client.post("/api/settings", json={"country": "GB"})

    def test_big_numbers_are_fine_in_small_currencies(self):
        self.client.post("/api/settings", json={"country": "ID"})
        res = self.client.post("/api/purchases", json={"product_type": "train", "price": 2_500_000}).get_json()
        self.assertTrue(res["ok"], res)
        self.client.delete(f"/api/purchases/{res['purchase']['id']}")
        self.client.post("/api/settings", json={"country": "GB"})

    def test_demo_and_export(self):
        state = self.client.post("/api/demo").get_json()
        self.assertEqual(state["summary"]["count"], len([r for r in sample_data.THIS_MONTH if r[0] <= date.today().day]))
        csv = self.client.get("/api/export.csv").data.decode()
        self.assertIn("kg CO2e", csv)

    def test_bad_months_are_400_not_500(self):
        for bad in ("2026-13", "2026-00", "abcd-ef", "2026-1"):
            for path in ("/api/state", "/api/drawing/tree", "/api/export.csv"):
                self.assertEqual(self.client.get(f"{path}?month={bad}").status_code, 400, (path, bad))

    def test_nan_and_odd_dates_never_reach_the_database(self):
        for body in ({"product_type": "train", "price": "NaN"},
                     {"product_type": "train", "price": 10, "date": "2026-W48-2"},
                     {"product_type": "train", "price": 10, "date": "20261124"}):
            res = self.client.post("/api/purchases", json=body)
            self.assertEqual(res.status_code, 400, body)
        months = self.client.get("/api/state").get_json()["months"]
        self.assertTrue(all(len(m) == 7 and m[4] == "-" for m in months), months)

    def test_rate_changes_do_not_rewrite_history(self):
        from shopimpact import catalog
        self.client.post("/api/settings", json={"country": "IN"})
        added = self.client.post("/api/purchases", json={"product_type": "fast_fashion", "price": 2000}).get_json()
        before = added["purchase"]["co2"]
        catalog.update_rates({"GBP": 0.76, "INR": 120.0})
        try:
            after = [p for p in self.client.get("/api/state").get_json()["purchases"]
                     if p["id"] == added["purchase"]["id"]][0]["co2"]
        finally:
            catalog.update_rates({})
            self.client.delete(f"/api/purchases/{added['purchase']['id']}")
            self.client.post("/api/settings", json={"country": "GB"})
        self.assertEqual(before, after)

    def test_new_budget_does_not_rewrite_last_month(self):
        from shopimpact.engine import month_key, shift_month
        last = shift_month(month_key(date.today()), -1)
        for day in range(1, 6):
            self.client.post("/api/purchases", json={"product_type": "train", "price": 50, "date": f"{last}-0{day}"})
        before = self.client.get(f"/api/state?month={last}").get_json()["summary"]["budget"]
        self.client.post("/api/settings", json={"co2_budget": 20})
        after = self.client.get(f"/api/state?month={last}").get_json()["summary"]["budget"]
        self.client.post("/api/settings", json={"co2_budget": 200})
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
