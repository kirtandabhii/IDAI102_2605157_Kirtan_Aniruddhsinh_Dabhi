# ShopImpact — conscious shopping dashboard (Streamlit)

ShopImpact turns everyday shopping into a calm, eco-conscious habit. Log a purchase (product type, brand, price) and the app instantly estimates its CO₂ footprint, prints a till receipt, and has a **Python turtle** stamp it with a leaf, a footprint or a badge. A monthly dashboard tracks spend, carbon and an eco score. Greener swaps are suggested for every product type, and badges reward lighter choices.

Built with **Streamlit** for the WACP Year 1 Python Programming summative assessment (Scenario 1).

> **Live app:** _add your Streamlit Community Cloud URL here_
> **Screenshots:** _add images to `docs/screenshots/` and link them here_
> **Design document:** [docs/design.md](docs/design.md) — users, feature plan, wireframes, palette, logic design
> **Testing log:** [docs/testing.md](docs/testing.md) — 63 automated tests, 29 purchase scenarios, fixes and user feedback

---

## What it does

| Brief requirement | Where it lives in ShopImpact |
| --- | --- |
| Input fields: product type, price, brand | The **till** on the Overview: `st.selectbox` with **77 product types**, `st.selectbox` with **461 real brands and shops** (you can also type your own), `st.number_input` for the price plus a draggable **price tag** (`st.select_slider`), `st.date_input` and an optional item name |
| Real-time CO₂ calculation | Every change reruns the script and the estimate strip updates: kg CO₂e, impact tier, the formula (`£85.00 × 1.20 kg/£`) and "feels like" km driven / phone charges |
| Monthly dashboard of spend and CO₂ | `st.metric` cards (footprint vs a budget ring, spend vs budget, eco score A–E, real-world equivalents) and an **Altair month curve** against your budget, with an end-of-month projection and hover details |
| Fun badges ("Eco Saver", "Low Impact Shopper") | 10 badges with clear rules: Eco Saver of the Month, Low Impact Shopper, Second-Life Hero, Ethical Brand Ally, Green Streak, Plant Powered, Mindful Spender, Swap Master, Carbon Cutter, First Step |
| Greener alternatives for each product type | Every type has a greener swap and greener brands (with logos). Take a swap before buying (in the till) or after (Ledger → Swap). A "Greener brands & shops" wall lists 100+ lower-impact names |
| Turtle graphics on eco-friendly choices | A sprig (light buy), light footprints (medium) or a deep footprint (heavy) on each receipt; a rosette drawn for every badge; a recursive **tree** that grows with your month |
| Optional: random eco tips | A tip on every receipt plus a rotating "Did you know" card |
| Optional: dark / high-contrast mode | Daylight, Night canopy and High-contrast themes (`st.segmented_control`), plus a Large-text option |
| Optional: motivational quotes | Quote card in the Garden view |

### Streamlit features used

`st.selectbox` (incl. `accept_new_options`), `st.number_input`, `st.select_slider`, `st.slider`, `st.date_input`, `st.text_input`, `st.button` (with icons and callbacks), `st.pills`, `st.segmented_control`, `st.toggle`, `st.metric`, `st.altair_chart`, `st.dialog`, `st.toast`, `st.download_button`, `st.file_uploader`, `st.columns`, keyed `st.container`s, `st.session_state`, `st.query_params`, `st.cache_resource`, `st.context.timezone`, and `st.html` for the receipt printer and turtle animations.

### Extras beyond the brief

- **Real brands with logos**: 461 brands and shops sold in India, Singapore, Switzerland and the United States, such as Zudio, Westside, Myntra, Amul, FairPrice, Shopee, Carousell, Migros, Coop, Galaxus, Freitag, Walmart, Target, Patagonia and ThredUp.
- **Price tag with "tuck" sounds**: drag the tag and the price follows, with a soft wooden *tuck* at every step (45, 46, 47…) and a firmer one every 10 steps. Everyday prices get the finest control.
- **Synthesised sound design**: marimba till chimes, thermal-printer chatter, a pen scratch while the turtle draws, and a fanfare for badges. Everything is generated live with the Web Audio API, so there are no audio files.
- **What-if simulator**: drag a slider to see the CO₂ and eco score if you swapped a share of this month's heavier buys.
- **Ledger** with search, impact filters (`st.pills`), sorting, one-click greener swaps, delete with **Undo**, and **CSV export**.
- **Every country and currency**: 235 countries and 153 currencies. Picking a country switches the currency. Rates refresh daily from [ExchangeRate-API](https://www.exchangerate-api.com), with a built-in fallback.
- **Backup & restore**: download all your data as JSON and restore it later. This is useful because Streamlit Cloud storage is temporary.
- **Responsive**: a navigation rail on desktop and a bottom tab bar on phones.

---

## How the numbers work

Each product type has a **multiplier**: approximate kg CO₂e per £1 spent (a spend-based emission factor).

```
CO₂ of a purchase (kg) = price converted to £ × multiplier        (frozen when you log it)
intensity               = month's kg CO₂e ÷ month's £ spent
eco score (0–100)       = 100 × (1 − min(intensity / 1.2, 1)),
                          then × budget ÷ footprint if the month is over its CO₂ budget
```

- Impact tiers: **low** ≤ 0.30 kg/£, **medium** ≤ 0.80 kg/£, **high** above that.
- Each purchase keeps the exchange rate, £ value and CO₂ it was logged with, so a later rate update never rewrites history.
- Each month keeps the budget it was planned with, so changing a budget never rewrites past months.
- A swap assumes the same spend ("same money, lighter choice"), and the app says so.
- The figures are rounded, awareness-level estimates for comparing choices, not a carbon audit.

### Badge rules (fair by design)

- Only purchases worth about **£1 or more** count, so badges can't be farmed with 1p entries.
- **Eco Saver of the Month**, **Mindful Spender** and **Carbon Cutter** judge a whole month. They show *on track* during the month and lock in when it ends. You're congratulated the next time you open the app.
- **Carbon Cutter** compares like with like: this month so far against last month **up to the same day**.
- **First Step** is a lifetime badge and is labelled as one.
- **Low Impact Shopper** uses the same 0.30 kg/£ line as the low-impact tier.

---

## Project structure

```
app.py                      Streamlit app: page set-up, private link, routing (main file)
shopimpact/
  service.py                every rule in one place: validation, frozen CO₂, budgets, badges
  engine.py                 the maths: pure functions on lists of dicts
  badges.py                 badge rules (each returns progress 0–1 and a hint)
  catalog.py                77 product types, multipliers, greener swaps, currencies
  brands.py                 461 real brands & shops with domains for logos
  world.py                  235 countries -> currency, built-in exchange rates
  rates.py                  daily live exchange-rate refresh (background)
  logos.py                  brand logo fetcher with monogram fallback
  turtle_svg.py             SvgTurtle: the turtle API recorded and rendered as SVG
  drawings.py               sprig / footprints / badge rosettes / recursive tree
  turtle_window.py          draws the same artwork in a real Python turtle window
  store.py                  SQLite storage (purchases, settings, budgets, awards)
  content.py, sample_data.py
  ui/
    views.py                the six screens, built from Streamlit widgets
    theme.py, style.css     design tokens and the stylesheet for Streamlit's widgets
    charts.py               Altair month curve and six-month trend
    html.py                 display-only cards (receipt, lists, badge art)
    runtime.js              browser side: sounds, turtle playback, receipt printer
    logo_cache.py           logos as data URIs
tests/
  test_engine.py            58 unit + API tests (maths, badges, validation, turtle, backup)
  test_streamlit_app.py     5 headless Streamlit AppTest tests (screens, ring-up flow)
docs/                     design document, testing log, screenshots
web_app.py, templates/, static/   optional standalone web edition (Flask), same Python logic
```

### Python data structures

- **Purchases** are a `list` of `dict`s: `{"product_type", "brand", "price", "currency", "date", "price_gbp", "co2", "rate", "note", "swapped_from"}`. `engine.enrich()` adds derived fields (tier, swap suggestion, equivalents).
- **Catalogue**: `PRODUCT_TYPES` is a `dict` of dicts (name, group, multiplier, swap, ideas, tags) across 8 groups.
- **Brands**: a list of tuples `(name, domain, countries, product types, kind, greener)`, built into dicts with a name-lookup `dict`.
- **Badges**: a `list` of dicts, each holding a `rule` function. `evaluate_badges()` runs every rule against a `BadgeContext`.
- **Monthly summary**: `engine.monthly_summary()` groups by tier and product group, builds a cumulative daily series, finds the biggest swaps, computes the what-if table and projects the month-end total.

### Turtle graphics — integration details

Python's `turtle` module draws into a Tk window, which doesn't exist on a web server (or on Streamlit Cloud). `shopimpact/turtle_svg.py` re-implements the turtle API (`forward`, `left`, `circle`, `begin_fill`, `dot`, `goto`, …) and **records every move in order**. The page then replays those strokes one by one while a small turtle walks the path.

Because the API is the same, every drawing function in `drawings.py` also runs unchanged on a real `turtle.Turtle()` (verified for all five drawings):

```bash
python -m shopimpact.turtle_window sprig
python -m shopimpact.turtle_window badge star
python -m shopimpact.turtle_window tree 82
```

---

## Run it locally

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py             # http://localhost:8501
```

Run the tests:

```bash
python -m unittest discover tests
```

---

## Deploy to Streamlit Community Cloud

1. Push this folder to a GitHub repository named as the brief requires, e.g. `IDAI102<StudentID>-<StudentName>`. `app.py` and `requirements.txt` sit at the top level.
2. Go to [share.streamlit.io](https://share.streamlit.io) → **Create app** → *Deploy a public app from GitHub*.
3. Pick the repository and branch, set **Main file path** to `app.py`, and under *Advanced settings* choose **Python 3.12**.
4. Click **Deploy**, then paste the live URL at the top of this README.

**Your data on Streamlit Cloud:** each visitor gets a private link (`?id=…`) that the browser also remembers. Purchases are stored in SQLite on the app's disk, which Streamlit Cloud may reset when the app restarts or redeploys. Use **Settings → Download a full backup** to keep a copy, and **Restore from a backup** to bring it back.

**Other hosts:** `Procfile`, `render.yaml` and `Dockerfile` all run the same Streamlit app (`streamlit run app.py --server.port $PORT`). The optional web edition runs with `gunicorn web_app:app`.

**Environment switches:** `SHOPIMPACT_DB` (database path), `SHOPIMPACT_LIVE_RATES=0` (built-in rates only), `SHOPIMPACT_LOGOS=0` (monograms only, no network).

---

## Design notes

- **Users**: students, young adults and eco-curious families. The goal is awareness and fun, not guilt. High-impact purchases are described plainly ("a heavier footprint") and always paired with a lighter route.
- **Palette**: lichen-green paper, moss ink and glacier blue. Fern, ochre and clay are used **only** for impact tiers, so colour always carries meaning. Text colours meet WCAG AA contrast.
- **Type**: Bricolage Grotesque (display), Figtree (body, large and friendly) and Martian Mono (receipts and figures).
- **Signature element**: the till and receipt printer. Every purchase prints a real-feeling receipt with a CO₂ line, and the turtle stamps it.
- **Ethics**: estimates are labelled as approximate, and data stays anonymous. Brand suggestions point to second-hand, refurbished, refill and certified options rather than pushing more consumption. Logos are shown only to identify each brand and remain their owners' trademarks.
