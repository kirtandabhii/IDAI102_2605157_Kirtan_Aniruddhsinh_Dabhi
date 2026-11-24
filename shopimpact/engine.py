"""The impact engine: turns raw purchases into CO2 estimates and dashboards.

A purchase is a plain dictionary:

    {"id": 7, "product_type": "fast_fashion", "brand": "Zara",
     "price": 39.99, "currency": "GBP", "date": "2026-11-21",
     "price_gbp": 39.99, "co2": 35.99, "note": "", "swapped_from": None}

`price_gbp` and `co2` are frozen when the purchase is logged, so a later
exchange-rate update never rewrites history.

All functions here are pure (no database, no web framework), which keeps them
easy to test — see tests/test_engine.py.
"""

import calendar
import math
import re
from datetime import date, datetime

from .brands import brand_card, greener_names, is_ethical_brand
from .catalog import CURRENCIES, GROUPS, PRODUCT_TYPES, TIERS, tier_for

# Reference values used for the "what does this feel like?" equivalents.
KG_PER_CAR_KM = 0.17          # average petrol car, per km
KG_PER_PHONE_CHARGE = 0.0124  # one full smartphone charge
KG_PER_TREE_DAY = 21.0 / 365  # a mature tree absorbs roughly 21 kg CO2 a year

# Intensity (kg CO2e per £) at which the eco score bottoms out at zero.
SCORE_FLOOR_INTENSITY = 1.2

GRADES = [  # (minimum score, letter, friendly label)
    (80, "A", "Feather-light"),
    (65, "B", "Light step"),
    (50, "C", "Balanced"),
    (35, "D", "Heavy-ish"),
    (0, "E", "Heavy footprint"),
]

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


# ---------------------------------------------------------------------------
# Small building blocks
# ---------------------------------------------------------------------------
def to_gbp(price, currency="GBP"):
    """Convert a price in any supported currency to pounds sterling."""
    rate = CURRENCIES.get(currency, CURRENCIES["GBP"])["to_gbp"]
    return float(price) * rate


def from_gbp(amount_gbp, currency="GBP"):
    """Convert pounds into any supported currency."""
    return float(amount_gbp) / CURRENCIES.get(currency, CURRENCIES["GBP"])["to_gbp"]


def convert(amount, from_currency, to_currency):
    """Convert money between two supported currencies (via GBP)."""
    return from_gbp(to_gbp(amount, from_currency), to_currency)


def impact_from_gbp(product_type, price_gbp):
    """kg CO2e for a purchase worth `price_gbp` pounds: price x multiplier."""
    info = PRODUCT_TYPES.get(product_type)
    if info is None or price_gbp is None or price_gbp < 0:
        return 0.0
    return round(price_gbp * info["multiplier"], 2)


def calculate_impact(product_type, price, currency="GBP"):
    """Estimated kg CO2e for one purchase: price (in £) x product multiplier."""
    if price is None:
        return 0.0
    return impact_from_gbp(product_type, to_gbp(price, currency))


def swap_details(product_type, price_gbp):
    """What would change if the shopper picked the greener alternative?

    The swap assumes the same spend — a simplification the app explains to
    the user ("same money, lighter choice").
    """
    info = PRODUCT_TYPES.get(product_type)
    if not info or not info["swap_to"]:
        return None
    alt_id = info["swap_to"]
    alt = PRODUCT_TYPES[alt_id]
    current = impact_from_gbp(product_type, price_gbp)
    greener = impact_from_gbp(alt_id, price_gbp)
    saving = round(max(current - greener, 0.0), 2)
    return {
        "to": alt_id,
        "to_name": alt["name"],
        "co2": greener,
        "saving": saving,
        "saving_pct": round(100 * saving / current) if current else 0,
        "why": info["swap_why"],
        "brands": greener_names(alt_id),
    }


def equivalents(kg):
    """Translate kilograms of CO2e into everyday comparisons."""
    kg = max(float(kg), 0.0)
    return {
        "car_km": round(kg / KG_PER_CAR_KM, 1),
        "phone_charges": int(round(kg / KG_PER_PHONE_CHARGE)),
        "tree_days": int(round(kg / KG_PER_TREE_DAY)),
    }


def eco_score(total_co2, total_spend_gbp, budget=None):
    """0-100 score. Higher is greener.

    Two parts, so that buying *more* can never make the score better:
      1. intensity — kg CO2e per £ spent (0.0 -> 100, 1.2 or more -> 0)
      2. budget    — once the month goes over its CO2 budget, the score is
                     scaled down by budget / footprint (twice the budget halves it)
    """
    if total_spend_gbp <= 0:
        return None
    intensity = total_co2 / total_spend_gbp
    score = 100 * (1 - min(intensity / SCORE_FLOOR_INTENSITY, 1.0))
    if budget and total_co2 > budget:
        score *= budget / total_co2
    return int(round(score))


def grade_for(score):
    """Map an eco score to a letter grade and a friendly label."""
    if score is None:
        return {"letter": "–", "label": "No purchases yet"}
    for minimum, letter, label in GRADES:
        if score >= minimum:
            return {"letter": letter, "label": label}
    return {"letter": "E", "label": "Heavy footprint"}


# ---------------------------------------------------------------------------
# Dates and months
# ---------------------------------------------------------------------------
def parse_iso_date(text):
    """Strict YYYY-MM-DD only (no week dates or compact forms). Returns a date or None."""
    if not isinstance(text, str) or not _DATE_RE.match(text):
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def is_valid_month(key):
    """True for 'YYYY-MM' with a real month number."""
    return isinstance(key, str) and bool(_MONTH_RE.match(key))


def month_key(value):
    """'2026-11-21' or a date -> '2026-11'."""
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m")
    return str(value)[:7]


def month_label(key):
    """'2026-11' -> 'November 2026'."""
    year, month = (int(part) for part in key.split("-"))
    return f"{calendar.month_name[month]} {year}"


def shift_month(key, delta):
    """Move a 'YYYY-MM' key forwards or backwards by `delta` months."""
    year, month = (int(part) for part in key.split("-"))
    index = year * 12 + (month - 1) + delta
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def month_end(key):
    year, month = (int(part) for part in key.split("-"))
    return date(year, month, calendar.monthrange(year, month)[1])


def purchases_in_month(purchases, key):
    """Filter a purchase list down to one month."""
    return [p for p in purchases if month_key(p["date"]) == key]


def is_finite_number(value):
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Enrichment — attach every derived number the UI needs to a purchase
# ---------------------------------------------------------------------------
def enrich(purchase, display_currency="GBP"):
    """Return a copy of the purchase with CO2, tier, names and swap info."""
    info = PRODUCT_TYPES.get(purchase["product_type"], {})
    multiplier = info.get("multiplier", 0.0)
    # Frozen at entry when available; older rows fall back to today's rate.
    price_gbp = purchase.get("price_gbp")
    if price_gbp is None:
        price_gbp = to_gbp(purchase["price"], purchase["currency"])
    co2 = purchase.get("co2")
    if co2 is None:
        co2 = impact_from_gbp(purchase["product_type"], price_gbp)
    if purchase["currency"] == display_currency:
        display_price = purchase["price"]
    else:
        display_price = from_gbp(price_gbp, display_currency)
    group = info.get("group", "leisure")
    enriched = dict(purchase)
    enriched.update({
        "type_name": info.get("name", purchase["product_type"]),
        "group": group,
        "group_name": GROUPS[group]["name"],
        "icon": GROUPS[group]["icon"],
        "multiplier": multiplier,
        "tier": tier_for(multiplier),
        "co2": round(co2, 2),
        "price_gbp": round(price_gbp, 4),
        "display_price": round(display_price, 2),
        "ethical_brand": is_ethical_brand(purchase.get("brand", "")),
        "brand_info": brand_card(purchase.get("brand", "")),
        "tags": info.get("tags", []),
        "swap": swap_details(purchase["product_type"], price_gbp),
        "equivalents": equivalents(co2),
    })
    if purchase.get("swapped_from"):
        original = impact_from_gbp(purchase["swapped_from"], price_gbp)
        enriched["swap_saved"] = round(max(original - co2, 0.0), 2)
        enriched["swapped_from_name"] = PRODUCT_TYPES.get(purchase["swapped_from"], {}).get("name")
    return enriched


def sort_purchases(purchases):
    """Oldest first, ties broken by id — the order a shopper logged them."""
    return sorted(purchases, key=lambda p: (str(p["date"]), p.get("id") or 0))


# ---------------------------------------------------------------------------
# The monthly dashboard
# ---------------------------------------------------------------------------
def cumulative_on_day(summary, day):
    """CO2 a month had reached by `day` (used for like-for-like comparisons)."""
    if not summary:
        return 0.0
    day = max(1, min(day, summary["days_in_month"]))
    return summary["daily"][day - 1]["cum"]


def monthly_summary(purchases, key, settings, today=None, budgets=None):
    """Everything the dashboard shows for one month.

    `purchases` should already be enriched and filtered to the month.
    `budgets` overrides the settings' budgets (each month keeps the budget it
    had, so changing a budget later never rewrites a past month).
    `today` is the shopper's local date (defaults to the server's).
    """
    today = today or date.today()
    budgets = budgets or {}
    display_currency = settings.get("currency", "GBP")
    budget = float(budgets.get("co2_budget", settings.get("co2_budget", 200)))
    spend_budget_gbp = budgets.get("spend_budget_gbp")
    if spend_budget_gbp is None:
        spend_budget = float(settings.get("spend_budget", 600))
    else:
        spend_budget = round(from_gbp(spend_budget_gbp, display_currency), 2)

    total_co2 = round(sum(p["co2"] for p in purchases), 2)
    total_gbp = sum(p["price_gbp"] for p in purchases)
    total_spend = round(sum(p["display_price"] for p in purchases), 2)
    score = eco_score(total_co2, total_gbp, budget)

    # Breakdown by impact tier.
    tiers = {tier: {"count": 0, "co2": 0.0, "spend": 0.0} for tier in TIERS}
    for p in purchases:
        bucket = tiers[p["tier"]]
        bucket["count"] += 1
        bucket["co2"] = round(bucket["co2"] + p["co2"], 2)
        bucket["spend"] = round(bucket["spend"] + p["display_price"], 2)

    # Breakdown by product group, biggest footprint first.
    groups = {}
    for p in purchases:
        g = groups.setdefault(p["group"], {"id": p["group"], "name": p["group_name"], "icon": p["icon"],
                                           "co2": 0.0, "spend": 0.0, "spend_gbp": 0.0, "count": 0})
        g["co2"] = round(g["co2"] + p["co2"], 2)
        g["spend"] = round(g["spend"] + p["display_price"], 2)
        g["spend_gbp"] += p["price_gbp"]
        g["count"] += 1
    group_list = sorted(groups.values(), key=lambda g: g["co2"], reverse=True)
    for g in group_list:
        g["share"] = round(g["co2"] / total_co2, 3) if total_co2 else 0
        g["intensity"] = round(g["co2"] / g["spend_gbp"], 2) if g["spend_gbp"] else 0
        g["tier"] = tier_for(g["intensity"])
        del g["spend_gbp"]

    # Day-by-day series for the month curve (cumulative CO2 against budget).
    year, month = (int(part) for part in key.split("-"))
    days_in_month = calendar.monthrange(year, month)[1]
    per_day = [0.0] * days_in_month
    count_day = [0] * days_in_month
    for p in purchases:
        day = int(str(p["date"])[8:10])
        per_day[day - 1] += p["co2"]
        count_day[day - 1] += 1
    daily, running = [], 0.0
    for i in range(days_in_month):
        running += per_day[i]
        daily.append({"day": i + 1, "co2": round(per_day[i], 2),
                      "cum": round(running, 2), "count": count_day[i]})

    # Biggest swap opportunities this month.
    swaps = [p for p in purchases if p["swap"] and p["swap"]["saving"] > 0]
    swaps.sort(key=lambda p: p["swap"]["saving"], reverse=True)
    potential = round(sum(p["swap"]["saving"] for p in swaps), 2)

    # "What if I swapped x% of my medium/high buys?" — computed here, once.
    heavy_saving = sum(p["swap"]["saving"] for p in swaps if p["tier"] != "low")
    whatif = []
    for pct in range(0, 101, 5):
        saved = heavy_saving * pct / 100
        after = max(total_co2 - saved, 0.0)
        whatif.append({"pct": pct, "saved": round(saved, 2), "after": round(after, 2),
                       "score": eco_score(after, total_gbp, budget)})

    is_current = (today.year, today.month) == (year, month)
    is_complete = today > month_end(key)
    days_elapsed = today.day if is_current else days_in_month
    projected = round(total_co2 / days_elapsed * days_in_month, 1) if is_current and days_elapsed else total_co2

    return {
        "month": key,
        "label": month_label(key),
        "is_current": is_current,
        "is_complete": is_complete,
        "days_in_month": days_in_month,
        "today": today.day if is_current else None,
        "compare_day": days_elapsed,
        "count": len(purchases),
        "spend": total_spend,
        "spend_gbp": round(total_gbp, 2),
        "co2": total_co2,
        "intensity": round(total_co2 / total_gbp, 3) if total_gbp else 0,
        "score": score,
        "grade": grade_for(score),
        "budget": budget,
        "budget_pct": round(100 * total_co2 / budget) if budget else 0,
        "budget_left": round(budget - total_co2, 1),
        "spend_budget": spend_budget,
        "spend_pct": round(100 * total_spend / spend_budget) if spend_budget else 0,
        "projected": projected,
        "tiers": tiers,
        "groups": group_list,
        "daily": daily,
        "potential_saving": potential,
        "whatif": whatif,
        "top_swaps": [{"id": p["id"], "type_name": p["type_name"], "brand": p.get("brand", ""),
                       "to_name": p["swap"]["to_name"], "saving": p["swap"]["saving"]}
                      for p in swaps[:3]],
        "swapped_saving": round(sum(p.get("swap_saved", 0) for p in purchases), 2),
        "equivalents": equivalents(total_co2),
        "ethical_count": sum(1 for p in purchases if p["ethical_brand"]),
    }


def history(all_enriched, end_key, budgets_for, months=6):
    """A compact summary of the last few months for the trend chart.

    `budgets_for(month)` returns that month's CO2 budget.
    """
    rows = []
    for offset in range(months - 1, -1, -1):
        key = shift_month(end_key, -offset)
        in_month = purchases_in_month(all_enriched, key)
        co2 = round(sum(p["co2"] for p in in_month), 1)
        gbp = sum(p["price_gbp"] for p in in_month)
        rows.append({"month": key, "label": month_label(key)[:3], "co2": co2,
                     "count": len(in_month), "score": eco_score(co2, gbp, budgets_for(key))})
    return rows


def estimate(product_type, price, currency, brand="", swapped_from=None):
    """Live preview for the 'ring it up' form, before anything is saved."""
    info = PRODUCT_TYPES.get(product_type)
    if not info:
        return {"ok": False, "error": "Choose a product type to see its impact."}
    price = float(price) if is_finite_number(price) and float(price) > 0 else 0.0
    price_gbp = to_gbp(price, currency)
    co2 = impact_from_gbp(product_type, price_gbp)
    result = {
        "ok": True,
        "co2": co2,
        "price_gbp": round(price_gbp, 4),
        "tier": tier_for(info["multiplier"]),
        "multiplier": info["multiplier"],
        "equivalents": equivalents(co2),
        "swap": swap_details(product_type, price_gbp),
        "ethical_brand": is_ethical_brand(brand),
        "brand_info": brand_card(brand),
        "greener": greener_names(product_type),
    }
    if swapped_from in PRODUCT_TYPES and swapped_from != product_type:
        original = impact_from_gbp(swapped_from, price_gbp)
        result["swapped_from_name"] = PRODUCT_TYPES[swapped_from]["name"]
        result["swapped_saving"] = round(max(original - co2, 0.0), 2)
    return result
