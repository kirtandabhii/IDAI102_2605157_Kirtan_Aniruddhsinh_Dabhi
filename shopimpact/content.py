"""Friendly words: eco tips (shown after each purchase) and quotes."""

import random

# Tips are grouped so a tip can relate to what was just bought.
ECO_TIPS = {
    "fashion": [
        "Wearing a garment for nine extra months can shrink its carbon, water and waste footprint by about a fifth.",
        "Washing at 30°C and air-drying keeps clothes looking new for longer and saves energy.",
        "Bamboo grows fast without fertiliser, but bamboo fabric is often chemically processed — look for FSC or OEKO-TEX labels.",
        "A cobbler resole can give a good pair of shoes years of extra life.",
    ],
    "food": [
        "Per kilo, beef has roughly ten times the footprint of chicken and far more than beans or lentils.",
        "Planning meals before you shop is one of the easiest ways to waste less food.",
        "Buying loose fruit and veg lets you take only what you need, with no plastic tray.",
        "Frozen veg is picked at its peak and rarely wasted — a quietly green choice.",
    ],
    "tech": [
        "Most of a smartphone's lifetime footprint comes from making it, so keeping it an extra year really counts.",
        "A new battery or screen is usually a fraction of the cost — and carbon — of a new device.",
        "Unplugged chargers still sip power. Switch them off at the wall.",
    ],
    "home": [
        "Concentrated cleaners ship less water, so each bottle carries less freight.",
        "Second-hand solid-wood furniture often outlasts new flat-pack pieces.",
        "A borrowed drill beats a bought one: most are used for only a few minutes in their life.",
    ],
    "care": [
        "Shampoo bars skip the plastic bottle and the water weight inside it.",
        "Refill stations for soap and lotion are popping up in many high streets.",
    ],
    "travel": [
        "For trips under about 700 km, the train often matches door-to-door flight times.",
        "Car-sharing for the school or work run halves the fuel per person.",
        "Gentle acceleration and correct tyre pressure can noticeably cut fuel use.",
    ],
    "leisure": [
        "Library cards are the lowest-carbon way to read — and they're free.",
        "Experiences make memorable gifts with almost no materials at all.",
        "Toy libraries and swap groups let kids rotate toys without buying new ones.",
    ],
    "general": [
        "The greenest product is often the one you already own.",
        "Waiting 48 hours before a non-essential purchase helps you buy what you really want.",
        "Buying fewer, better things saves money and carbon at the same time.",
        "Repair cafés fix kettles, lamps and clothes for free in many towns.",
    ],
}

QUOTES = [
    ("Buy less, choose well, make it last.", "Vivienne Westwood"),
    ("The greatest threat to our planet is the belief that someone else will save it.", "Robert Swan"),
    ("We don't need a handful of people doing zero waste perfectly. "
     "We need millions of people doing it imperfectly.", "Anne-Marie Bonneau"),
    ("What you do makes a difference, and you have to decide what kind of difference you want to make.",
     "Jane Goodall"),
    ("Every time you spend money, you're casting a vote for the kind of world you want.", "Anna Lappé"),
    ("There is no such thing as 'away'. When we throw anything away it must go somewhere.", "Annie Leonard"),
    ("The earth is what we all have in common.", "Wendell Berry"),
]

# What the app says after each purchase, by impact tier.
REWARD_MESSAGES = {
    "low": ["A light choice — the turtle drew you a sprig.", "Low impact. Nicely done.",
            "That one barely leaves a mark."],
    "medium": ["A middle-of-the-road step.", "Not bad — there may be a lighter option next time.",
               "Logged. Have a look at the greener swap."],
    "high": ["A heavier footprint. A swap could cut it a lot.", "Logged — this one is carbon-heavy.",
             "Big impact. The swap below shows a lighter route."],
}


def random_tip(group=None, rng=random):
    """A tip related to the product group, sometimes a general one."""
    pool = list(ECO_TIPS.get(group, [])) + ECO_TIPS["general"]
    return rng.choice(pool)


def random_quote(rng=random):
    text, author = rng.choice(QUOTES)
    return {"text": text, "author": author}


def reward_message(tier, rng=random):
    return rng.choice(REWARD_MESSAGES.get(tier, REWARD_MESSAGES["medium"]))
