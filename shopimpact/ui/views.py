"""The six screens of the Streamlit app, built from Streamlit widgets.

Callbacks never calculate anything themselves — they hand the shopper's input
to shopimpact.service (validation, CO2, badges) and store the result in
st.session_state for the next run to show.
"""

import math
import uuid
from datetime import date, datetime
from functools import lru_cache

import streamlit as st

from .. import drawings
from ..badges import BADGES
from ..brands import BRANDS, BY_NAME
from ..catalog import CURRENCIES, GROUPS, PRODUCT_TYPES, catalog_payload, tier_for
from ..content import ECO_TIPS, QUOTES
from ..engine import estimate, month_key, shift_month
from ..service import ValidationError
from ..world import COUNTRIES, COUNTRY_BY_CODE, POPULAR
from . import charts, html
from .logo_cache import prefetch
from .theme import THEME_NAMES

VIEWS = [  # (key, label, material icon)
    ("overview", "Overview", ":material/space_dashboard:"),
    ("ledger", "Ledger", ":material/receipt_long:"),
    ("swaps", "Swaps", ":material/swap_horiz:"),
    ("badges", "Badges", ":material/workspace_premium:"),
    ("garden", "Garden", ":material/park:"),
    ("settings", "Settings", ":material/tune:"),
]
TIPS = [tip for group in ECO_TIPS.values() for tip in group]
TYPE_IDS = list(PRODUCT_TYPES)
TYPE_NAMES = {k: v["name"] for k, v in PRODUCT_TYPES.items()}
BRAND_NAMES = sorted((b["name"] for b in BRANDS), key=str.lower)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
@lru_cache(maxsize=None)
def badge_art():
    return {b["id"]: html.svg_uri(drawings.render("badge", color=b["color"], emblem=b["emblem"], name=b["name"]))
            for b in BADGES}


@lru_cache(maxsize=None)
def reward_svg(kind):
    return drawings.render(kind)


@lru_cache(maxsize=64)
def tag_options(currency):
    """Price-tag stops on an eased scale: every step at everyday prices, bigger jumps near the top."""
    maximum, step = CURRENCIES[currency]["slider"]
    stops, positions = set(), 700
    for pos in range(positions + 1):
        stops.add(round(maximum * (pos / positions) ** 2 / step) * step)
    return tuple(sorted(stops))


def nearest(options, value):
    value = value or 0
    return min(options, key=lambda o: abs(o - value))


def greener_for(type_id, limit=4):
    names = [b["name"] for b in BRANDS if b["greener"] and type_id in b["types"]]
    return (names + PRODUCT_TYPES[type_id]["ideas"])[:limit]


def ss():
    return st.session_state


def toast(message, icon=None):
    ss().setdefault("toasts", []).append((message, icon))


def type_label(type_id):
    t = PRODUCT_TYPES[type_id]
    return f"{t['name']}  ·  {t['multiplier']:.2f} kg/£ · {tier_for(t['multiplier'])}"


# ---------------------------------------------------------------------------
# Callbacks (run before the next rerun)
# ---------------------------------------------------------------------------
def set_view(view):
    ss().view = view
    st.query_params["view"] = view


def change_month(delta):
    ss().month = shift_month(ss().month, delta)


def _on_type():
    ss().f_swapped_from = None


def _on_price():
    ss().f_tag = nearest(tag_options(ss().currency), ss().f_price)


def _on_tag():
    value = ss().f_tag
    ss().f_price = float(value) if value else None


def _take_swap(swap_to):
    ss().f_swapped_from = ss().f_type
    ss().f_type = swap_to


def _ring(service, sid, today, now_text):
    s = ss()
    data = {"product_type": s.f_type, "price": s.f_price, "brand": s.f_brand or "",
            "date": s.f_date.isoformat() if isinstance(s.f_date, date) else None,
            "note": s.f_note or "", "swapped_from": s.get("f_swapped_from")}
    try:
        result = service.add(sid, data, today)
    except ValidationError as err:
        s.form_error = str(err)
        s.error_nonce = uuid.uuid4().hex
        return
    s.form_error = ""
    s.receipt = {"nonce": uuid.uuid4().hex, "purchase": result["purchase"], "reward": result["reward"],
                 "tip": result["tip"], "fresh": True, "when": now_text}
    s.badge_queue = s.get("badge_queue", []) + result["new_badges"]
    s.month = result["state"]["month"]
    for key, value in (("f_type", None), ("f_brand", None), ("f_price", None), ("f_note", ""), ("f_swapped_from", None)):
        s[key] = value
    s.f_tag = 0


def _delete(service, sid, today, purchase_id):
    try:
        result = service.delete(sid, purchase_id, today)
    except LookupError as err:
        toast(str(err), ":material/error:")
        return
    ss().last_deleted = result["deleted"]
    toast(f"Deleted {TYPE_NAMES.get(result['deleted']['product_type'], 'purchase').lower()}.", ":material/delete:")


def _undo(service, sid, today):
    deleted = ss().pop("last_deleted", None)
    if deleted:
        service.restore(sid, deleted, today)
        toast("Purchase restored.", ":material/undo:")


def _open(dialog, value=None):
    ss().dialog = (dialog, value)


def _save_settings(service, sid, today, field, key):
    try:
        service.update_settings(sid, {field: ss()[key]}, today, ss().month)
    except ValidationError as err:
        toast(str(err), ":material/error:")
    if field == "currency":
        ss().f_price = None  # a typed price belongs to the old currency


def _save_country(service, sid, today):
    code = ss().set_country
    if code in COUNTRY_BY_CODE:
        service.update_settings(sid, {"country": code}, today, ss().month)
        c = COUNTRY_BY_CODE[code]
        ss().pop("set_currency", None)  # re-reads the new currency on the next run
        ss().f_price = None
        toast(f"{c['name']} — prices now in {c['currency']}.", ":material/public:")


def _save_ui(service, sid, field, key, transform=lambda v: v):
    value = ss()[key]
    if value is None:
        return
    service.save_ui_prefs(sid, {field: transform(value)})


def _toggle_ui(service, sid, field, prefs):
    if field == "sound":
        service.save_ui_prefs(sid, {"sound": not prefs["sound"]})
    elif field == "theme":
        service.save_ui_prefs(sid, {"theme": "light" if prefs["theme"] != "light" else "dark"})


# ---------------------------------------------------------------------------
# Rail and top bar
# ---------------------------------------------------------------------------
def rail(view, prefs, service, sid):
    with st.container(key="rail"):
        st.html(html.brand_mark())
        for key, label, icon in VIEWS:
            st.button(label, key=f"nav_{key}", icon=icon, type="primary" if view == key else "secondary",
                      on_click=set_view, args=(key,), width="stretch")
        with st.container(key="rail-foot"):
            st.button("Sound" if prefs["sound"] else "Muted", key="nav_sound", width="stretch",
                      icon=":material/volume_up:" if prefs["sound"] else ":material/volume_off:",
                      on_click=_toggle_ui, args=(service, sid, "sound", prefs), help="Sounds on/off")
            st.button("Night" if prefs["theme"] == "light" else "Day", key="nav_theme", width="stretch",
                      icon=":material/dark_mode:" if prefs["theme"] == "light" else ":material/light_mode:",
                      on_click=_toggle_ui, args=(service, sid, "theme", prefs), help="Switch daylight / night canopy")


def topbar(eyebrow, heading, state):
    left, right = st.columns([3, 1.3], vertical_alignment="bottom")
    left.html(html.title(eyebrow, heading))
    with right:
        with st.container(key="monthswitch", horizontal=True, vertical_alignment="center"):
            st.button("", key="month_prev", icon=":material/chevron_left:", disabled=not state["can_prev"],
                      on_click=change_month, args=(-1,), help="Previous month")
            st.html(html.month_label(state["summary"]["label"]))
            st.button("", key="month_next", icon=":material/chevron_right:", disabled=not state["can_next"],
                      on_click=change_month, args=(1,), help="Next month")


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------
def overview(state, service, sid, today, prefs, now_text):
    s = state["summary"]
    currency = state["currency"]["code"]
    main, desk = st.columns([2.55, 1], gap="medium")
    with main:
        till(state, service, sid, today, now_text)
        kpis(s, currency)
        with st.container(key="card-curve"):
            st.html(html.curve_head(s))
            if state["total_count"]:
                st.altair_chart(charts.month_curve(s, prefs["theme"]), width="stretch")
            else:
                st.html(html.empty_month(reward_svg("sprig")))
                st.button("Load a sample month", key="empty_demo", icon=":material/auto_awesome:",
                          on_click=_open, args=("demo",))
        left, right = st.columns(2, gap="medium")
        with left, st.container(key="card-groups"):
            st.html(html.groups(s))
        with right, st.container(key="card-recent"):
            prefetch([p["brand"] for p in state["purchases"][:6]])
            st.html(html.recent(state["purchases"], currency, s["label"]))
            st.button("Open ledger", key="to_ledger", type="tertiary", on_click=set_view, args=("ledger",))
    with desk:
        receipt(state, currency)
        with st.container(key="card-tip"):
            idx = ss().get("tip_index", 0) % len(TIPS)
            st.html(html.tip(TIPS[idx]))
            st.button("Next tip", key="next_tip", type="tertiary",
                      on_click=lambda: ss().update(tip_index=ss().get("tip_index", 0) + 1))
        with st.container(key="card-shelf"):
            st.html(html.shelf(state["badges"], badge_art()))
            st.button("All badges", key="to_badges", type="tertiary", on_click=set_view, args=("badges",))


def till(state, service, sid, today, now_text):
    currency = state["currency"]["code"]
    s = ss()
    s.currency = currency
    options = tag_options(currency)
    if s.get("f_tag") not in options:
        s.f_tag = nearest(options, s.get("f_price"))
    used = sorted({p["brand"] for p in state["purchases"] if p["brand"] and p["brand"].lower() not in BY_NAME})
    brand_options = BRAND_NAMES + [b for b in used if b not in BRAND_NAMES]
    if s.get("f_brand") and s.f_brand not in brand_options:
        brand_options.append(s.f_brand)

    with st.container(key="till"):
        st.html(html.till_head())
        c1, c2, c3, c4 = st.columns([2.1, 1.35, 1, 1.05])
        c1.selectbox("Product type", TYPE_IDS, index=None, key="f_type", format_func=type_label,
                     placeholder=f"Choose from {len(TYPE_IDS)} kinds of purchase", on_change=_on_type)
        c2.selectbox("Brand or shop", brand_options, index=None, key="f_brand", accept_new_options=True,
                     placeholder=f"Search {len(BRANDS)} brands", help="Pick a brand or type any shop name")
        c3.number_input(f"Price ({currency})", min_value=0.0, value=None, step=1.0, format="%.2f", key="f_price",
                        placeholder="0.00", on_change=_on_price)
        c4.date_input("Date", value=today, key="f_date", max_value=today, min_value=date(2000, 1, 1), format="DD/MM/YYYY")
        n1, n2, n3 = st.columns([2.1, 2.4, 1.05], vertical_alignment="bottom")
        n1.text_input("Item (optional)", key="f_note", max_chars=120, placeholder="e.g. Wool jumper")
        with n2:
            st.select_slider("Price tag", options=options, key="f_tag", on_change=_on_tag,
                             format_func=lambda v: html.money(v, currency, 0), label_visibility="collapsed")
            st.html('<p class="slide-hint">Drag the tag to try prices — it clicks at every step</p>')
        n3.button("Ring it up", key="ring", type="primary", icon=":material/point_of_sale:", width="stretch",
                  on_click=_ring, args=(service, sid, today, now_text))

        # Live estimate — recomputed in Python on every change.
        ptype, price = s.get("f_type"), s.get("f_price")
        est = estimate(ptype, price or 0, currency, s.get("f_brand") or "", s.get("f_swapped_from")) if ptype else None
        swapped_name = est.get("swapped_from_name") if est and s.get("f_swapped_from") else None
        offer = est and price and not swapped_name and est.get("swap") and est["swap"]["saving"] > 0
        if offer:
            e1, e2 = st.columns([2.6, 1.4], vertical_alignment="center")
            e1.html(html.estimate(est, ptype, bool(price), currency, swapped_name))
            with e2:
                sw = est["swap"]
                st.button(f"Try {sw['to_name'].lower()} — saves {sw['saving']:,.1f} kg ({sw['saving_pct']}%)",
                          key="take_swap", icon=":material/swap_horiz:", on_click=_take_swap, args=(sw["to"],),
                          width="stretch")
                st.html(html.swap_logos(sw["brands"]))
        else:
            st.html(html.estimate(est, ptype, bool(price), currency, swapped_name))
        if s.get("form_error"):
            st.html(f'<p class="form-error" role="alert">{html.esc(s.form_error)}</p>'
                    f'<script>(function go(){{if(!window.ShopImpact)return setTimeout(go,40);'
                    f'if(!window.ShopImpact.played.has("{s.get("error_nonce", "")}")){{window.ShopImpact.played.add("{s.get("error_nonce", "")}");'
                    f'window.ShopImpact.sound.error();}}}})();</script>', unsafe_allow_javascript=True)


def kpis(s, currency):
    k1, k2, k3, k4 = st.columns([1.35, 1, 1, 1], gap="small")
    delta = None
    if s.get("vs_prev_pct") is not None:
        delta = f'{s["vs_prev_pct"]:+d}% vs {s["vs_prev_basis"]}'
    with k1, st.container(key="kpi-footprint"):
        st.metric("Footprint this month", f'{s["co2"]:,.1f} kg CO₂e', delta, delta_color="inverse",
                  help="Each purchase: price in £ × the product type's kg CO₂e per £. Frozen when you log it.")
        st.html(html.footprint_extra(s))
    with k2, st.container(key="kpi-spend"):
        st.metric("Spent", html.money(s["spend"], currency))
        st.html(html.spend_extra(s, currency))
    with k3, st.container(key="kpi-score"):
        score = "–" if s["score"] is None else f'{s["score"]} / 100'
        st.metric("Eco score", score, help="Carbon per £ spent, pulled down further if the month goes over its CO₂ budget.")
        st.html(html.score_extra(s))
    with k4, st.container(key="kpi-feels"):
        st.metric("Feels like driving", f'{s["equivalents"]["car_km"]:,.0f} km',
                  help="Average petrol car: 0.17 kg CO₂ per km.")
        st.html(html.feels_extra(s))


def receipt(state, currency):
    r = ss().get("receipt")
    if r and r["purchase"]["id"] in {p["id"] for p in state["purchases"]} | {state["latest"]["id"] if state["latest"] else -1}:
        latest = next((p for p in state["purchases"] if p["id"] == r["purchase"]["id"]), r["purchase"])
        st.html(html.receipt("si-desk", r["nonce"], latest, r["reward"], r["tip"], currency, r["fresh"], r["when"]),
                unsafe_allow_javascript=True)
        return
    latest = state["latest"]
    if latest:
        kind = drawings.REWARD_FOR_TIER[latest["tier"]]
        reward = {"svg": reward_svg(kind), "message": "Your latest purchase."}
        when = html.short_date(latest["date"]) + " " + latest["date"][:4]
        st.html(html.receipt("si-desk", f"latest-{latest['id']}", latest, reward, None, currency, False, when),
                unsafe_allow_javascript=True)
    else:
        st.html(html.receipt("si-desk", "welcome", None, {"svg": reward_svg("sprig")}, None, currency, True, ""),
                unsafe_allow_javascript=True)


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------
def ledger(state, service, sid, today):
    currency = state["currency"]["code"]
    s = ss()
    f1, f2, f3, f4 = st.columns([2.4, 2, 1.3, 1.2], vertical_alignment="bottom")
    f1.text_input("Search", key="lg_q", placeholder="Search item, brand or type", label_visibility="collapsed",
                  icon=":material/search:")
    f2.pills("Impact", ["low", "medium", "high"], selection_mode="multi", default=["low", "medium", "high"],
             key="lg_tiers", format_func=str.capitalize, label_visibility="collapsed")
    f3.selectbox("Sort", ["date", "co2", "price"], key="lg_sort", label_visibility="collapsed",
                 format_func={"date": "Newest first", "co2": "Highest CO₂ first", "price": "Highest price first"}.get)
    filename, csv_text = service.export_csv(sid, state["month"], today)
    f4.download_button("Export CSV", csv_text, file_name=filename, mime="text/csv", icon=":material/download:",
                       width="stretch")

    if s.get("last_deleted"):
        u1, _ = st.columns([1.4, 4])
        u1.button("Undo last delete", key="undo", icon=":material/undo:", on_click=_undo, args=(service, sid, today))

    term = (s.get("lg_q") or "").strip().lower()
    tiers = set(s.get("lg_tiers") or [])
    rows = [p for p in state["purchases"] if p["tier"] in tiers and
            (not term or any(term in (v or "").lower() for v in (p["type_name"], p["brand"], p["note"], p["group_name"])))]
    if s.get("lg_sort") == "co2":
        rows.sort(key=lambda p: p["co2"], reverse=True)
    elif s.get("lg_sort") == "price":
        rows.sort(key=lambda p: p["display_price"], reverse=True)
    st.html(html.ledger_totals(rows, len(state["purchases"]), currency, state["summary"]["swapped_saving"]))

    if not rows:
        with st.container(key="card-ledger-empty"):
            msg = ("No purchases match — clear the search or turn the impact filters back on." if state["purchases"]
                   else f"Purchases you ring up in {state['summary']['label']} appear here.")
            st.html(f'<div class="empty"><h3>{"No purchases match" if state["purchases"] else "Nothing in the ledger yet"}'
                    f'</h3><p>{html.esc(msg)}</p></div>')
        return
    prefetch([p["brand"] for p in rows])
    top = max(p["co2"] for p in state["purchases"]) or 0.01
    with st.container(key="ledger"):
        for p in rows:
            with st.container(key=f"row-{p['id']}"):
                c1, c2, c3 = st.columns([10, 1.4, 0.7], vertical_alignment="center", gap="small")
                c1.html(html.ledger_line(p, currency, top))
                if p["swap"] and p["swap"]["saving"] > 0:
                    c2.button("Swap", key=f"swap_{p['id']}", icon=":material/swap_horiz:", on_click=_open,
                              args=("swap", p["id"]), help=f"Swap to {p['swap']['to_name']}")
                c3.button("", key=f"del_{p['id']}", icon=":material/delete:", on_click=_delete,
                          args=(service, sid, today, p["id"]), help="Delete this purchase")


# ---------------------------------------------------------------------------
# Swaps
# ---------------------------------------------------------------------------
def swaps(state, service, sid, today):
    s = state["summary"]
    left, right = st.columns([1.3, 1], gap="medium")
    with left, st.container(key="card-whatif"):
        st.html(html.card_head("What if you swapped?",
                               "Drag to swap a share of this month's medium and high-impact buys for their greener option."))
        pct = st.slider("Share swapped", 0, 100, 50, 5, key="wi_pct", format="%d%%", label_visibility="collapsed")
        row = next(w for w in s["whatif"] if w["pct"] == pct)
        m1, m2, m3 = st.columns(3)
        m1.metric("You'd save", f'{row["saved"]:,.1f} kg')
        m2.metric("New monthly total", f'{row["after"]:,.1f} kg')
        m3.metric("New eco score", "–" if row["score"] is None else row["score"],
                  None if row["score"] is None or s["score"] is None else row["score"] - s["score"])
        st.html(html.whatif_bars(s["co2"], row["after"], pct))
    with right, st.container(key="card-topswaps"):
        st.html(html.card_head("Your biggest wins", "The swaps that would save the most this month."))
        if not s["top_swaps"]:
            st.html('<p class="hint">Log some purchases and the biggest wins show up here.</p>')
        for t in s["top_swaps"]:
            a, b = st.columns([3, 1], vertical_alignment="center")
            a.html(html.top_swap(t))
            b.button("Swap", key=f"tswap_{t['id']}", icon=":material/swap_horiz:", on_click=_open, args=("swap", t["id"]))

    greener = sorted((b for b in BRANDS if b["greener"]), key=lambda b: b["name"].lower())
    with st.container(key="card-logowall"):
        st.html(html.card_head("Greener brands & shops",
                               "Second-hand, refurbished, refill and lower-impact names to try next time."))
        shown = greener if ss().get("show_all_brands") else greener[:24]
        prefetch([b["name"] for b in shown])
        st.html(html.logo_wall(shown, TYPE_NAMES))
        st.button("Show fewer" if ss().get("show_all_brands") else f"Show all {len(greener)}", key="logo_more",
                  type="tertiary", on_click=lambda: ss().update(show_all_brands=not ss().get("show_all_brands")))

    st.html('<h2 class="si-h2" style="font-size:1.4rem;font-weight:720;margin-top:.6rem">Greener alternatives</h2>')
    group = st.pills("Group", ["all"] + list(GROUPS), default="all", key="cat_group", label_visibility="collapsed",
                     format_func=lambda g: "All" if g == "all" else GROUPS[g]["name"]) or "all"
    types = [t for t in catalog_payload()["types"] if group == "all" or t["group"] == group]
    types.sort(key=lambda t: t["multiplier"], reverse=True)
    names = {n for t in types for n in greener_for(t["swap_to"] or t["id"])}
    prefetch(names)
    st.html(html.catalog(types, greener_for, max(t["multiplier"] for t in PRODUCT_TYPES.values())))


# ---------------------------------------------------------------------------
# Badges
# ---------------------------------------------------------------------------
def badges(state):
    b = state["badges"]
    earned = sum(1 for x in b if x["earned"])
    st.html(f'<p class="card-sub" style="font-size:.98rem;color:var(--ink-2)">You have <b>{earned} of {len(b)}</b> badges '
            f'for {html.esc(state["summary"]["label"])}. Month-long badges (Eco Saver, Mindful Spender, Carbon Cutter) show '
            f'“on track” until the month ends, then lock in. Only purchases worth about £1 or more count. '
            f'Tap a badge to watch the turtle draw it.</p>')
    art = badge_art()
    for start in range(0, len(b), 4):
        cols = st.columns(4, gap="medium")
        for col, badge in zip(cols, b[start:start + 4]):
            with col, st.container(key=f"card-badge-{badge['id']}"):
                st.html(html.badge_card(badge, art[badge["id"]]))
                st.button("Watch it drawn", key=f"watch_{badge['id']}", icon=":material/draw:", type="tertiary",
                          on_click=_open, args=("badge", badge["id"]))


# ---------------------------------------------------------------------------
# Garden
# ---------------------------------------------------------------------------
def garden(state, service, sid, today, prefs):
    s = state["summary"]
    left, right = st.columns([1.7, 1], gap="medium")
    with left, st.container(key="card-tree"):
        a, b = st.columns([3, 1], vertical_alignment="center")
        a.html(html.card_head("This month's tree", "A Python turtle grows it from your purchases."))
        b.button("Replay", key="tree_replay", icon=":material/replay:",
                 on_click=lambda: ss().update(tree_replays=ss().get("tree_replays", 0) + 1))
        svg = service.tree_svg(sid, state["month"], today)
        nonce = f"tree-{state['month']}-{s['count']}-{s['score']}-{ss().get('tree_replays', 0)}"
        st.html(html.turtle_stage("si-tree", nonce, svg), unsafe_allow_javascript=True)
    with right:
        with st.container(key="card-treekey"):
            st.html(html.tree_key())
            m1, m2, m3 = st.columns(3)
            m1.metric("Eco score", "–" if s["score"] is None else s["score"])
            m2.metric("Light buys", s["tiers"]["low"]["count"])
            m3.metric("Heavy buys", s["tiers"]["high"]["count"])
        with st.container(key="card-history"):
            st.html(html.card_head("Six-month trend", "kg CO₂e per month"))
            st.altair_chart(charts.history(state["history"], state["month"], prefs["theme"]), width="stretch")
    with st.container(key="card-quote"):
        idx = ss().get("quote_index", 0) % len(QUOTES)
        st.html(html.quote({"text": QUOTES[idx][0], "author": QUOTES[idx][1]}))
        st.button("Another quote", key="next_quote", type="tertiary",
                  on_click=lambda: ss().update(quote_index=ss().get("quote_index", 0) + 1))


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
def settings(state, service, sid, today, prefs, rates_status, share_url):
    st_ = state["settings"]
    currency = state["currency"]
    s = ss()
    c1, c2, c3 = st.columns(3, gap="medium")
    with c1:
        with st.container(key="card-you"):
            st.html('<h2 class="si-h2">You</h2>')
            st.text_input("Your first name", value=st_.get("name") or "", key="set_name", max_chars=40,
                          placeholder="Used in your greeting",
                          on_change=_save_settings, args=(service, sid, today, "name", "set_name"))
            codes = POPULAR + [c["code"] for c in COUNTRIES if c["code"] not in POPULAR]
            country = st_.get("country")
            st.selectbox("Country", codes, index=codes.index(country) if country in codes else None, key="set_country",
                         placeholder="Choose your country",
                         format_func=lambda code: f"{COUNTRY_BY_CODE[code]['name']} · {COUNTRY_BY_CODE[code]['currency']}",
                         on_change=_save_country, args=(service, sid, today),
                         help="Picking a country switches to its currency. Brands stay the same everywhere.")
            codes_cur = sorted(CURRENCIES)
            st.selectbox("Currency", codes_cur, index=codes_cur.index(st_["currency"]), key="set_currency",
                         format_func=lambda code: f"{code} · {CURRENCIES[code]['symbol']}",
                         on_change=_save_settings, args=(service, sid, today, "currency", "set_currency"))
            rate = "" if currency["code"] == "GBP" else f"£1 ≈ {html.money(1 / currency['to_gbp'], currency['code'])}. "
            source = ("Live rates from <a href='https://www.exchangerate-api.com' target='_blank'>Exchange Rate API</a>"
                      if rates_status.get("source") == "ExchangeRate-API" else "Built-in rates (live rates load when online)")
            st.html(f'<p class="hint">{html.esc(rate)}{source}. Each purchase keeps the rate it was logged with.</p>')
        with st.container(key="card-link"):
            st.html('<h2 class="si-h2">Your private link</h2><p class="hint">Your purchases are saved under this '
                    'anonymous link — bookmark it to come back. Anyone with the link can see this ledger.</p>'
                    f'<div class="private-link">{html.esc(share_url)}</div>')
    with c2:
        with st.container(key="card-budgets"):
            st.html('<h2 class="si-h2">Monthly budgets</h2>')
            st.slider("CO₂ budget (kg)", 20, 600, value=int(min(max(st_["co2_budget"], 20), 600)), step=10, key="set_co2",
                      on_change=_save_settings, args=(service, sid, today, "co2_budget", "set_co2"))
            st.html('<p class="hint">New budgets apply from this month on — past months keep theirs.</p>')
            rate = currency["to_gbp"]
            step = _nice(25 / rate)
            low, high = _nice(50 / rate), max(_nice(50 / rate) + step, round(3000 / rate / step) * step)
            value = min(max(int(round(st_["spend_budget"] / step) * step), low), high)
            st.slider(f"Spending budget ({currency['code']})", int(low), int(high), value=int(value), step=int(step),
                      key=f"set_spend_{currency['code']}",
                      on_change=_save_settings, args=(service, sid, today, "spend_budget", f"set_spend_{currency['code']}"))
        with st.container(key="card-data"):
            st.html('<h2 class="si-h2">Your data</h2>')
            st.button("Load a sample month", key="demo_btn", icon=":material/auto_awesome:", on_click=_open, args=("demo",))
            filename, csv_text = service.export_csv(sid, state["month"], today)
            st.download_button("Export this month (CSV)", csv_text, file_name=filename, mime="text/csv",
                               icon=":material/download:", key="csv2")
            st.download_button("Download a full backup (JSON)", service.backup(sid), file_name="shopimpact-backup.json",
                               mime="application/json", icon=":material/save:", key="backup")
            st.file_uploader("Restore from a backup", type=["json"], key="restore_file",
                             help="Replaces the purchases in this ledger with the backup's.")
            if s.get("restore_file") is not None and st.button("Restore this backup", key="restore_go",
                                                                 icon=":material/settings_backup_restore:"):
                try:
                    count = service.restore_backup(sid, s.restore_file.getvalue().decode("utf-8", "replace"), today)
                    toast(f"Restored {count} purchases.", ":material/check:")
                    st.rerun()
                except ValidationError as err:
                    st.error(str(err))
            st.button("Erase all purchases", key="reset_btn", icon=":material/delete_forever:", on_click=_open,
                      args=("reset",))
    with c3:
        with st.container(key="card-look"):
            st.html('<h2 class="si-h2">Look &amp; feel</h2>')
            st.segmented_control("Theme", list(THEME_NAMES), default=prefs["theme"], key="ui_theme",
                                 format_func=THEME_NAMES.get,
                                 on_change=_save_ui, args=(service, sid, "theme", "ui_theme"))
            st.segmented_control("Text size", ["regular", "large"], default=prefs["text"], key="ui_text",
                                 format_func=str.capitalize,
                                 on_change=_save_ui, args=(service, sid, "text", "ui_text"))
            st.toggle("Sounds", value=prefs["sound"], key="ui_sound", on_change=_save_ui, args=(service, sid, "sound", "ui_sound"))
            st.slider("Volume", 0, 100, value=int(prefs["volume"] * 100), step=5, key="ui_volume", format="%d%%",
                      on_change=_save_ui, args=(service, sid, "volume", "ui_volume", lambda v: v / 100))
            st.toggle("Reduce motion", value=prefs["motion"] == "reduced", key="ui_motion",
                      on_change=_save_ui, args=(service, sid, "motion", "ui_motion", lambda v: "reduced" if v else "full"))
            st.slider("Turtle speed", 0.5, 3.0, value=float(prefs["speed"]), step=0.25, key="ui_speed", format="%.2f×",
                      on_change=_save_ui, args=(service, sid, "speed", "ui_speed"))
        with st.container(key="card-about"):
            st.html('<h2 class="si-h2">How the numbers work</h2><div class="about">'
                    '<p>Each product type has a multiplier — roughly how many kilograms of CO₂e are emitted per £1 spent '
                    'on it. A purchase’s footprint is <code>price in £ × multiplier</code>, frozen at the moment you log it.</p>'
                    '<p>The eco score starts from carbon per £ (0 kg/£ → 100, 1.2 kg/£ or more → 0) and is pulled down '
                    'further if the month goes over its CO₂ budget, so spending more never improves it.</p>'
                    '<p>Figures are rounded, awareness-level estimates for comparing choices — not a carbon audit.</p></div>')


def _nice(value):
    p = 10 ** math.floor(math.log10(value))
    n = value / p
    return (1 if n < 1.5 else 2 if n < 3.5 else 5 if n < 7.5 else 10) * p


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------
@st.dialog("Greener swap", width="medium")
def swap_dialog(purchase, service, sid, today):
    p = purchase
    st.html(f'<p class="eyebrow">{html.esc(p["note"] or p["type_name"])}</p>'
            f'<div style="display:grid;grid-template-columns:1fr auto 1fr;gap:.6rem;align-items:center">'
            f'<div class="ts-item"><span class="card-sub" style="margin:0">Now</span><b>{html.esc(p["type_name"])}</b>'
            f'<span style="font-family:var(--f-mono)">{html.kg(p["co2"], 2)} kg</span></div>{html.gi("arrow")}'
            f'<div class="ts-item" style="background:var(--low-soft)"><span class="card-sub" style="margin:0">Greener</span>'
            f'<b>{html.esc(p["swap"]["to_name"])}</b><span style="font-family:var(--f-mono)">{html.kg(p["swap"]["co2"], 2)} kg</span></div></div>'
            f'<p class="pt-why" style="margin-top:.8rem">{html.esc(p["swap"]["why"])} '
            f'<b style="color:var(--low)">Saves {html.kg(p["swap"]["saving"], 2)} kg ({p["swap"]["saving_pct"]}%)</b> — '
            f'assuming you spend the same.</p>')
    pick = st.pills("Brand you'd buy instead (optional)", p["swap"]["brands"], key=f"pick_{p['id']}")
    typed = st.text_input("Or type a brand", key=f"typed_{p['id']}", max_chars=60)
    a, b = st.columns(2)
    if a.button("Keep as is", key=f"keep_{p['id']}", width="stretch"):
        st.rerun()
    if b.button("Swap it", key=f"confirm_swap_{p['id']}", type="primary", icon=":material/swap_horiz:", width="stretch"):
        try:
            result = service.swap(sid, p["id"], today, brand=(typed or pick or ""))
        except (ValidationError, LookupError) as err:
            st.error(str(err))
            return
        toast(f"Swapped to {result['purchase']['type_name'].lower()} — {result['purchase'].get('swap_saved', 0):,.1f} kg lighter.",
              ":material/eco:")
        ss().badge_queue = ss().get("badge_queue", []) + result["new_badges"]
        st.rerun()


@st.dialog("Badge", width="small", on_dismiss="rerun")
def badge_dialog(card, eyebrow, celebrate):
    st.html(f'<p class="eyebrow" style="text-align:center">{html.esc(eyebrow)}</p>')
    svg = drawings.render("badge", color=card["color"], emblem=card["emblem"], name=card["name"]) \
        if "color" in card else card["svg"]
    st.html(html.turtle_stage(f"si-badge-{card['id']}", f"badge-{card['id']}-{uuid.uuid4().hex}", svg,
                              cls="badge-stage", chime="badge" if celebrate else None, always=True,
                              max_ms=2800, min_ms=1600), unsafe_allow_javascript=True)
    st.html(f'<h3 class="badge-title" style="justify-content:center;font-size:1.3rem">{html.esc(card["name"])}</h3>'
            f'<p class="badge-blurb" style="text-align:center">{html.esc(card.get("blurb", ""))}</p>')
    if st.button("Lovely", key="badge_ok", type="primary", width="stretch"):
        st.rerun()


@st.dialog("Load a sample month?", width="small")
def demo_dialog(service, sid, today, has_data):
    if has_data:
        st.warning("This replaces every purchase in this ledger with the sample. Download a backup first if you "
                   "want to keep them.")
    st.html('<p class="hint">15 everyday purchases this month and 7 last month, mixing cheap and expensive, '
            'eco and non-eco — the test set the brief asks for.</p>')
    a, b = st.columns(2)
    if a.button("Cancel", width="stretch"):
        st.rerun()
    if b.button("Load sample", type="primary", width="stretch", icon=":material/auto_awesome:"):
        service.load_demo(sid, today)
        ss().month = month_key(today)
        ss().pop("receipt", None)
        toast("Sample month loaded — 15 purchases this month, 7 last month.", ":material/auto_awesome:")
        st.rerun()


@st.dialog("Erase all purchases?", width="small")
def reset_dialog(service, sid, today):
    st.warning("This permanently deletes every purchase in this ledger. Settings are kept.")
    a, b = st.columns(2)
    if a.button("Cancel", width="stretch"):
        st.rerun()
    if b.button("Erase everything", type="primary", width="stretch", icon=":material/delete_forever:"):
        service.reset(sid, today)
        ss().pop("receipt", None)
        toast("All purchases erased.", ":material/delete:")
        st.rerun()


def run_dialogs(state, service, sid, today):
    """Open at most one dialog per run: explicit requests first, then badges."""
    s = ss()
    request = s.pop("dialog", None)
    if request:
        kind, value = request
        if kind == "swap":
            purchase = next((p for p in state["purchases"] if p["id"] == value), None)
            if purchase and purchase["swap"]:
                swap_dialog(purchase, service, sid, today)
        elif kind == "badge":
            card = next(b for b in BADGES if b["id"] == value)
            status = next(b for b in state["badges"] if b["id"] == value)
            eyebrow = "Earned" if status["earned"] else ("On track" if status["on_track"] else
                                                         f"Locked · {round(status['progress'] * 100)}% there")
            badge_dialog({**card, "blurb": status["blurb"] if status["earned"] else f"{status['blurb']} {status['hint']}"},
                         eyebrow, False)
        elif kind == "demo":
            demo_dialog(service, sid, today, state["total_count"] > 0)
        elif kind == "reset":
            reset_dialog(service, sid, today)
        return
    queue = s.get("badge_queue") or []
    if queue:
        card = queue[0]
        s.badge_queue = queue[1:]
        badge_dialog(card, f"Badge unlocked{' · ' + card['month'] if card.get('month') else ''}", True)


def greeting(name, now):
    hour = now.hour
    hello = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
    return f"{hello}, {name}" if name else hello
