"""The one place where ShopImpact's rules live.

Both front ends call this module:
    app.py         the Streamlit app (the assessed submission)
    web_app.py     the optional standalone web edition (Flask)

It validates input, freezes each purchase's £ value and CO2, keeps a budget
snapshot per month, evaluates badges and builds everything a screen shows.
"""

import csv
import io
import json
from datetime import date, timedelta

from . import drawings, sample_data
from .badges import BADGES_BY_ID, evaluate_badges
from .catalog import CURRENCIES, PRODUCT_TYPES
from .content import random_tip, reward_message
from .engine import (cumulative_on_day, enrich, impact_from_gbp, is_finite_number, is_valid_month,
                     month_key, monthly_summary, parse_iso_date, purchases_in_month, shift_month,
                     sort_purchases, history, to_gbp)
from .world import COUNTRY_BY_CODE

MAX_PRICE_GBP = 1_000_000
MAX_BRAND = 60
MAX_NOTE = 120
EARLIEST_DATE = date(2000, 1, 1)


class ValidationError(ValueError):
    """A friendly, user-facing message about bad input."""


def _freeze(product_type, price, currency):
    """£ value, CO2 and exchange rate fixed at the moment a purchase is logged."""
    rate = CURRENCIES[currency]["to_gbp"]
    price_gbp = round(float(price) * rate, 4)
    return price_gbp, impact_from_gbp(product_type, price_gbp), rate


def validate_purchase(data, settings, today):
    """Check the 'ring it up' form. Returns a clean purchase dict or raises ValidationError."""
    ptype = str(data.get("product_type") or "").strip()
    if ptype not in PRODUCT_TYPES:
        raise ValidationError("Choose a product type from the list.")

    raw_price = data.get("price")
    if raw_price in (None, "") or not is_finite_number(raw_price):
        raise ValidationError("Enter a price as a number, for example 24.99.")
    price = round(float(raw_price), 2)
    if price <= 0:
        raise ValidationError("Enter a price above zero.")
    currency = data.get("currency") if data.get("currency") in CURRENCIES else settings["currency"]
    if to_gbp(price, currency) > MAX_PRICE_GBP:
        raise ValidationError("That price looks too large — check for an extra zero.")

    brand = str(data.get("brand") or "").strip()
    if len(brand) > MAX_BRAND:
        raise ValidationError(f"Keep the brand under {MAX_BRAND} characters.")
    note = str(data.get("note") or "").strip()
    if len(note) > MAX_NOTE:
        raise ValidationError(f"Keep the item name under {MAX_NOTE} characters.")

    when = parse_iso_date(str(data.get("date") or today.isoformat()))
    if when is None:
        raise ValidationError("Pick a valid date (YYYY-MM-DD).")
    if when > today + timedelta(days=1):  # one day of slack for time zones
        raise ValidationError("That date is in the future — log purchases once you've made them.")
    if when < EARLIEST_DATE:
        raise ValidationError("Pick a date from the year 2000 onwards.")

    swapped_from = data.get("swapped_from")
    if swapped_from not in PRODUCT_TYPES or swapped_from == ptype:
        swapped_from = None  # only set when the shopper took a greener swap

    price_gbp, co2, rate = _freeze(ptype, price, currency)
    return {"product_type": ptype, "brand": brand, "price": price, "currency": currency,
            "date": when.isoformat(), "note": note, "swapped_from": swapped_from,
            "price_gbp": price_gbp, "co2": co2, "rate": rate}


def csv_safe(value):
    """Stop spreadsheet apps treating a cell as a formula (CSV injection)."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


class Service:
    def __init__(self, store):
        self.store = store

    # -- budgets -------------------------------------------------------------
    def _current_budgets(self, settings):
        rate = CURRENCIES[settings["currency"]]["to_gbp"]
        return {"co2_budget": float(settings["co2_budget"]),
                "spend_budget_gbp": round(float(settings["spend_budget"]) * rate, 2)}

    def _snapshot(self, sid, month, settings, overwrite=False):
        b = self._current_budgets(settings)
        self.store.set_month_budget(sid, month, b["co2_budget"], b["spend_budget_gbp"], overwrite)

    # -- the whole dashboard for one month ------------------------------------
    def state(self, sid, key, today):
        if not is_valid_month(key):
            raise ValidationError("Month must look like 2026-11.")
        self.store.freeze_missing(sid, lambda row: _freeze(row["product_type"], row["price"], row["currency"]))
        settings = self.store.settings(sid)
        currency = settings["currency"]
        snapshots = self.store.month_budgets(sid)
        current = self._current_budgets(settings)

        def budgets_for(month):
            return snapshots.get(month, current)

        everything = [enrich(p, currency) for p in sort_purchases(self.store.purchases(sid))]
        month = purchases_in_month(everything, key)
        summary = monthly_summary(month, key, settings, today, budgets_for(key))

        # Finished months keep the budget they had, even if settings change later.
        if summary["is_complete"] and month and key not in snapshots:
            self._snapshot(sid, key, settings)

        prev_key = shift_month(key, -1)
        prev_month = purchases_in_month(everything, prev_key)
        prev = monthly_summary(prev_month, prev_key, settings, today, budgets_for(prev_key)) if prev_month else None
        baseline = cumulative_on_day(prev, summary["compare_day"]) if prev else 0
        summary["vs_prev_pct"] = round(100 * (summary["co2"] - baseline) / baseline) if baseline else None
        summary["vs_prev_basis"] = ("same point last month" if summary["is_current"] else "last month") \
            if baseline else None

        badges = evaluate_badges(month, everything, summary, prev)
        data_months = {month_key(p["date"]) for p in everything}
        today_key = month_key(today)
        latest_month = max(data_months | {today_key})
        earliest_month = min(data_months | {today_key})
        # The receipt shows the last purchase logged in this month (or overall if the month is empty).
        pool = month or everything
        latest = max(pool, key=lambda p: p["id"]) if pool else None

        state = {
            "ok": True,
            "month": key,
            "today": today.isoformat(),
            "months": sorted(data_months | {today_key}),
            "can_prev": key > shift_month(earliest_month, -12),
            "can_next": key < latest_month,
            "settings": settings,
            "currency": {"code": currency, "symbol": CURRENCIES[currency]["symbol"],
                         "name": CURRENCIES[currency]["name"], "to_gbp": CURRENCIES[currency]["to_gbp"],
                         "slider_max": CURRENCIES[currency]["slider"][0],
                         "slider_step": CURRENCIES[currency]["slider"][1]},
            "summary": summary,
            "purchases": list(reversed(month)),  # newest date first for lists
            "latest": latest,
            "badges": badges,
            "history": history(everything, key, lambda m: budgets_for(m)["co2_budget"]),
            "total_count": len(everything),
        }
        # Month-long badges from a month that has just finished get celebrated once.
        state["celebrate"] = self._finished_month_awards(sid, everything, today, settings, budgets_for) \
            if key == today_key else []
        return state

    def _finished_month_awards(self, sid, everything, today, settings, budgets_for):
        last = shift_month(month_key(today), -1)
        in_last = purchases_in_month(everything, last)
        if not in_last:
            return []
        summary = monthly_summary(in_last, last, settings, today, budgets_for(last))
        before = shift_month(last, -1)
        in_before = purchases_in_month(everything, before)
        prev = monthly_summary(in_before, before, settings, today, budgets_for(before)) if in_before else None
        earned = {b["id"] for b in evaluate_badges(in_last, everything, summary, prev)
                  if b["earned"] and b["id"] in ("eco_saver", "mindful_spender", "carbon_cutter")}
        fresh = earned - self.store.awarded(sid, last)
        if fresh:
            self.store.award(sid, fresh, last)
        return [self._badge_card(b, month=summary["label"]) for b in sorted(fresh)]

    def _badge_card(self, badge_id, month=None):
        info = BADGES_BY_ID[badge_id]
        return {"id": badge_id, "name": info["name"], "blurb": info["blurb"], "month": month,
                "svg": drawings.render("badge", color=info["color"], emblem=info["emblem"], name=info["name"])}

    def new_badges(self, sid, state):
        """Badges earned now that have not been celebrated before."""
        key = state["month"]
        earned = {b["id"] for b in state["badges"] if b["earned"]}
        fresh = earned - self.store.awarded(sid, key)
        if fresh:
            self.store.award(sid, fresh, key)
        return [self._badge_card(b["id"]) for b in state["badges"] if b["id"] in fresh]

    # -- actions ---------------------------------------------------------------
    def add(self, sid, data, today):
        settings = self.store.settings(sid)
        purchase = validate_purchase(data, settings, today)
        key = month_key(purchase["date"])
        self._snapshot(sid, key, settings)  # first purchase of a month fixes its budget
        saved = enrich(self.store.add(sid, purchase), settings["currency"])
        state = self.state(sid, key, today)
        kind = drawings.REWARD_FOR_TIER[saved["tier"]]
        return {
            "ok": True,
            "purchase": saved,
            "reward": {"kind": kind, "svg": drawings.render(kind), "message": reward_message(saved["tier"])},
            "tip": random_tip(saved["group"]),
            "new_badges": self.new_badges(sid, state),
            "state": state,
        }

    def swap(self, sid, purchase_id, today, to=None, brand=None):
        current = self.store.get(sid, purchase_id)
        if not current:
            raise LookupError("That purchase no longer exists.")
        target = to or PRODUCT_TYPES[current["product_type"]]["swap_to"]
        if target not in PRODUCT_TYPES:
            raise ValidationError("There is no greener swap for this product type.")
        brand = (brand or "").strip()
        if len(brand) > MAX_BRAND:
            raise ValidationError(f"Keep the brand under {MAX_BRAND} characters.")
        original = current["swapped_from"] or current["product_type"]
        price_gbp = current["price_gbp"] if current["price_gbp"] is not None else \
            to_gbp(current["price"], current["currency"])
        updated = self.store.update_type(sid, purchase_id, target, original,
                                         impact_from_gbp(target, price_gbp), brand or None)
        settings = self.store.settings(sid)
        saved = enrich(updated, settings["currency"])
        state = self.state(sid, month_key(saved["date"]), today)
        return {"ok": True, "purchase": saved, "svg": drawings.render("sprig"),
                "new_badges": self.new_badges(sid, state), "state": state}

    def delete(self, sid, purchase_id, today):
        current = self.store.get(sid, purchase_id)
        if not current:
            raise LookupError("That purchase no longer exists.")
        self.store.delete(sid, purchase_id)
        return {"ok": True, "deleted": current, "state": self.state(sid, month_key(current["date"]), today)}

    def restore(self, sid, data, today):
        """Undo a delete: put the purchase back exactly as it was (same frozen values)."""
        settings = self.store.settings(sid)
        purchase = validate_purchase(data, settings, today)
        for field in ("price_gbp", "co2", "rate"):
            if is_finite_number(data.get(field)):
                purchase[field] = float(data[field])
        self.store.add(sid, purchase)
        return {"ok": True, "state": self.state(sid, month_key(purchase["date"]), today)}

    def update_settings(self, sid, data, today, month=None):
        values = {}
        if "name" in data:
            values["name"] = str(data["name"]).strip()[:40]
        current = self.store.settings(sid)
        if data.get("country") in COUNTRY_BY_CODE:
            values["country"] = data["country"]
            data = {**data}
            data.setdefault("currency", COUNTRY_BY_CODE[data["country"]]["currency"])
        if data.get("currency") in CURRENCIES:
            values["currency"] = data["currency"]
            if data["currency"] != current["currency"] and "spend_budget" not in data:
                # Keep the spending budget worth the same when the currency changes.
                gbp = current["spend_budget"] * CURRENCIES[current["currency"]]["to_gbp"]
                local = gbp / CURRENCIES[data["currency"]]["to_gbp"]
                step = CURRENCIES[data["currency"]]["slider"][1] * 10
                values["spend_budget"] = max(step, round(local / step) * step)
        currency = values.get("currency", current["currency"])
        max_spend = MAX_PRICE_GBP / CURRENCIES[currency]["to_gbp"]
        for field, low, high in (("co2_budget", 10, 2000), ("spend_budget", 1, max_spend)):
            if field in data:
                if not is_finite_number(data[field]):
                    raise ValidationError(f"{field.replace('_', ' ').capitalize()} must be a number.")
                values[field] = max(low, min(high, round(float(data[field]))))
        saved = self.store.save_settings(sid, values)
        if "co2_budget" in values or "spend_budget" in values:
            # A new budget applies to this month onwards — past months keep theirs.
            self._snapshot(sid, month_key(today), saved, overwrite=True)
        return self.state(sid, month if is_valid_month(month or "") else month_key(today), today)

    UI_DEFAULTS = {"theme": "light", "text": "regular", "sound": True, "volume": 0.6, "motion": "full", "speed": 1.0}

    def ui_prefs(self, sid):
        """Look-and-feel choices (theme, text size, sound…), with safe defaults."""
        saved = self.store.settings(sid).get("ui") or {}
        return {**self.UI_DEFAULTS, **{k: v for k, v in saved.items() if k in self.UI_DEFAULTS}}

    def save_ui_prefs(self, sid, changes):
        prefs = self.ui_prefs(sid)
        allowed = {"theme": {"light", "dark", "contrast"}, "text": {"regular", "large"}, "motion": {"full", "reduced"}}
        for key, value in changes.items():
            if key in allowed and value in allowed[key]:
                prefs[key] = value
            elif key == "sound":
                prefs[key] = bool(value)
            elif key == "volume" and is_finite_number(value):
                prefs[key] = max(0.0, min(1.0, float(value)))
            elif key == "speed" and is_finite_number(value):
                prefs[key] = max(0.5, min(3.0, float(value)))
        self.store.save_settings(sid, {"ui": prefs})
        return prefs

    def load_demo(self, sid, today):
        self.store.clear(sid)
        settings = self.store.settings(sid)
        rows = sample_data.build(today=today, currency=settings["currency"])
        for row in rows:
            row["price_gbp"], row["co2"], row["rate"] = _freeze(row["product_type"], row["price"], row["currency"])
        self.store.add_many(sid, rows)
        for key in {month_key(r["date"]) for r in rows}:
            self._snapshot(sid, key, settings)
        state = self.state(sid, month_key(today), today)
        # Celebrate nothing retroactively: mark sample-data badges as already seen.
        self.store.award(sid, [b["id"] for b in state["badges"] if b["earned"]], state["month"])
        state["celebrate"] = []
        return state

    def reset(self, sid, today):
        self.store.clear(sid)
        return self.state(sid, month_key(today), today)

    # -- outputs ---------------------------------------------------------------
    def export_csv(self, sid, key, today):
        state = self.state(sid, key, today)
        code = state["currency"]["code"]
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["Date", "Product type", "Brand", f"Price ({code})", "kg CO2e", "Impact",
                         "Greener swap", "Possible saving (kg)", "Note"])
        for p in reversed(state["purchases"]):
            writer.writerow([p["date"], csv_safe(p["type_name"]), csv_safe(p["brand"]), f'{p["display_price"]:.2f}',
                             f'{p["co2"]:.2f}', p["tier"], p["swap"]["to_name"] if p["swap"] else "",
                             f'{p["swap"]["saving"]:.2f}' if p["swap"] else "", csv_safe(p["note"])])
        s = state["summary"]
        writer.writerow([])
        writer.writerow(["Month", s["label"]])
        writer.writerow(["Total spend", f'{s["spend"]:.2f}'])
        writer.writerow(["Total kg CO2e", f'{s["co2"]:.2f}'])
        writer.writerow(["Eco score", s["score"] if s["score"] is not None else "-"])
        return f"shopimpact-{key}.csv", buffer.getvalue()

    def tree_svg(self, sid, key, today):
        state = self.state(sid, key, today)
        tiers = state["summary"]["tiers"]
        seed = sum(ord(c) for c in key + sid[:6])
        return drawings.render("tree", score=state["summary"]["score"], low=tiers["low"]["count"],
                               medium=tiers["medium"]["count"], high=tiers["high"]["count"], seed=seed)

    def backup(self, sid):
        """Everything this shopper has, as JSON they can keep."""
        return json.dumps({"app": "ShopImpact", "version": 2, "settings": self.store.settings(sid),
                           "purchases": self.store.purchases(sid)}, indent=2)

    def restore_backup(self, sid, text, today):
        """Replace this shopper's data with a backup file (every row re-validated)."""
        try:
            payload = json.loads(text)
            rows = payload["purchases"]
            assert isinstance(rows, list)
        except (ValueError, KeyError, TypeError, AssertionError):
            raise ValidationError("That file isn't a ShopImpact backup.")
        settings = self.store.settings(sid)
        clean = []
        for i, row in enumerate(rows, start=1):
            try:
                purchase = validate_purchase(row, settings, today)
            except ValidationError as err:
                raise ValidationError(f"Row {i}: {err}")
            for field in ("price_gbp", "co2", "rate"):
                if is_finite_number(row.get(field)):
                    purchase[field] = float(row[field])
            clean.append(purchase)
        self.store.clear(sid)
        incoming = payload.get("settings") if isinstance(payload.get("settings"), dict) else {}
        wanted = {k: incoming[k] for k in ("name", "country", "currency", "co2_budget", "spend_budget")
                  if k in incoming and incoming[k] is not None}
        try:
            self.update_settings(sid, wanted, today)  # same checks as the Settings screen
        except ValidationError:
            pass  # keep current settings if the backup's are unusable
        self.store.add_many(sid, clean)
        for key in {month_key(p["date"]) for p in clean}:
            self._snapshot(sid, key, self.store.settings(sid))
        return len(clean)
