"""HTML for the parts of the Streamlit app that only *display* things.

Every number shown here was computed in Python (shopimpact/engine.py). These
functions just lay it out with the design system's classes.
"""

import base64
import json
from datetime import date
from html import escape

from ..catalog import CURRENCIES, GROUPS
from .logo_cache import logo_uri
from .theme import icon_svg


def esc(value):
    return escape("" if value is None else str(value), quote=True)


def svg_uri(svg):
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def js_string(text):
    """A JS string literal that is safe inside <script> — and inside st.html, whose
    sanitiser (DOMPurify) drops any script whose text contains '<' + a letter."""
    return json.dumps(text).replace("<", "\\u003c").replace(">", "\\u003e")


def gi(name):
    return f'<i class="gi gi-{name}" aria-hidden="true"></i>'


# ---------------------------------------------------------------------------
# Number formatting
# ---------------------------------------------------------------------------
def money(amount, currency, decimals=None):
    info = CURRENCIES.get(currency, CURRENCIES["GBP"])
    if decimals is None:
        decimals = 0 if abs(amount) >= 1000 or info["slider"][1] > 1 else 2
    sym = info["symbol"]
    number = f"{abs(amount):,.{decimals}f}"
    sign = "−" if amount < 0 else ""
    if sym == currency or sym[-1:].isalpha():
        return f"{sign}{sym} {number}"
    return f"{sign}{sym}{number}"


def kg(value, decimals=1):
    return f"{value:,.{decimals}f}"


def short_date(iso):
    d = date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%b')}"


# ---------------------------------------------------------------------------
# Shell
# ---------------------------------------------------------------------------
BRAND_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40"><ellipse cx="19" cy="22" rx="12" ry="9.5" fill="#4E8A57"/>'
             '<path d="M11 22h16M19 13.5v17M13.5 16.5l11 11M24.5 16.5l-11 11" stroke="#F7F6EF" stroke-width="1.6" '
             'stroke-linecap="round" fill="none" opacity=".8"/><circle cx="33.5" cy="19" r="3.6" fill="#1E3B2F"/>'
             '<path d="M10 29l-2.5 3.5M28 29l2.5 3.5M10 15l-2.5-3.5" stroke="#1E3B2F" stroke-width="2.6" '
             'stroke-linecap="round" fill="none"/></svg>')


def brand_mark():
    return f'<div class="brand"><img src="{svg_uri(BRAND_SVG)}" alt=""><span>Shop<b>Impact</b></span></div>'


def title(eyebrow, heading):
    return f'<div class="si-title"><span class="eyebrow">{esc(eyebrow)}</span><h1>{esc(heading)}</h1></div>'


def month_label(text):
    return f'<div class="month-label" aria-live="polite">{esc(text)}</div>'


def card_head(heading, sub=None, right=""):
    sub_html = f'<p class="card-sub">{esc(sub)}</p>' if sub else ""
    return f'<div class="card-head"><div><h2>{esc(heading)}</h2>{sub_html}</div>{right}</div>'


# ---------------------------------------------------------------------------
# Till
# ---------------------------------------------------------------------------
def till_head():
    return '<div class="till-head"><h2>Ring up a purchase</h2><span>Every number updates as you change it</span></div>'


def estimate(est, ptype, price_given, currency, swapped_from_name=None):
    if not ptype or not est or not est.get("ok"):
        return '<div class="estimate"><p class="est-empty">Pick a product type and price — the CO₂ estimate updates as you go.</p></div>'
    if not price_given:
        return (f'<div class="estimate"><div class="est-co2"><strong>{est["multiplier"]:.2f}</strong>'
                f'<span>kg CO₂e for every £1</span></div><span class="pill pill-{est["tier"]}">{est["tier"]} impact</span>'
                f'<span class="est-feel">Add a price to see this purchase’s footprint.</span></div>')
    e = est["equivalents"]
    brand_note = " · <b>greener brand</b>" if est["ethical_brand"] else ""
    formula = f'£{est["price_gbp"]:,.2f} × {est["multiplier"]:.2f} kg/£' if currency == "GBP" else \
        f'{money(est["price_gbp"], "GBP")} × {est["multiplier"]:.2f} kg/£'
    right = ""
    if swapped_from_name:
        right = (f'<span class="est-good">{gi("leaf")}Swapped from {esc(swapped_from_name.lower())} — saves '
                 f'{kg(est.get("swapped_saving", 0))} kg</span>')
    elif est["tier"] == "low":
        right = f'<span class="est-good">{gi("leaf")}Already one of the lightest choices</span>'
    return (f'<div class="estimate"><div class="est-co2"><strong>{kg(est["co2"], 2)}</strong><span>kg CO₂e</span></div>'
            f'<span class="pill pill-{est["tier"]}">{est["tier"]} impact</span>'
            f'<span class="est-feel">≈ <b>{kg(e["car_km"])} km</b> by car · <b>{e["phone_charges"]:,}</b> phone charges'
            f'{brand_note}<br><span class="est-why">{esc(formula)}</span></span>{right}</div>')


def swap_logos(names):
    imgs = [f'<img src="{u}" alt="" title="{esc(n)}">' for n in names if (u := logo_uri(n))]
    if not imgs:
        return ""
    return f'<div class="est-logos" aria-label="Greener brands">{"".join(imgs[:4])}</div>'


# ---------------------------------------------------------------------------
# Receipt + turtle stamp
# ---------------------------------------------------------------------------
def _barcode(seed):
    n = str(seed * 7919 + 1234)
    return f"--b1:{1 + int(n[0]) % 3}px;--b2:{4 + int(n[1]) % 3}px;--b3:{6 + int(n[2]) % 3}px;--b4:{10 + int(n[3]) % 4}px"


def receipt(root_id, nonce, purchase, reward, tip, currency, fresh, when_text):
    """The printer, a receipt, and a script that feeds it out and stamps it."""
    lines, d = [], 0

    def line(html, cls=""):
        nonlocal d
        lines.append(f'<div class="rc-line {cls}" style="--d:{d}">{html}</div>')
        d += 1

    if purchase:
        p = purchase
        e = p["equivalents"]
        line(f'<strong>ShopImpact</strong>conscious till · no. {p["id"]:04d}', "rc-head")
        line(f'<span>{esc(when_text)}</span>', "rc-row rc-muted")
        lines.append('<hr class="rc-rule">')
        line(esc(p["note"] or p["type_name"]), "rc-item")
        if p["note"]:
            line(esc(p["type_name"]), "rc-muted")
        logo = p["brand_info"] and logo_uri(p["brand_info"]["name"])
        logo_html = f'<img src="{logo}" alt="">' if logo else ""
        line(f'<span class="rc-brand">{logo_html}<span>{esc(p["brand"] or "Unbranded")}</span></span>'
             f'<span>{esc(money(p["display_price"], currency))}</span>', "rc-row")
        lines.append('<hr class="rc-rule">')
        line(f'<span>CO₂e</span><span>{kg(p["co2"], 2)} kg</span>', "rc-dots rc-big")
        line(f'£{p["price_gbp"]:,.2f} × {p["multiplier"]:.2f} kg/£', "rc-formula")
        line(f'<span>Impact</span><span>{p["tier"].upper()}</span>', "rc-dots")
        line(f'<span>Feels like</span><span>{kg(e["car_km"])} km by car</span>', "rc-dots")
        if p.get("swap_saved"):
            line(f'<span>Swap saved</span><span>{kg(p["swap_saved"], 2)} kg</span>', "rc-dots")
        lines.append('<div class="rc-stamp" data-stamp></div>')
        line(esc(reward.get("message", "Logged.")), "rc-msg")
        if p["swap"] and p["swap"]["saving"] > 0:
            line(f'Lighter next time: <b>{esc(p["swap"]["to_name"])}</b> would be {kg(p["swap"]["co2"], 2)} kg '
                 f'(−{p["swap"]["saving_pct"]}%).', "rc-swap")
        if tip:
            lines.append('<hr class="rc-rule">')
            line(f'TIP · {esc(tip)}', "rc-muted")
        lines.append(f'<div class="rc-barcode rc-line" style="--d:{d};{_barcode(p["id"])}"></div>')
        line("thank you for shopping mindfully", "rc-foot rc-muted")
        tier = p["tier"]
    else:
        lines.append('<div class="rc-head"><strong>ShopImpact</strong>conscious till · ready</div><hr class="rc-rule">'
                     '<div class="rc-item">Your first receipt prints here.</div>'
                     '<div class="rc-muted">Ring up a purchase and a turtle will stamp it with a leaf, a footprint or a badge.</div>'
                     '<div class="rc-stamp" data-stamp></div>'
                     '<div class="rc-dots"><span>Light buy</span><span>leaf sprig</span></div>'
                     '<div class="rc-dots"><span>Medium buy</span><span>light steps</span></div>'
                     '<div class="rc-dots"><span>Heavy buy</span><span>deep footprint</span></div>'
                     f'<div class="rc-barcode" style="{_barcode(42)}"></div>'
                     '<div class="rc-foot rc-muted">ring up a purchase to start</div>')
        tier = "low"
    svg = reward.get("svg", "") if reward else ""
    return (f'<div class="desk" id="{root_id}" aria-label="Latest receipt">'
            f'<div class="printer"><span class="printer-led"></span><span class="printer-slot"></span>'
            f'<span class="printer-label">Receipt</span></div>'
            f'<div class="receipt-well"><article class="receipt">{"".join(lines)}</article></div></div>'
            f'<script>(function go(){{ if(!window.ShopImpact) return setTimeout(go, 40);'
            f' window.ShopImpact.printReceipt({js_string(root_id)}, {js_string(nonce)}, {js_string(tier)},'
            f' {js_string(svg)}, {"true" if fresh else "false"}); }})();</script>')


def turtle_stage(host_id, nonce, svg, cls="tree-stage", chime=None, always=False, max_ms=6500, min_ms=2200):
    """A stage the turtle draws on, plus the script that starts it."""
    opts = json.dumps({"chime": chime, "always": always, "maxMs": max_ms, "minMs": min_ms})
    return (f'<div class="{cls}" id="{host_id}" role="img" aria-label="Turtle drawing"></div>'
            f'<script>(function go(){{ if(!window.ShopImpact) return setTimeout(go, 40);'
            f' window.ShopImpact.draw({js_string(host_id)}, {js_string(nonce)}, {js_string(svg)}, {opts}); }})();</script>')


# ---------------------------------------------------------------------------
# Overview cards
# ---------------------------------------------------------------------------
def footprint_extra(s):
    left = s["budget_left"]
    over = left < 0
    colour = "var(--high)" if over else "var(--medium)" if s["budget_pct"] > 80 else "var(--low)"
    foot = (f'<b>{kg(-left)} kg</b> over budget' if over else f'<b>{kg(left)} kg</b> left of {s["budget"]:,.0f}')
    if s["is_current"] and s["count"]:
        foot += f' · on track for {s["projected"]:,.0f}'
    ring = (f'<div class="ring" style="--p:{min(s["budget_pct"], 100)};--c:{colour}" role="img" '
            f'aria-label="{s["budget_pct"]}% of budget"><span>{s["budget_pct"]}%<small>of budget</small></span></div>')
    return f'<div class="kpi-row"><p class="kpi-foot">{foot}</p>{ring}</div>'


def spend_extra(s, currency):
    return (f'<div class="bar" title="{s["spend_pct"]}% of spending budget"><i style="width:{min(s["spend_pct"], 100)}%"></i></div>'
            f'<p class="kpi-foot"><b>{s["count"]}</b> purchase{"" if s["count"] == 1 else "s"} · {s["spend_pct"]}% of '
            f'{esc(money(s["spend_budget"], currency, 0))}</p>')


def score_extra(s):
    g = s["grade"]
    cls = "none" if s["score"] is None else g["letter"]
    basis = s.get("vs_prev_basis")
    delta = ""
    if s.get("vs_prev_pct") is not None:
        arrow = "▼" if s["vs_prev_pct"] <= 0 else "▲"
        delta = f' · {arrow} {abs(s["vs_prev_pct"])}% vs {esc(basis)}'
    return (f'<div class="kpi-row" style="justify-content:flex-start"><span class="grade grade-{cls}">{g["letter"]}</span>'
            f'<p class="kpi-foot"><b>{esc(g["label"])}</b>{delta}</p></div>')


def feels_extra(s):
    e = s["equivalents"]
    return (f'<div class="feels"><span><b>{e["phone_charges"]:,}</b> phone charges</span>'
            f'<span><b>{e["tree_days"]:,}</b> days of a tree’s work</span></div>')


def curve_head(s):
    if s["count"]:
        sub = f'{kg(s["co2"])} kg so far against a {s["budget"]:,.0f} kg budget'
    else:
        sub = f'No purchases in {s["label"]} yet'
    proj = '<span><i class="lg lg-proj"></i>Projected</span>' if s["is_current"] and s["count"] else ""
    legend = (f'<div class="legend"><span><i class="lg"></i>Running total</span>'
              f'<span><i class="lg lg-budget"></i>Budget</span>{proj}</div>')
    return card_head("Footprint over the month", sub, legend)


def groups(s):
    spend = s["spend"] or 1
    strip = "".join(f'<i class="ts-{t}" style="width:{100 * s["tiers"][t]["spend"] / spend}%"></i>'
                    for t in ("low", "medium", "high"))
    head = card_head("Where it comes from", None, f'<div class="tier-strip" title="Share of spending by impact tier">{strip}</div>')
    if not s["groups"]:
        return head + '<div class="empty"><p>Categories appear once you log a purchase.</p></div>'
    top = max(g["co2"] for g in s["groups"]) or 0.01
    rows = "".join(
        f'<li class="group-row"><span class="g-icon">{gi(g["icon"])}</span><span class="g-name">{esc(g["name"])}</span>'
        f'<span class="g-val">{kg(g["co2"])} kg · {round(g["share"] * 100)}%</span>'
        f'<span class="g-bar"><i style="width:{100 * g["co2"] / top}%;background:var(--{g["tier"]})"></i></span></li>'
        for g in s["groups"])
    return head + f'<ul class="groups">{rows}</ul>'


def recent(purchases, currency, label):
    head = card_head("Latest purchases")
    if not purchases:
        return head + f'<div class="empty"><p>Nothing logged in {esc(label)} yet.</p></div>'
    items = []
    for p in purchases[:6]:
        logo = p["brand_info"] and logo_uri(p["brand_info"]["name"])
        img = f'<img src="{logo}" alt="">' if logo else ""
        items.append(
            f'<li><span class="tdot tdot-{p["tier"]}" title="{p["tier"]} impact"></span>'
            f'<div class="r-main"><div class="r-name">{esc(p["note"] or p["type_name"])}</div>'
            f'<div class="r-sub">{img}<span>{esc(p["brand"] or "Unbranded")} · {esc(money(p["display_price"], currency))}</span></div></div>'
            f'<div class="r-co2">{kg(p["co2"])} kg<small>{short_date(p["date"])}</small></div></li>')
    return head + f'<ul class="recent">{"".join(items)}</ul>'


def shelf(badges, art):
    imgs = []
    for b in badges:
        status = " — earned" if b["earned"] else " — {}%".format(round(b["progress"] * 100))
        cls = "" if b["earned"] else "locked"
        imgs.append(f'<img class="{cls}" src="{art[b["id"]]}" alt="{esc(b["name"])}" title="{esc(b["name"] + status)}">')
    imgs = "".join(imgs)
    nxt = sorted((b for b in badges if not b["earned"]), key=lambda b: -b["progress"])
    line = (f'Next up: <b>{esc(nxt[0]["name"])}</b> — {esc(nxt[0]["hint"])}' if nxt
            else "Every badge earned this month. Remarkable.")
    return card_head("Badge shelf") + f'<div class="shelf">{imgs}</div><p class="shelf-next">{line}</p>'


def tip(text):
    return f'<span class="eyebrow">Did you know</span><p class="tip-text">{esc(text)}</p>'


def empty_month(sprig_svg):
    return (f'<div class="empty"><img src="{svg_uri(sprig_svg)}" alt="" style="width:110px;height:110px">'
            f'<h3>Your month is a blank receipt</h3><p>Ring up something you bought — or load a sample month of '
            f'15 everyday purchases to see the dashboard come alive.</p></div>')


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------
def ledger_totals(rows, all_count, currency, swapped_saving):
    spend = sum(p["display_price"] for p in rows)
    co2 = sum(p["co2"] for p in rows)
    extra = f'<span>Saved by swaps <b>{kg(swapped_saving)} kg</b></span>' if swapped_saving else ""
    return (f'<div class="ledger-totals"><span>Showing <b>{len(rows)}</b> of {all_count}</span>'
            f'<span>Spend <b>{esc(money(spend, currency))}</b></span><span>Footprint <b>{kg(co2)} kg</b></span>{extra}</div>')


def ledger_line(p, currency, max_co2):
    d = date.fromisoformat(p["date"])
    logo = p["brand_info"] and logo_uri(p["brand_info"]["name"])
    img = f'<img src="{logo}" alt="">' if logo else ""
    eth = f'<span class="eth" title="On the greener brands list">{gi("leaf")}</span>' if p["ethical_brand"] else ""
    sub = esc(p["type_name"]) if p["note"] else esc(p["group_name"])
    if p.get("swapped_from"):
        sub += f' · <span class="swapped-tag">swapped from {esc((p.get("swapped_from_name") or "").lower())}</span>'
    return (f'<div class="lg-line"><span class="lg-date"><b>{d.day}</b>{d.strftime("%a")}</span>'
            f'<span class="lg-item"><span class="g-icon">{gi(p["icon"])}</span><div><div class="r-name">'
            f'{esc(p["note"] or p["type_name"])}</div><div class="r-sub">{sub}</div></div></span>'
            f'<span class="lg-brand">{img}<span>{esc(p["brand"] or "—")}</span>{eth}</span>'
            f'<span class="lg-price">{esc(money(p["display_price"], currency))}</span>'
            f'<span class="lg-co2">{kg(p["co2"], 2)} kg<span class="minibar"><i style="width:{100 * p["co2"] / max_co2}%;'
            f'background:var(--{p["tier"]})"></i></span></span>'
            f'<span><span class="pill pill-{p["tier"]}">{p["tier"]}</span></span></div>')


# ---------------------------------------------------------------------------
# Swaps
# ---------------------------------------------------------------------------
def whatif_bars(now, after, pct):
    top = max(now, 1)
    return (f'<div class="wi-compare"><span>Now · {kg(now)} kg</span><div class="wi-bar before"><i style="width:{100 * now / top}%"></i></div>'
            f'<span>After swapping {pct}% · {kg(after)} kg</span><div class="wi-bar after"><i style="width:{100 * after / top}%"></i></div></div>')


def top_swap(t):
    brand = f' · {esc(t["brand"])}' if t["brand"] else ""
    return (f'<div class="ts-item"><span><b>{esc(t["type_name"])}</b>{brand}</span>'
            f'<span>→ {esc(t["to_name"])} <small>−{kg(t["saving"])} kg</small></span></div>')


def logo_wall(brands, type_names):
    cards = []
    for b in brands:
        uri = logo_uri(b["name"]) or ""
        kinds = " · ".join(type_names[t] for t in b["types"][:2] if t in type_names)
        cards.append(f'<div class="logo-card"><img src="{uri}" alt=""><div><b>{esc(b["name"])}</b>'
                     f'<small>{esc(kinds)}</small></div></div>')
    return f'<div class="logo-wall">{"".join(cards)}</div>'


def catalog(types, greener_for, max_multiplier):
    cards = []
    for t in types:
        meters = (f'<div class="pt-meter-row"><span>This choice</span><b>{t["multiplier"]:.2f} kg / £1</b></div>'
                  f'<div class="pt-track"><i style="width:{100 * t["multiplier"] / max_multiplier}%;background:var(--{t["tier"]})"></i></div>')
        if t["swap_to"]:
            meters += (f'<div class="pt-meter-row"><span>Greener swap</span><b>{t["swap_multiplier"]:.2f} kg / £1</b></div>'
                       f'<div class="pt-track"><i style="width:{100 * t["swap_multiplier"] / max_multiplier}%;background:var(--low)"></i></div>')
            lighter = round(100 * (1 - t["swap_multiplier"] / t["multiplier"]))
            body = (f'<div class="pt-swap">{gi("arrow")}<span>Swap to <b>{esc(t["swap_name"])}</b> · {lighter}% lighter</span></div>'
                    f'<p class="pt-why">{esc(t["swap_why"])}</p>')
        else:
            body = f'<p class="pt-good">{gi("leaf")}Already a light choice.</p>'
        chips = []
        for name in greener_for(t["swap_to"] or t["id"]):
            uri = logo_uri(name)
            img = f'<img src="{uri}" alt="">' if uri else ""
            chips.append(f'<span class="brand-chip">{img}{esc(name)}</span>')
        cards.append(f'<article class="pt-card"><div class="pt-top"><h3>{esc(t["name"])}</h3>'
                     f'<span class="pill pill-{t["tier"]}">{t["tier"]}</span></div><div class="pt-meter">{meters}</div>'
                     f'{body}<div class="brands">{"".join(chips)}</div></article>')
    return f'<div class="catalog">{"".join(cards)}</div>'


# ---------------------------------------------------------------------------
# Badges & garden
# ---------------------------------------------------------------------------
def badge_card(b, art_uri):
    if b["earned"]:
        tag = '<span class="earned-tag">Lifetime</span>' if b.get("lifetime") else '<span class="earned-tag">Earned</span>'
        hint = esc(b["hint"]) if b.get("lifetime") else "Unlocked this month."
    elif b.get("on_track"):
        tag = '<span class="earned-tag track-tag">On track</span>'
        hint = esc(b["hint"])
    else:
        tag, hint = "", esc(b["hint"])
    locked = "" if b["earned"] else " locked"
    return (f'<div class="badge-art{locked}"><img src="{art_uri}" alt=""></div>'
            f'<p class="badge-title">{esc(b["name"])}{tag}</p><p class="badge-blurb">{esc(b["blurb"])}</p>'
            f'<div class="bar badge-card-bar"><i style="width:{b["progress"] * 100}%"></i></div>'
            f'<span class="badge-hint">{hint}</span>')


def tree_key():
    return (card_head("How it grows") +
            '<dl class="key">'
            '<div><dt><span class="kdot k-branch"></span>Branches</dt><dd>More levels as your eco score rises.</dd></div>'
            '<div><dt><span class="kdot k-low"></span>Green leaves</dt><dd>Low-impact purchases.</dd></div>'
            '<div><dt><span class="kdot k-med"></span>Golden leaves</dt><dd>Medium-impact purchases.</dd></div>'
            '<div><dt><span class="kdot k-high"></span>Fallen leaves</dt><dd>One for each high-impact purchase.</dd></div>'
            '</dl>')


def quote(q):
    return f'<p class="quote">{esc(q["text"])}</p><p class="quote-by">— {esc(q["author"])}</p>'


def group_icon(group_id):
    return GROUPS[group_id]["icon"]


def icon_uri(name, color):
    return svg_uri(icon_svg(name, color))
