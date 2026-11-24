"""ShopImpact — conscious shopping dashboard (Streamlit app).

Run locally:      streamlit run app.py
Deploy:           Streamlit Community Cloud → main file: app.py

How it fits together
--------------------
    app.py                 this file: page set-up, the shopper's id, routing
    shopimpact/service.py  every rule — validation, CO₂, budgets, badges
    shopimpact/engine.py   the maths (pure functions on lists of dicts)
    shopimpact/ui/views.py the six screens, built from Streamlit widgets
    shopimpact/ui/*        theme (CSS), charts (Altair), HTML cards, browser runtime

Python computes every number; the screens only display them.
"""

import base64
import json
import os
import re
import uuid
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st

from shopimpact import rates
from shopimpact.engine import month_key
from shopimpact.service import Service
from shopimpact.store import Store
from shopimpact.ui import views
from shopimpact.ui.html import js_string
from shopimpact.ui.logo_cache import dropdown_logo_urls, warm_all
from shopimpact.ui.theme import stylesheet

BASE_DIR = Path(__file__).parent
DB_PATH = os.environ.get("SHOPIMPACT_DB", str(BASE_DIR / "instance" / "shopimpact.db"))
# The browser runtime is sent base64-encoded: st.html's sanitiser removes scripts whose
# text contains HTML-like snippets, and the runtime builds SVG with them.
RUNTIME_B64 = base64.b64encode((BASE_DIR / "shopimpact" / "ui" / "runtime.js").read_bytes()).decode()
RUNTIME_LOADER = ("(function(){var b=atob('" + RUNTIME_B64 + "');var u=new Uint8Array(b.length);"
                  "for(var i=0;i!==b.length;i++)u[i]=b.charCodeAt(i);"
                  "new Function(new TextDecoder().decode(u))();})();")

st.set_page_config(page_title="ShopImpact — conscious shopping", page_icon="🐢", layout="wide",
                   initial_sidebar_state="collapsed")


@st.cache_resource
def get_service():
    """One database connection pool and service for every visitor."""
    warm_all()  # start fetching brand logos in the background
    return Service(Store(DB_PATH))


def shopper_id():
    """Anonymous id kept in the page link (?id=…).

    On a visit without one, the browser looks for the id it saved last time
    (localStorage) and comes back with it; a first-time visitor gets a new one.
    """
    sid = st.query_params.get("id", "")
    if re.fullmatch(r"[0-9a-f]{32}", sid or ""):
        return sid
    fresh = uuid.uuid4().hex
    st.html("<div class='si-runtime'></div><script>(function(){var k='shopimpact.id';var id=null;"
            "try{id=localStorage.getItem(k);}catch(e){}"
            f"if(!id||!/^[0-9a-f]{{32}}$/.test(id)){{id='{fresh}';}}"
            "var u=new URL(window.location.href);u.searchParams.set('id',id);window.location.replace(u.toString());})();"
            "</script>", unsafe_allow_javascript=True)
    st.html(f'<p style="padding:2rem;font-family:sans-serif">Opening your ledger… '
            f'<a href="?id={fresh}">Continue</a></p>')
    st.stop()


def local_now():
    """The shopper's own clock (from their browser's time zone), not the server's."""
    try:
        tz = st.context.timezone
        return datetime.now(ZoneInfo(tz)) if tz else datetime.now()
    except Exception:
        return datetime.now()


def main():
    service = get_service()
    rates.ensure_fresh()
    sid = shopper_id()
    now = local_now()
    today = now.date()
    s = st.session_state
    s.setdefault("month", month_key(today))
    s.setdefault("view", st.query_params.get("view", "overview"))
    if s.view not in {v[0] for v in views.VIEWS}:
        s.view = "overview"

    prefs = service.ui_prefs(sid)
    st.html(stylesheet(prefs["theme"], prefs["text"], prefs["motion"]))
    st.html(f'<div class="si-runtime"></div><script>{RUNTIME_LOADER}</script>', unsafe_allow_javascript=True)

    state = service.state(sid, s.month, today)
    config = {"sound": prefs["sound"], "volume": prefs["volume"], "motion": prefs["motion"],
              "speed": prefs["speed"], "priceStep": state["currency"]["slider_step"], "sid": sid}
    st.html(f'<div class="si-runtime"></div><script>(function go(){{ if(!window.ShopImpact) return setTimeout(go, 40);'
            f' Object.assign(window.ShopImpact.config, JSON.parse({js_string(json.dumps(config))})); }})();</script>',
            unsafe_allow_javascript=True)

    # Logos for the brand dropdown (files served from ./static/logos).
    logo_map = js_string(json.dumps(dropdown_logo_urls()))
    st.html(f'<div class="si-runtime"></div><script>(function go(){{ if(!window.ShopImpact) return setTimeout(go, 40);'
            f' window.ShopImpact.brandLogos = JSON.parse({logo_map}); window.ShopImpact.decorateBrand(); }})();</script>',
            unsafe_allow_javascript=True)

    views.rail(s.view, prefs, service, sid)
    now_text = now.strftime("%d %b %Y, %H:%M")
    name = state["settings"].get("name") or ""
    titles = {
        "overview": (f"Overview · {state['summary']['label']}", views.greeting(name, now)),
        "ledger": ("Every purchase this month", "Your ledger"),
        "swaps": ("Lighter choices", "Greener swaps"),
        "badges": ("Rewards", "Badges"),
        "garden": ("Turtle graphics", "Your garden"),
        "settings": ("Preferences", "Settings"),
    }
    views.topbar(*titles[s.view], state)

    if s.view == "overview":
        views.overview(state, service, sid, today, prefs, now_text)
    elif s.view == "ledger":
        views.ledger(state, service, sid, today)
    elif s.view == "swaps":
        views.swaps(state, service, sid, today)
    elif s.view == "badges":
        views.badges(state)
    elif s.view == "garden":
        views.garden(state, service, sid, today, prefs)
    else:
        share = f"{st.context.url.split('?')[0]}?id={sid}" if st.context.url else f"?id={sid}"
        views.settings(state, service, sid, today, prefs, dict(rates.STATUS), share)

    # Month-long badges from a month that just ended are celebrated once.
    if state.get("celebrate"):
        s.badge_queue = s.get("badge_queue", []) + state["celebrate"]
    for message, icon in s.pop("toasts", []):
        st.toast(message, icon=icon)
    views.run_dialogs(state, service, sid, today)


main()
