"""Live exchange rates.

The app starts with the built-in estimates in world.py. In the background it
asks ExchangeRate-API's free open endpoint for today's rates (at most every six
hours) and updates every currency in place. If the network is down nothing
changes — the built-in rates keep working.

Set SHOPIMPACT_LIVE_RATES=0 to switch this off (the tests do).
"""

import json
import os
import threading
import time
import urllib.request

from . import catalog
from .logos import _SSL

URL = "https://open.er-api.com/v6/latest/USD"
REFRESH_EVERY = 6 * 3600
STATUS = {"source": "built-in estimates", "updated": None}
_lock = threading.Lock()
_last_try = 0.0


def refresh():
    """Fetch today's rates and apply them. Returns True on success."""
    req = urllib.request.Request(URL, headers={"User-Agent": "ShopImpact/1.0"})
    with urllib.request.urlopen(req, timeout=6, context=_SSL) as res:
        data = json.loads(res.read(500_000))
    if data.get("result") != "success" or not isinstance(data.get("rates"), dict):
        return False
    catalog.update_rates(data["rates"])
    STATUS.update(source="ExchangeRate-API", updated=data.get("time_last_update_utc"))
    return True


def _safe_refresh():
    try:
        refresh()
    except Exception:  # network trouble: keep the rates we have
        pass


def ensure_fresh():
    """Start a background refresh if the rates are stale. Never blocks a request."""
    global _last_try
    if os.environ.get("SHOPIMPACT_LIVE_RATES", "1") == "0":
        return
    now = time.time()
    with _lock:
        if now - _last_try < REFRESH_EVERY:
            return
        _last_try = now
    threading.Thread(target=_safe_refresh, daemon=True).start()
