"""ShopImpact — a conscious shopping companion.

Package layout (each module does one job):

    catalog.py     product types, CO2 multipliers, greener swaps, currencies
    world.py       every country, its currency and built-in exchange rates
    rates.py       daily live exchange-rate refresh (falls back to built-in)
    brands.py      461 real brands and shops, with logo domains
    logos.py       brand logo fetcher with monogram fallback
    engine.py      impact maths: per-purchase CO2, monthly dashboard summaries
    badges.py      the rules that award badges
    turtle_svg.py  a turtle-graphics pen that records moves and renders SVG
    drawings.py    leaf / footprint / badge / tree drawings (turtle API only)
    content.py     eco tips and motivational quotes
    store.py       SQLite persistence for purchases, settings and awards
    sample_data.py a realistic demo month for testing the app
"""

__version__ = "1.1.0"
