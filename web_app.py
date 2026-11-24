"""ShopImpact — optional standalone web edition (Flask).

The assessed app is the Streamlit app in app.py. This edition serves the same
Python logic (shopimpact/service.py) to a hand-built browser front end, for
hosts that don't run Streamlit.

Run locally:   python web_app.py         (http://127.0.0.1:5050)
Production:    gunicorn web_app:app
"""

import os
import uuid
from datetime import date

from flask import Flask, Response, g, jsonify, make_response, render_template, request

from shopimpact import __version__, drawings, logos, rates
from shopimpact.badges import BADGES_BY_ID
from shopimpact.brands import BRANDS, brands_payload
from shopimpact.catalog import catalog_payload
from shopimpact.content import ECO_TIPS, QUOTES, random_quote
from shopimpact.engine import estimate, is_valid_month, month_key
from shopimpact.service import Service, ValidationError
from shopimpact.store import Store

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("SHOPIMPACT_DB", os.path.join(BASE_DIR, "instance", "shopimpact.db"))
COOKIE = "shopimpact_id"

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True  # page edits show up without a restart
store = Store(DB_PATH)
service = Service(store)
_BRAND_BY_DOMAIN = {b["domain"]: b for b in BRANDS}


def _asset_version():
    """Changes whenever a CSS/JS file changes, so browsers never use stale copies."""
    newest = 0.0
    for root, _, files in os.walk(os.path.join(BASE_DIR, "static")):
        for name in files:
            newest = max(newest, os.path.getmtime(os.path.join(root, name)))
    return f"{__version__}-{int(newest)}"


# ---------------------------------------------------------------------------
# Anonymous shopper id (cookie)
# ---------------------------------------------------------------------------
@app.before_request
def identify_shopper():
    sid = request.cookies.get(COOKIE)
    g.new_sid = not sid
    g.sid = sid or uuid.uuid4().hex
    rates.ensure_fresh()  # refreshes exchange rates in the background, at most every 6 hours


@app.after_request
def remember_shopper(response):
    if getattr(g, "new_sid", False):
        response.set_cookie(COOKIE, g.sid, max_age=60 * 60 * 24 * 365 * 2, httponly=True, samesite="Lax")
    return response


def today():
    return date.today()


def error(message, status=400):
    return jsonify({"ok": False, "error": message}), status


@app.errorhandler(ValidationError)
def on_validation(err):
    return error(str(err))


@app.errorhandler(LookupError)
def on_missing(err):
    return error(str(err), 404)


def month_arg():
    key = request.args.get("month") or month_key(today())
    if not is_valid_month(key):
        raise ValidationError("Month must look like 2026-11.")
    return key


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
@app.get("/")
def index():
    return render_template("index.html", version=_asset_version())


@app.get("/healthz")
def health():
    return {"ok": True, "version": __version__}


# ---------------------------------------------------------------------------
# API — every rule lives in shopimpact/service.py
# ---------------------------------------------------------------------------
@app.get("/api/catalog")
def api_catalog():
    art = {b["id"]: drawings.render("badge", color=b["color"], emblem=b["emblem"], name=b["name"])
           for b in BADGES_BY_ID.values()}
    return jsonify({"ok": True, **catalog_payload(), "brands": brands_payload(), "tips": ECO_TIPS,
                    "quotes": [{"text": t, "author": a} for t, a in QUOTES], "badge_art": art})


@app.get("/api/logo/<path:domain>")
def api_logo(domain):
    """A brand's logo (or a monogram), cached for a week in the browser."""
    brand = _BRAND_BY_DOMAIN.get(domain.lower())
    if not brand:
        return error("Unknown brand.", 404)
    body, ctype, real = logos.get_logo(brand["domain"], brand["name"])
    response = Response(body, mimetype=ctype.split(";")[0])
    response.headers["Cache-Control"] = "public, max-age=604800, immutable" if real else "public, max-age=86400"
    response.headers["X-Logo-Source"] = "favicon" if real else "monogram"
    return response


@app.get("/api/state")
def api_state():
    state = service.state(g.sid, month_arg(), today())
    state["quote"] = random_quote()
    state["rates"] = dict(rates.STATUS)
    return jsonify(state)


@app.post("/api/estimate")
def api_estimate():
    data = request.get_json(silent=True) or {}
    settings = store.settings(g.sid)
    return jsonify(estimate(data.get("product_type"), data.get("price"), settings["currency"],
                            data.get("brand", ""), data.get("swapped_from")))


@app.post("/api/purchases")
def api_add():
    return jsonify(service.add(g.sid, request.get_json(silent=True) or {}, today()))


@app.post("/api/purchases/<int:purchase_id>/swap")
def api_swap(purchase_id):
    data = request.get_json(silent=True) or {}
    return jsonify(service.swap(g.sid, purchase_id, today(), data.get("to"), data.get("brand")))


@app.delete("/api/purchases/<int:purchase_id>")
def api_delete(purchase_id):
    return jsonify(service.delete(g.sid, purchase_id, today()))


@app.post("/api/purchases/restore")
def api_restore():
    return jsonify(service.restore(g.sid, request.get_json(silent=True) or {}, today()))


@app.post("/api/settings")
def api_settings():
    month = request.args.get("month")
    return jsonify(service.update_settings(g.sid, request.get_json(silent=True) or {}, today(), month))


@app.post("/api/demo")
def api_demo():
    return jsonify(service.load_demo(g.sid, today()))


@app.post("/api/reset")
def api_reset():
    return jsonify(service.reset(g.sid, today()))


@app.get("/api/drawing/<kind>")
def api_drawing(kind):
    """Turtle drawings on demand: reward drawings, badge emblems and the monthly tree."""
    if kind in ("sprig", "steps", "deep_step"):
        return jsonify({"ok": True, "svg": drawings.render(kind)})
    if kind == "badge":
        info = BADGES_BY_ID.get(request.args.get("id", ""))
        if not info:
            return error("Unknown badge.", 404)
        return jsonify({"ok": True, "svg": drawings.render("badge", color=info["color"],
                                                           emblem=info["emblem"], name=info["name"])})
    if kind == "tree":
        return jsonify({"ok": True, "svg": service.tree_svg(g.sid, month_arg(), today())})
    return error("Unknown drawing.", 404)


@app.get("/api/export.csv")
def api_export():
    filename, text = service.export_csv(g.sid, month_arg(), today())
    response = make_response(text)
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0" if os.environ.get("PORT") else "127.0.0.1", port=port,
            debug=os.environ.get("FLASK_DEBUG") == "1")
