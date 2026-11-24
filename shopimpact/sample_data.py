"""A realistic sample month so new users (and testers) can explore instantly.

It mixes cheap and expensive, eco and non-eco purchases — the Stage 4 test
plan in the brief asks for 10-15 of exactly this kind of entry. Prices are
written in £ and converted to the shopper's currency.
"""

from datetime import date

from .catalog import CURRENCIES
from .engine import shift_month

# (day, product type, brand, price in £, note)
THIS_MONTH = [
    (1, "grocery_mixed", "Migros", 46.20, "Weekly shop"),
    (2, "second_hand_clothing", "Carousell", 14.00, "Wool jumper"),
    (3, "train", "SBB", 38.50, "Weekend trip"),
    (5, "fast_fashion", "Zudio", 39.99, "Party top"),
    (7, "local_produce", "Whole Foods Market", 22.80, "Veg box"),
    (8, "new_electronics", "boAt", 59.00, "Wireless earbuds"),
    (10, "plant_dairy", "Oatly", 6.40, "Oat milk x4"),
    (12, "beef_lamb", "Licious", 12.40, "Sunday roast"),
    (13, "used_books", "ThriftBooks", 7.50, "Three books"),
    (15, "eco_cleaning", "Blueland", 9.00, "Laundry refills"),
    (17, "zero_waste_care", "Bare Necessities", 12.50, "Shampoo bar"),
    (18, "bottled_drinks", "Coca-Cola", 8.20, "Party drinks"),
    (20, "refurbished_electronics", "Back Market", 89.00, "Refurbished tablet"),
    (21, "plant_protein", "Planted", 5.60, "Plant chicken & lentils"),
    (23, "public_transport", "SMRT", 25.00, "Travel card top-up"),
]

LAST_MONTH = [
    (3, "flight", "IndiGo", 89.00, "Weekend away"),
    (6, "fast_fashion", "H&M", 55.00, "Jeans"),
    (9, "grocery_mixed", "FairPrice", 52.30, "Weekly shop"),
    (14, "leather_shoes", "Clarks", 75.00, "Work shoes"),
    (19, "dairy", "Amul", 11.40, "Cheese & butter"),
    (22, "small_gadgets", "Amazon", 24.99, "Phone stand"),
    (26, "second_hand_clothing", "Depop", 18.00, "Denim jacket"),
]


def _local_price(gbp, currency):
    """Convert a £ price and round it the way shops price things."""
    value = gbp / CURRENCIES[currency]["to_gbp"]
    if value >= 1000:
        return float(round(value / 10) * 10 - 1)   # e.g. 5,191 -> 5,189
    if value >= 100:
        return float(round(value)) - (0.01 if currency != "INR" else 0)
    return round(value, 2)


def build(today=None, currency="GBP"):
    """Purchase dicts for this month (up to today) and the whole of last month."""
    today = today or date.today()
    if currency not in CURRENCIES:
        currency = "GBP"
    this_key = today.strftime("%Y-%m")
    last_key = shift_month(this_key, -1)

    def row(key, day, ptype, brand, price, note):
        return {"product_type": ptype, "brand": brand, "price": _local_price(price, currency),
                "currency": currency, "date": f"{key}-{day:02d}", "note": note}

    rows = [row(last_key, *r) for r in LAST_MONTH]                       # oldest first, as if logged
    rows += [row(this_key, *r) for r in THIS_MONTH if r[0] <= today.day]  # never log the future
    return rows
