"""Design tokens, icons and the stylesheet for the Streamlit app.

Three themes share one stylesheet (style.css); only the token values change.
Lichen paper, moss ink, glacier blue — fern, ochre and clay are reserved for
impact tiers so colour always means something.
"""

from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).parent

TOKENS = {
    "light": {
        "bg": "#DCE4D2", "bg-deep": "#CFD9C3", "surface": "#F7F6EF", "surface-2": "#EDEFE4",
        "ink": "#1E3B2F", "ink-2": "#4B6155", "ink-3": "#5F7166",
        "line": "rgba(30, 59, 47, .13)", "line-strong": "rgba(30, 59, 47, .26)",
        "accent": "#2F6F8F", "accent-soft": "rgba(47, 111, 143, .12)",
        "low": "#3F7D48", "medium": "#8F6510", "high": "#B04E34",
        "low-soft": "rgba(78, 138, 87, .14)", "medium-soft": "rgba(212, 162, 58, .18)", "high-soft": "rgba(181, 84, 58, .13)",
        "counter": "#1E3B2F", "counter-2": "#284A3B", "counter-ink": "#EEF2E6", "counter-ink-2": "#B4C8B9",
        "key": "#F7F6EF", "key-ink": "#1E3B2F", "key-edge": "#B9C4AE",
        "paper": "#FBFAF4", "paper-ink": "#2B2F2A",
        "shadow": "0 1px 0 rgba(30,59,47,.05), 0 10px 30px -18px rgba(30,59,47,.35)",
        "scheme": "light",
    },
    "dark": {
        "bg": "#0F1713", "bg-deep": "#0B110E", "surface": "#17221C", "surface-2": "#1E2B24",
        "ink": "#E4EBDD", "ink-2": "#AABAAE", "ink-3": "#8FA295",
        "line": "rgba(228, 235, 221, .10)", "line-strong": "rgba(228, 235, 221, .22)",
        "accent": "#7FB6D1", "accent-soft": "rgba(127, 182, 209, .14)",
        "low": "#82C189", "medium": "#E2B65A", "high": "#E38466",
        "low-soft": "rgba(130, 193, 137, .14)", "medium-soft": "rgba(226, 182, 90, .14)", "high-soft": "rgba(227, 132, 102, .14)",
        "counter": "#20332A", "counter-2": "#2A4236", "counter-ink": "#EEF2E6", "counter-ink-2": "#A9BEAF",
        "key": "#DDE8CF", "key-ink": "#14241C", "key-edge": "#8FA184",
        "paper": "#FBFAF4", "paper-ink": "#2B2F2A",
        "shadow": "0 1px 0 rgba(0,0,0,.25), 0 14px 30px -18px rgba(0,0,0,.7)",
        "scheme": "dark",
    },
    "contrast": {
        "bg": "#000000", "bg-deep": "#000000", "surface": "#0A0A0A", "surface-2": "#161616",
        "ink": "#FFFFFF", "ink-2": "#F2F2F2", "ink-3": "#D6D6D6",
        "line": "rgba(255, 255, 255, .55)", "line-strong": "#FFFFFF",
        "accent": "#FFD60A", "accent-soft": "rgba(255, 214, 10, .2)",
        "low": "#4DFF91", "medium": "#FFD60A", "high": "#FF8A8A",
        "low-soft": "rgba(77, 255, 145, .18)", "medium-soft": "rgba(255, 214, 10, .18)", "high-soft": "rgba(255, 122, 122, .2)",
        "counter": "#000000", "counter-2": "#111111", "counter-ink": "#FFFFFF", "counter-ink-2": "#EDEDED",
        "key": "#FFD60A", "key-ink": "#000000", "key-edge": "#9C8200",
        "paper": "#FFFFFF", "paper-ink": "#000000",
        "shadow": "none",
        "scheme": "dark",
    },
}

THEME_NAMES = {"light": "Daylight", "dark": "Night canopy", "contrast": "High contrast"}

# Line icons (24×24, stroke) — the same set the web edition uses.
ICONS = {
    "shirt": '<path d="M8.5 3.5 3.5 6.5l2 5 2.5-1v10.5h8V10.5l2.5 1 2-5-5-3c-.6 1.6-2 2.8-3.5 2.8S9.1 5.1 8.5 3.5z"/>',
    "basket": '<path d="M3 10.5h18l-2.2 9.5H5.2z"/><path d="M8 10.5l3-6.5M16 10.5l-3-6.5M9 14v3M12 14v3M15 14v3"/>',
    "plug": '<path d="M9 3v5M15 3v5"/><path d="M6.5 8h11v3.5a5.5 5.5 0 0 1-11 0z"/><path d="M12 17v4"/>',
    "home": '<path d="M4 11 12 4l8 7v9.5H4z"/><path d="M10 20.5V15h4v5.5"/>',
    "drop": '<path d="M12 3.5s6 6.4 6 10.8a6 6 0 0 1-12 0C6 9.9 12 3.5 12 3.5z"/>',
    "route": '<circle cx="6" cy="18" r="2.3"/><circle cx="18" cy="6" r="2.3"/><path d="M8.3 18H16a3 3 0 0 0 0-6H8a3 3 0 0 1 0-6h7.7"/>',
    "gift": '<rect x="3.5" y="9" width="17" height="11.5" rx="1.5"/><path d="M3.5 13h17M12 9v11.5"/>'
            '<path d="M12 9C10.5 5 6.5 4.6 6.5 7S10 9 12 9s5.5.4 5.5-2-4-2-5.5 2z"/>',
    "wrench": '<path d="M15.2 3.6a4.6 4.6 0 0 0-3.9 6.7l-7.1 7.1a1.8 1.8 0 0 0 2.5 2.5l7.1-7.1a4.6 4.6 0 0 0 6.7-3.9l-2.9 1.4-2.4-2.4z"/>',
    "leaf": '<path d="M5 19C5 10.5 10 5 19 5c0 9-5.5 14-14 14z"/><path d="M5 19l8.5-8.5"/>',
    "arrow": '<path d="M4 12h15M14 7l5 5-5 5"/>',
    "swap": '<path d="M4 8h14l-3.5-3.5M20 16H6l3.5 3.5"/>',
}


def icon_svg(name, color="#000", width=1.75):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</svg>')


def _icon_css():
    rules = [".gi{display:inline-block;width:1.15em;height:1.15em;flex:none;background:currentColor;"
             "-webkit-mask:var(--m) center/contain no-repeat;mask:var(--m) center/contain no-repeat;}"]
    for name in ICONS:
        url = "data:image/svg+xml;utf8," + quote(icon_svg(name))
        rules.append(f'.gi-{name}{{--m:url("{url}");}}')
    return "\n".join(rules)


@lru_cache(maxsize=1)
def _base_css():
    return (HERE / "style.css").read_text(encoding="utf-8") + "\n" + _icon_css()


def stylesheet(theme="light", text="regular", motion="full"):
    """The full <style> block for one theme / text size / motion setting."""
    tokens = TOKENS.get(theme, TOKENS["light"])
    root = ";".join(f"--{k}:{v}" for k, v in tokens.items() if k != "scheme")
    size = "19.5px" if text == "large" else "17px"
    extra = ""
    if motion == "reduced":
        extra = ("*,*::before,*::after{animation-duration:.01ms!important;animation-iteration-count:1!important;"
                 "transition-duration:.01ms!important}")
    return (f"<style>:root{{{root};--base-size:{size};color-scheme:{tokens['scheme']}}}\n"
            f"{_base_css()}\n{extra}</style>")


def chart_colors(theme="light"):
    t = TOKENS.get(theme, TOKENS["light"])
    return {k: t[k] for k in ("ink", "ink-2", "ink-3", "line", "accent", "low", "medium", "high", "surface")}
