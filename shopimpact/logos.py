"""Brand logos.

The browser asks our server for /api/logo/<domain>. We fetch the brand's
website icon from a public favicon service, keep it in memory, and send it
back with a long cache header. If no icon exists we draw a monogram (the
brand's initials on a colour derived from its name) so every brand still gets
a tidy badge. Only domains in brands.py are accepted, so the endpoint can't be
used as an open proxy.
"""

import hashlib
import os
import ssl
import threading
import urllib.error
import urllib.request
from xml.sax.saxutils import escape

try:  # python.org builds on macOS ship without CA certificates
    import certifi
    _SSL = ssl.create_default_context(cafile=certifi.where())
except ImportError:  # pragma: no cover
    _SSL = ssl.create_default_context()

SOURCES = (  # tried in order until one returns an image
    "https://www.google.com/s2/favicons?domain={domain}&sz=64",
    "https://www.google.com/s2/favicons?domain=www.{domain}&sz=64",
    "https://icons.duckduckgo.com/ip3/{domain}.ico",
    "https://icon.horse/icon/{domain}",
    "https://www.{domain}/favicon.ico",
)
TIMEOUT = 4
MAX_BYTES = 200_000
_cache = {}
_lock = threading.Lock()

# Muted, earthy monogram colours that sit well on the app's paper.
PALETTE = ["#2F6F8F", "#4E8A57", "#7A6A3A", "#A2553F", "#45607A", "#5B4B8A", "#2E7C7A", "#8A5A2B"]


def monogram_svg(name):
    """Initials on a rounded square — the fallback logo."""
    words = [w for w in name.replace("&", " ").replace("-", " ").split() if w[:1].isalnum()]
    initials = "".join(w[0] for w in words[:2]).upper() or name[:1].upper()
    colour = PALETTE[int(hashlib.md5(name.encode()).hexdigest(), 16) % len(PALETTE)]
    size = 30 if len(initials) == 1 else 25
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
            f'<rect width="64" height="64" rx="14" fill="{colour}"/>'
            f'<text x="32" y="33" dy=".35em" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" '
            f'font-weight="700" font-size="{size}" fill="#F7F6EF">{escape(initials)}</text></svg>').encode()


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; ShopImpact/1.0; logo fetcher)"})
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=_SSL) as res:
        ctype = res.headers.get("Content-Type", "")
        if res.status != 200 or not ctype.startswith("image/"):
            return None
        if res.headers.get("X-Icon-Fallback", "").lower() == "true":
            return None  # a generic letter placeholder — our own monogram looks better
        body = res.read(MAX_BYTES + 1)
        if not body or len(body) > MAX_BYTES:
            return None
        return body, ctype


def get_logo(domain, name):
    """(bytes, content type, is_real_logo) for a brand domain, cached in memory."""
    with _lock:
        if domain in _cache:
            return _cache[domain]
    result = None
    offline = os.environ.get("SHOPIMPACT_LOGOS", "1") == "0"  # tests run without the network
    for template in () if offline else SOURCES:
        try:
            got = _fetch(template.format(domain=domain))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            got = None
        if got:
            result = (got[0], got[1], True)
            break
    if result is None:
        result = (monogram_svg(name), "image/svg+xml", False)
    with _lock:
        _cache[domain] = result
    return result
