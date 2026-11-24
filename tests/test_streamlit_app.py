"""Headless tests of the Streamlit app (app.py) with Streamlit's AppTest.

Run with:  python -m unittest discover tests
"""

import os
import tempfile
import unittest

os.environ.setdefault("SHOPIMPACT_LIVE_RATES", "0")
os.environ.setdefault("SHOPIMPACT_LOGOS", "0")  # no network in tests
_TMP = tempfile.TemporaryDirectory()
os.environ["SHOPIMPACT_DB"] = os.path.join(_TMP.name, "streamlit-test.db")

from streamlit.testing.v1 import AppTest  # noqa: E402

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


def open_app(shopper="a" * 32):
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params["id"] = shopper
    return at.run()


class StreamlitAppTests(unittest.TestCase):
    def test_overview_renders_with_real_widgets(self):
        at = open_app("b" * 32)
        self.assertFalse(at.exception, at.exception)
        keys = {w.key for w in at.selectbox} | {w.key for w in at.number_input} | {w.key for w in at.button}
        for key in ("f_type", "f_brand", "f_price", "ring", "nav_ledger"):
            self.assertIn(key, keys)
        self.assertTrue(any(m.label == "Footprint this month" for m in at.metric))

    def test_every_screen_renders(self):
        at = open_app("c" * 32)
        for view in ("overview", "ledger", "swaps", "badges", "garden", "settings"):
            at.session_state["view"] = view
            at.run()
            self.assertFalse(at.exception, f"{view}: {at.exception}")

    def test_ring_up_a_purchase(self):
        at = open_app("d" * 32)
        at.selectbox(key="f_type").set_value("fast_fashion")
        at.selectbox(key="f_brand").set_value("Zara")
        at.number_input(key="f_price").set_value(40.0)
        at.run()
        at.button(key="ring").click().run()
        self.assertFalse(at.exception, at.exception)
        receipt = at.session_state["receipt"]
        self.assertEqual(receipt["purchase"]["co2"], 36.0)
        self.assertEqual(receipt["purchase"]["brand"], "Zara")
        self.assertIsNone(at.session_state["f_type"])       # the form resets for the next purchase
        footprint = next(m for m in at.metric if m.label == "Footprint this month")
        self.assertIn("36.0", footprint.value)

    def test_missing_price_shows_a_friendly_error(self):
        at = open_app("e" * 32)
        at.selectbox(key="f_type").set_value("train").run()
        at.button(key="ring").click().run()
        self.assertIn("price", at.session_state["form_error"].lower())

    def test_price_tag_follows_the_price(self):
        at = open_app("f" * 32)
        at.number_input(key="f_price").set_value(47.0).run()
        self.assertEqual(at.select_slider(key="f_tag").value, 47)


if __name__ == "__main__":
    unittest.main()
