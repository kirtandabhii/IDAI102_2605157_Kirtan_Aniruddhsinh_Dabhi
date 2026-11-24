"""Badge rules.

Each badge is a dictionary with display details plus a `rule` function. A rule
receives a BadgeContext and returns (progress, hint): progress runs from 0.0 to
1.0 and the badge is earned at 1.0. The hint tells the shopper what is left.

Fairness rules (from the audit):
  * Only purchases worth about £1 or more count, so badges can't be farmed
    with 1p entries.
  * Badges that judge a whole month (Eco Saver, Mindful Spender, Carbon Cutter)
    show "on track" during the month and lock in once it ends.
  * Carbon Cutter compares like with like: this month so far against last
    month up to the same day.
  * First Step is a lifetime badge, labelled as such.
"""

from .catalog import TIER_LIMITS
from .engine import cumulative_on_day, month_label

MIN_QUALIFYING_GBP = 1.0   # purchases below this don't count towards badges
LOW_INTENSITY = TIER_LIMITS["low"]  # the same line as the low-impact tier


class BadgeContext:
    """Everything a rule might need, computed once per evaluation."""

    def __init__(self, month_purchases, all_purchases, summary, prev_summary):
        self.summary = summary                       # this month's dashboard summary
        self.prev = prev_summary                     # last month's summary (or None)
        self.all = all_purchases                     # enriched, every month
        # Qualifying purchases, in the order they were logged.
        self.month = sorted((p for p in month_purchases if p["price_gbp"] >= MIN_QUALIFYING_GBP),
                            key=lambda p: p.get("id") or 0)
        self.count = len(self.month)
        self.is_complete = summary["is_complete"]
        self.month_name = summary["label"].split()[0]

    def tagged(self, tag):
        return [p for p in self.month if tag in p["tags"]]

    def trailing_low_streak(self):
        """How many of the most recently logged purchases in a row were low impact."""
        streak = 0
        for p in reversed(self.month):
            if p["tier"] != "low":
                break
            streak += 1
        return streak

    def lock_in(self, met, progress_if_not, hint_if_not):
        """Month-long badges: earned only once the month is over."""
        if not met:
            return progress_if_not, hint_if_not
        if self.is_complete:
            return 1.0, "Earned."
        return 0.95, f"On track — locks in when {self.month_name} ends."


def _ratio(value, target):
    return max(0.0, min(value / target, 1.0)) if target else 0.0


def _left(n, word):
    return f"{n} more {word}{'' if n == 1 else 's'}"


# --- Rules -----------------------------------------------------------------
def rule_first_step(ctx):
    """Lifetime badge: earned from the month of your very first purchase onwards."""
    if not ctx.all:
        return 0.0, "Ring up your first purchase."
    first = min(p["date"] for p in ctx.all)
    if first[:7] > ctx.summary["month"]:
        return 0.0, "Ring up your first purchase."
    return 1.0, f"Lifetime badge — earned in {month_label(first[:7])}."


def rule_low_impact(ctx):
    need = 5
    if ctx.count == 0:
        return 0.0, f"Log {need} purchases averaging under {LOW_INTENSITY:.2f} kg CO₂e per £."
    spend = sum(p["price_gbp"] for p in ctx.month)
    intensity = sum(p["co2"] for p in ctx.month) / spend if spend else 0
    count_part = _ratio(ctx.count, need)
    if intensity <= LOW_INTENSITY:
        hint = "Earned." if count_part >= 1 else f"Keep it light for {_left(need - ctx.count, 'purchase')}."
        return count_part, hint
    return count_part * _ratio(LOW_INTENSITY, intensity) * 0.95, \
        f"Average is {intensity:.2f} kg per £ — aim for {LOW_INTENSITY:.2f} or less."


def rule_eco_saver(ctx):
    need = 5
    co2, budget = ctx.summary["co2"], ctx.summary["budget"]
    if co2 > budget:
        return _ratio(budget, co2) * 0.9, f"You are {co2 - budget:.1f} kg over this month's budget."
    if ctx.count < need:
        return _ratio(ctx.count, need) * 0.9, f"Stay under budget for {_left(need - ctx.count, 'purchase')}."
    return ctx.lock_in(True, 0, "")


def rule_second_life(ctx):
    n = len(ctx.tagged("second_life"))
    return _ratio(n, 3), "Earned." if n >= 3 else f"Buy {_left(3 - n, 'second-hand or refurbished item')}."


def rule_ethical_ally(ctx):
    n = sum(1 for p in ctx.month if p["ethical_brand"])
    return _ratio(n, 2), "Earned." if n >= 2 else f"Shop with {_left(2 - n, 'greener brand')}."


def rule_green_streak(ctx):
    n = ctx.trailing_low_streak()
    return _ratio(n, 5), "Earned." if n >= 5 else f"{n} low-impact in a row — {5 - n} to go."


def rule_plant_powered(ctx):
    n = len(ctx.tagged("plant"))
    return _ratio(n, 3), "Earned." if n >= 3 else f"Pick {_left(3 - n, 'plant-based or local food shop')}."


def rule_mindful_spender(ctx):
    need = 5
    spend, budget = ctx.summary["spend"], ctx.summary["spend_budget"]
    if spend > budget:
        return _ratio(budget, spend) * 0.9, "Spending is over this month's budget."
    if ctx.count < need:
        return _ratio(ctx.count, need) * 0.9, f"Stay within budget for {_left(need - ctx.count, 'purchase')}."
    return ctx.lock_in(True, 0, "")


def rule_swap_master(ctx):
    n = sum(1 for p in ctx.month if p.get("swapped_from"))
    return _ratio(n, 3), "Earned." if n >= 3 else f"Use the Swap button on {_left(3 - n, 'purchase')}."


def rule_carbon_cutter(ctx):
    if not ctx.prev or ctx.prev["co2"] <= 0:
        return 0.0, "Needs a previous month to compare against."
    # Like for like: last month up to the same day of the month.
    baseline = cumulative_on_day(ctx.prev, ctx.summary["compare_day"])
    if baseline <= 0:
        return 0.0, f"Last month had nothing logged by day {ctx.summary['compare_day']} to compare against."
    target = baseline * 0.8
    if ctx.count < 5:
        return _ratio(ctx.count, 5) * 0.5, f"Log {_left(5 - ctx.count, 'purchase')} first."
    met = ctx.summary["co2"] <= target
    return ctx.lock_in(met, _ratio(target, ctx.summary["co2"]) * 0.9,
                       f"Get below {target:.0f} kg (20% under last month at this point).")


# --- The badge list ----------------------------------------------------------
# `emblem` picks the turtle drawing in drawings.py, `color` its rosette colour.
BADGES = [
    {"id": "first_step", "name": "First Step", "emblem": "footprint", "color": "#3F7D58",
     "blurb": "Lifetime badge: you logged your first purchase. Awareness starts here.", "rule": rule_first_step},
    {"id": "eco_saver", "name": "Eco Saver of the Month", "emblem": "star", "color": "#2F6F8F",
     "blurb": "Finish a month with 5+ purchases and stay under its CO₂ budget.", "rule": rule_eco_saver},
    {"id": "low_impact", "name": "Low Impact Shopper", "emblem": "leaf", "color": "#4E8A57",
     "blurb": f"5+ purchases averaging {LOW_INTENSITY:.2f} kg CO₂e per £ or less — the low-impact tier.",
     "rule": rule_low_impact},
    {"id": "second_life", "name": "Second-Life Hero", "emblem": "loop", "color": "#7A6A3A",
     "blurb": "Three second-hand, refurbished, rented or repaired finds in one month.", "rule": rule_second_life},
    {"id": "ethical_ally", "name": "Ethical Brand Ally", "emblem": "heart", "color": "#A2553F",
     "blurb": "Two purchases from brands on the greener list.", "rule": rule_ethical_ally},
    {"id": "green_streak", "name": "Green Streak", "emblem": "bolt", "color": "#C08A1E",
     "blurb": "The last five purchases you logged were all low impact.", "rule": rule_green_streak},
    {"id": "plant_powered", "name": "Plant Powered", "emblem": "sprout", "color": "#5E8C3A",
     "blurb": "Three plant-based or local food shops in one month.", "rule": rule_plant_powered},
    {"id": "mindful_spender", "name": "Mindful Spender", "emblem": "check", "color": "#45607A",
     "blurb": "Finish a month with 5+ purchases and stay within its spending budget.", "rule": rule_mindful_spender},
    {"id": "swap_master", "name": "Swap Master", "emblem": "swap", "color": "#2E7C7A",
     "blurb": "Swapped three purchases for their greener alternative.", "rule": rule_swap_master},
    {"id": "carbon_cutter", "name": "Carbon Cutter", "emblem": "arrow", "color": "#5B4B8A",
     "blurb": "Finish a month at least 20% below last month (compared day for day).", "rule": rule_carbon_cutter},
]

BADGES_BY_ID = {b["id"]: b for b in BADGES}


def evaluate_badges(month_purchases, all_purchases, summary, prev_summary):
    """Run every rule and return JSON-friendly results (rules stripped out)."""
    ctx = BadgeContext(month_purchases, all_purchases, summary, prev_summary)
    results = []
    for badge in BADGES:
        progress, hint = badge["rule"](ctx)
        progress = round(max(0.0, min(progress, 1.0)), 3)
        results.append({
            "id": badge["id"], "name": badge["name"], "blurb": badge["blurb"],
            "emblem": badge["emblem"], "color": badge["color"],
            "progress": progress, "earned": progress >= 1.0, "hint": hint,
            "on_track": hint.startswith("On track"), "lifetime": badge["id"] == "first_step",
        })
    return results
