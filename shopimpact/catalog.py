"""The curated knowledge base behind ShopImpact.

Every product type carries a *multiplier*: an approximate kilograms of CO2e
emitted per £1 spent (a "spend-based emission factor"). The figures are
rounded, awareness-level estimates inspired by published spend-based factors
and lifecycle studies — good for comparing choices, not for carbon accounting.

Estimated impact of a purchase = price (converted to £) x multiplier.

Real brands and shops live in brands.py; countries and rates in world.py.
"""

import math

from .world import COUNTRIES, PER_USD, POPULAR, SYMBOLS

# ---------------------------------------------------------------------------
# Impact tiers — a multiplier at or below the limit falls into that tier.
# ---------------------------------------------------------------------------
TIER_LIMITS = {"low": 0.30, "medium": 0.80}  # anything above 0.80 is "high"

TIERS = {
    "low": {"label": "Low impact", "short": "Low"},
    "medium": {"label": "Medium impact", "short": "Medium"},
    "high": {"label": "High impact", "short": "High"},
}

# ---------------------------------------------------------------------------
# Currencies — every currency in the world (see world.py). Prices are
# converted to £ before the multiplier is applied, so a ₹2,000 purchase is not
# treated like a £2,000 one. `slider` is the till's price-tag range:
# (maximum, step) — roughly £1,000 in that currency, in friendly steps.
# ---------------------------------------------------------------------------
def _nice_ceil(value):
    """Round up to 1, 1.5, 2, 2.5, 3, 4, 5, 6, 8 x a power of ten."""
    magnitude = 10 ** math.floor(math.log10(value))
    for m in (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if value <= m * magnitude * (1 + 1e-9):
            return m * magnitude
    return 10 * magnitude


def _slider_for(to_gbp):
    step = 1
    if to_gbp < 0.05:  # small units (₹, ¥, Rp…): step by 1, 5, 10, 50, 100…
        raw = 0.1 / to_gbp
        magnitude = 10 ** math.floor(math.log10(raw))
        step = int(5 * magnitude if raw / magnitude >= 5 else magnitude)
    maximum = _nice_ceil(1000 / to_gbp)
    maximum = max(step * 20, round(maximum / step) * step)
    return (int(maximum), step)


def build_currencies(per_usd):
    """Turn 'units per US dollar' into what the app needs, keyed by ISO code."""
    gbp_per_usd = per_usd["GBP"]
    currencies = {}
    for code in sorted(per_usd):
        to_gbp = gbp_per_usd / per_usd[code]
        currencies[code] = {"symbol": SYMBOLS.get(code, code), "name": code,
                            "to_gbp": round(to_gbp, 9), "slider": _slider_for(to_gbp)}
    return currencies


CURRENCIES = build_currencies(PER_USD)


def update_rates(per_usd):
    """Apply fresh rates (units per US dollar) — used by rates.py."""
    merged = dict(PER_USD)
    merged.update({c: float(r) for c, r in per_usd.items() if c in PER_USD and float(r) > 0})
    for code, info in build_currencies(merged).items():
        CURRENCIES[code].update(info)

# ---------------------------------------------------------------------------
# Product groups (used for the dashboard breakdown and icons).
# ---------------------------------------------------------------------------
GROUPS = {
    "fashion": {"name": "Clothing & shoes", "icon": "shirt"},
    "food": {"name": "Food & drink", "icon": "basket"},
    "tech": {"name": "Electronics", "icon": "plug"},
    "home": {"name": "Home & garden", "icon": "home"},
    "care": {"name": "Personal care", "icon": "drop"},
    "travel": {"name": "Travel & transport", "icon": "route"},
    "leisure": {"name": "Books, toys & hobbies", "icon": "gift"},
    "services": {"name": "Services & subscriptions", "icon": "wrench"},
}


# ---------------------------------------------------------------------------
# Product types
#   name        what the shopper sees
#   group       one of GROUPS
#   multiplier  kg CO2e per £1
#   swap_to     the greener product type we suggest (None = already a good pick)
#   swap_why    one friendly sentence explaining the swap
#   ideas       greener options that are not brands (brands come from brands.py)
#   tags        flags used by badge rules ("second_life", "plant")
# ---------------------------------------------------------------------------
def _t(name, group, multiplier, swap_to=None, swap_why="", ideas=(), tags=()):
    return {"name": name, "group": group, "multiplier": multiplier, "swap_to": swap_to,
            "swap_why": swap_why, "ideas": list(ideas), "tags": list(tags)}


PRODUCT_TYPES = {
    # --- Clothing & shoes ---------------------------------------------------
    "fast_fashion": _t("New clothing (fast fashion)", "fashion", 0.90, "second_hand_clothing",
                       "Pre-loved clothes skip the factory, the dye house and the shipping.",
                       ["A clothes swap with friends", "A charity shop"]),
    "premium_clothing": _t("Premium & designer clothing", "fashion", 0.55, "second_hand_clothing",
                           "Well-made pieces last — and pre-owned designer costs the planet almost nothing."),
    "sportswear": _t("Sportswear & activewear", "fashion", 0.80, "second_hand_clothing",
                     "Most activewear is polyester made from oil; barely-worn kit is easy to find."),
    "ethnic_handloom": _t("Handloom & ethnic wear", "fashion", 0.30, None, "",
                          ["Handloom from local weavers", "Khadi"]),
    "organic_clothing": _t("Organic or recycled clothing & textiles", "fashion", 0.35, "second_hand_clothing",
                           "Organic is a good step — second-hand is the lightest step of all."),
    "second_hand_clothing": _t("Second-hand clothing", "fashion", 0.08, None, "",
                               ["Charity and thrift shops", "Clothes swaps"], ["second_life"]),
    "clothing_rental": _t("Rented or borrowed outfits", "fashion", 0.06, None, "",
                          ["Borrow from a friend"], ["second_life"]),
    "leather_shoes": _t("Leather shoes", "fashion", 1.20, "eco_footwear",
                        "Leather carries the footprint of cattle farming; recycled and plant-based soles avoid most of it.",
                        ["A cobbler resole"]),
    "trainers": _t("New trainers & sneakers", "fashion", 0.85, "eco_footwear",
                   "Trainers mix plastics, rubber and glue; recycled-material pairs cut much of that."),
    "eco_footwear": _t("Recycled or plant-based shoes", "fashion", 0.40, "second_hand_clothing",
                       "Even greener: a barely-worn second-hand pair."),
    "bags_accessories": _t("Bags, eyewear & accessories", "fashion", 0.70, "upcycled_goods",
                           "Bags made from old truck tarps, tyres or fire hoses give waste a second life."),
    "upcycled_goods": _t("Upcycled & recycled-material goods", "fashion", 0.12, None, "",
                         ["Local upcyclers and makers"], ["second_life"]),
    "jewellery_watches": _t("Watches & jewellery", "fashion", 0.45, "preloved_luxury",
                            "Mining gold and gems is energy-hungry; pre-owned pieces need none of it."),
    "preloved_luxury": _t("Pre-owned watches & jewellery", "fashion", 0.05, None, "",
                          ["Certified pre-owned dealers"], ["second_life"]),

    # --- Food & drink -------------------------------------------------------
    "beef_lamb": _t("Beef & lamb", "food", 2.60, "plant_protein",
                    "Beans, lentils and tofu deliver protein for a small fraction of the emissions."),
    "chicken_pork": _t("Chicken & pork", "food", 0.95, "plant_protein",
                       "Lighter than beef, but pulses and tofu are lighter still."),
    "fish_seafood": _t("Fish & seafood", "food", 0.85, "plant_protein",
                       "Trawling and farmed prawns are carbon-heavy; plant protein and local veg are not."),
    "dairy": _t("Dairy & cheese", "food", 1.10, "plant_dairy",
                "Oat and soy milks need far less land and produce far less methane."),
    "plant_protein": _t("Plant protein (beans, tofu, dal)", "food", 0.25, None, "",
                        ["Dried pulses and lentils"], ["plant"]),
    "plant_dairy": _t("Plant milk & yoghurt", "food", 0.30, None, "", [], ["plant"]),
    "grocery_mixed": _t("Mixed groceries", "food", 0.60, "local_produce",
                        "Seasonal, local produce avoids heated greenhouses and air freight."),
    "packaged_snacks": _t("Snacks, chocolate & sweets", "food", 0.65, "bulk_groceries",
                          "Buying loose nuts and fruit cuts plastic wrappers and processing."),
    "bulk_groceries": _t("Loose & bulk-bin groceries", "food", 0.28, None, "",
                         ["Bring your own jars"], ["plant"]),
    "local_produce": _t("Local, seasonal fruit & veg", "food", 0.15, None, "",
                        ["Farmers' markets", "Your local sabzi-wala or hawker stall"], ["plant"]),
    "rice_grains": _t("Rice, flour & grains", "food", 0.45, "bulk_groceries",
                      "Paddy rice releases methane; millets and loose grains are lighter choices."),
    "coffee_tea": _t("Coffee & tea", "food", 0.70, "bulk_groceries",
                     "Loose-leaf tea and refillable beans skip pods and packaging."),
    "bottled_drinks": _t("Bottled & canned drinks", "food", 0.50, "refill_drinks",
                         "A refillable bottle removes the packaging and the delivery lorry."),
    "refill_drinks": _t("Refills & reusable bottles", "food", 0.10, None, "",
                        ["Tap water", "Refill stations"]),
    "alcohol": _t("Beer, wine & spirits", "food", 0.55, None, "", ["Local breweries"]),
    "takeaway_delivery": _t("Takeaway & food delivery", "food", 0.65, "rescued_food",
                            "Surplus-food bags rescue meals that would otherwise be thrown away."),
    "restaurant_meal": _t("Restaurant & café meals", "food", 0.45, "plant_meal_out",
                          "A plant-based dish usually has a fraction of the footprint of a meat one."),
    "plant_meal_out": _t("Plant-based meals out", "food", 0.22, None, "", [], ["plant"]),
    "rescued_food": _t("Rescued surplus food", "food", 0.08, None, "", []),

    # --- Electronics --------------------------------------------------------
    "new_electronics": _t("New phones, laptops & tablets", "tech", 0.60, "refurbished_electronics",
                          "Most of a device's lifetime footprint comes from making it — refurbished skips that."),
    "tv_appliances": _t("TVs & large appliances", "tech", 0.55, "refurbished_electronics",
                        "Refurbished appliances come tested and save a whole manufacturing run."),
    "small_gadgets": _t("Small gadgets & accessories", "tech", 0.75, "refurbished_electronics",
                        "Cheap gadgets break fast; a refurbished, repairable one lasts."),
    "gaming": _t("Games consoles & accessories", "tech", 0.60, "refurbished_electronics",
                 "Pre-owned consoles play exactly the same games."),
    "refurbished_electronics": _t("Refurbished electronics", "tech", 0.15, None, "", [], ["second_life"]),

    # --- Home & garden ------------------------------------------------------
    "new_furniture": _t("New furniture", "home", 0.70, "second_hand_furniture",
                        "Solid second-hand furniture often outlives flat-pack — and has no new timber cost."),
    "second_hand_furniture": _t("Second-hand furniture & homeware", "home", 0.10, None, "",
                                ["Freecycle groups"], ["second_life"]),
    "home_textiles": _t("Bedding & home textiles", "home", 0.70, "organic_clothing",
                        "Organic cotton and recycled fibres skip pesticides and virgin plastic."),
    "kitchenware": _t("Kitchenware & homeware", "home", 0.55, "second_hand_furniture",
                      "Pots, pans and crockery last decades — pre-loved ones are as good as new."),
    "cleaning": _t("Cleaning & laundry products", "home", 0.45, "eco_cleaning",
                   "Concentrates and refills ship less water and less plastic."),
    "eco_cleaning": _t("Refill & concentrated cleaners", "home", 0.15, None, "", ["Refill stations"]),
    "paper_products": _t("Toilet paper & tissues", "home", 0.50, "recycled_paper",
                         "Recycled or bamboo paper spares virgin forests."),
    "recycled_paper": _t("Recycled or bamboo paper products", "home", 0.18, None, ""),
    "diy_hardware": _t("DIY & hardware", "home", 0.50, None, "", ["A tool library", "Borrow from a neighbour"]),
    "plants_garden": _t("Plants & gardening", "home", 0.20, None, "", ["Seed swaps"]),
    "flowers": _t("Cut flowers", "home", 0.60, "plants_garden",
                  "Potted plants live on; imported cut roses are often flown in."),

    # --- Personal care ------------------------------------------------------
    "cosmetics": _t("Cosmetics & toiletries", "care", 0.50, "zero_waste_care",
                    "Solid bars are mostly product, not water and plastic bottle."),
    "zero_waste_care": _t("Solid & refillable toiletries", "care", 0.15, None, "", ["Refill stations"]),
    "pharmacy": _t("Medicines & pharmacy", "care", 0.35, None, ""),

    # --- Travel & transport -------------------------------------------------
    "flight": _t("Short-haul flight", "travel", 1.80, "train",
                 "For trips under ~700 km, the train usually emits a small fraction per passenger."),
    "long_haul": _t("Long-haul flight", "travel", 1.40, "staycation",
                    "A trip closer to home can be just as restful for a fraction of the carbon."),
    "fuel": _t("Petrol or diesel", "travel", 1.60, "public_transport",
               "A full bus or a bike moves you for a sliver of the fuel."),
    "taxi_ride": _t("Taxi & ride-hailing", "travel", 0.55, "public_transport",
                    "Metro, bus or bike gets you there for much less carbon."),
    "car_rental": _t("Car rental", "travel", 0.75, "car_sharing",
                     "Shared and electric cars are used more and pollute less per trip."),
    "car_sharing": _t("Car sharing & EV rental", "travel", 0.25, None, ""),
    "ev_charging": _t("EV charging", "travel", 0.20, None, "", ["Charge when the grid is greenest"]),
    "train": _t("Train ticket", "travel", 0.12, None, ""),
    "public_transport": _t("Bus, metro & bike share", "travel", 0.08, None, "", ["Walk or cycle"]),
    "hotel": _t("Hotels & holiday stays", "travel", 0.35, "staycation",
                "Eco-certified and local stays use less energy and keep money in the community."),
    "staycation": _t("Local trips & eco-stays", "travel", 0.18, None, ""),

    # --- Books, toys & hobbies ----------------------------------------------
    "new_books": _t("New books & magazines", "leisure", 0.25, "used_books",
                    "A library card or a pre-loved copy needs no new paper at all."),
    "used_books": _t("Second-hand & library books", "leisure", 0.03, None, "",
                     ["Your local library"], ["second_life"]),
    "plastic_toys": _t("Plastic toys & gifts", "leisure", 0.80, "eco_toys",
                       "Wooden and recycled toys last longer and avoid virgin plastic."),
    "eco_toys": _t("Wooden or recycled toys", "leisure", 0.25, None, "", ["Toy libraries"]),
    "sports_gear": _t("Sports & fitness gear", "leisure", 0.60, "second_hand_goods",
                      "Bikes, rackets and weights are built to last — second-hand ones work just as well."),
    "stationery": _t("Stationery & art supplies", "leisure", 0.50, "recycled_paper",
                     "Recycled-paper notebooks and refillable pens cut waste."),
    "pet_supplies": _t("Pet food & supplies", "leisure", 0.85, None, "",
                       ["Buy food in bulk bags"]),
    "second_hand_goods": _t("Second-hand goods (marketplaces)", "leisure", 0.06, None, "",
                            ["Neighbourhood swap groups"], ["second_life"]),
    "experience_gift": _t("Experiences & gift cards", "leisure", 0.20, None, "",
                          ["A cooking class", "A museum pass"]),
    "events_tickets": _t("Concerts, cinema & events", "leisure", 0.15, None, ""),

    # --- Services & subscriptions -------------------------------------------
    "device_repair": _t("Device & appliance repair", "services", 0.05, None, "",
                        ["Repair cafés"], ["second_life"]),
    "salon": _t("Haircuts & salon", "services", 0.12, None, ""),
    "gym_fitness": _t("Gym & fitness classes", "services", 0.10, None, ""),
    "streaming": _t("Streaming & digital subscriptions", "services", 0.10, None, ""),
}


def tier_for(multiplier):
    """Classify a multiplier as 'low', 'medium' or 'high' impact."""
    if multiplier <= TIER_LIMITS["low"]:
        return "low"
    if multiplier <= TIER_LIMITS["medium"]:
        return "medium"
    return "high"


def catalog_payload():
    """Product types, groups, currencies and countries in a JSON-friendly shape."""
    types = []
    for type_id, info in PRODUCT_TYPES.items():
        swap = info["swap_to"]
        types.append({
            "id": type_id,
            "name": info["name"],
            "group": info["group"],
            "multiplier": info["multiplier"],
            "tier": tier_for(info["multiplier"]),
            "swap_to": swap,
            "swap_name": PRODUCT_TYPES[swap]["name"] if swap else None,
            "swap_multiplier": PRODUCT_TYPES[swap]["multiplier"] if swap else None,
            "swap_why": info["swap_why"],
            "ideas": info["ideas"],
            "tags": info["tags"],
        })
    groups = [{"id": gid, **g} for gid, g in GROUPS.items()]
    currencies = [{"code": c, "symbol": v["symbol"], "name": v["name"], "to_gbp": v["to_gbp"],
                   "slider_max": v["slider"][0], "slider_step": v["slider"][1]}
                  for c, v in CURRENCIES.items()]
    return {"types": types, "groups": groups, "currencies": currencies,
            "countries": COUNTRIES, "popular_countries": POPULAR,
            "tiers": TIERS, "tier_limits": TIER_LIMITS}
