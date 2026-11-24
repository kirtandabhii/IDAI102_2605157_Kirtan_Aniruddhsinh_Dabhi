"""Brand logos for the Streamlit app.

Each logo is fetched once (see shopimpact/logos.py) and kept two ways:
  * a data URI, for logos drawn inside the app's HTML cards and receipts;
  * a small file in static/logos/, served by Streamlit's static file serving
    (server.enableStaticServing) so the brand dropdown can show it next to
    every option without sending all 461 images to the browser.

A background thread warms the whole collection on first start. The folder is
a cache — it is git-ignored and rebuilt on any server.
"""

import base64
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .. import logos
from ..brands import BRANDS, lookup

STATIC_DIR = Path(__file__).resolve().parents[2] / "static" / "logos"
URL_PREFIX = "app/static/logos/"   # Streamlit serves ./static at /app/static/
EXTENSIONS = {"image/png": "png", "image/x-icon": "ico", "image/vnd.microsoft.icon": "ico",
              "image/svg+xml": "svg", "image/jpeg": "jpg", "image/gif": "gif", "image/webp": "webp",
              "image/avif": "avif"}

_uris = {}       # domain -> data URI
_files = {}      # domain -> file name in static/logos
_lock = threading.Lock()
_warming = False


def _safe_name(domain):
    return re.sub(r"[^a-z0-9.-]", "_", domain.lower())


def _scan_existing():
    """Files from an earlier run are reused straight away."""
    if not STATIC_DIR.is_dir():
        return
    by_stem = {p.stem: p.name for p in STATIC_DIR.iterdir() if p.is_file()}
    for brand in BRANDS:
        name = by_stem.get(_safe_name(brand["domain"]))
        if name:
            _files[brand["domain"]] = name


_scan_existing()


def _store(brand):
    body, ctype, _real = logos.get_logo(brand["domain"], brand["name"])
    ctype = ctype.split(";")[0].strip()
    uri = f"data:{ctype};base64,{base64.b64encode(body).decode()}"
    file_name = None
    ext = EXTENSIONS.get(ctype)
    offline = os.environ.get("SHOPIMPACT_LOGOS", "1") == "0"   # tests: never cache monograms as files
    if ext and not offline:
        file_name = f"{_safe_name(brand['domain'])}.{ext}"
        try:
            STATIC_DIR.mkdir(parents=True, exist_ok=True)
            path = STATIC_DIR / file_name
            if not path.exists():
                path.write_bytes(body)
        except OSError:
            file_name = None  # read-only disk: the data URI still works
    with _lock:
        _uris[brand["domain"]] = uri
        if file_name:
            _files[brand["domain"]] = file_name
    return uri


def logo_uri(name):
    """Data URI for a brand's logo (or its monogram); None for unknown brands."""
    brand = lookup(name)
    if not brand:
        return None
    with _lock:
        if brand["domain"] in _uris:
            return _uris[brand["domain"]]
    return _store(brand)


def dropdown_logo_urls():
    """{brand name: URL} for every logo already saved as a file — used by the brand dropdown."""
    with _lock:
        return {b["name"]: URL_PREFIX + _files[b["domain"]] for b in BRANDS if b["domain"] in _files}


def prefetch(names, workers=8):
    """Fetch several logos in parallel (used before drawing a list)."""
    todo = []
    for name in names:
        brand = lookup(name)
        if brand and brand["domain"] not in _uris:
            todo.append(brand["name"])
    if todo:
        with ThreadPoolExecutor(workers) as pool:
            list(pool.map(logo_uri, todo))


def warm_all():
    """Start fetching every logo in the background (once per server)."""
    global _warming
    with _lock:
        if _warming:
            return
        _warming = True
    threading.Thread(target=prefetch, args=([b["name"] for b in BRANDS], 12), daemon=True).start()
