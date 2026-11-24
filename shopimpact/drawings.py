"""Turtle drawings used as rewards across the app.

Every function here uses only the standard turtle API (forward, left, circle,
begin_fill, dot, goto, ...). They receive a turtle `t`, which can be our
SvgTurtle (for the web app) or a real `turtle.Turtle()` (turtle_window.py).

    sprig      a leafy sprig  -> low-impact purchase
    steps      two light footprints -> medium-impact purchase
    deep_step  one heavy footprint  -> high-impact purchase
    badge      a ribbon rosette with an emblem -> badge unlocked
    tree       a recursive tree that grows with the month's eco score
"""

import math
import random

from .turtle_svg import SvgTurtle

# Palette (matches the app's CSS tokens).
MOSS = "#1E3B2F"
FERN = "#4E8A57"
FERN_LIGHT = "#7DAE6B"
SAGE = "#A9C48F"
GLACIER = "#2F6F8F"
GLACIER_LIGHT = "#7FB0C6"
OCHRE = "#D4A23A"
CLAY = "#B5543A"
BARK = "#5A4632"
SOIL = "#8A7353"
PAPER = "#F7F6EF"


def shade(hex_color, amount):
    """Lighten (amount > 0) or darken (amount < 0) a #RRGGBB colour."""
    hex_color = hex_color.lstrip("#")
    rgb = [int(hex_color[i:i + 2], 16) for i in (0, 2, 4)]
    if amount >= 0:
        rgb = [round(c + (255 - c) * amount) for c in rgb]
    else:
        rgb = [round(c * (1 + amount)) for c in rgb]
    return "#" + "".join(f"{max(0, min(255, c)):02x}" for c in rgb)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _jump(t, x, y, heading=None):
    """Move without drawing."""
    t.penup()
    t.goto(x, y)
    if heading is not None:
        t.setheading(heading)
    t.pendown()


def _centered(t, fn, cx, cy, *args):
    """Draw `fn` so that its bounding box is centred on (cx, cy).

    We 'dry run' the drawing on an invisible SvgTurtle to measure it first.
    """
    probe = SvgTurtle()
    probe.penup()
    fn(probe, *args)
    x0, y0, x1, y1 = probe.bounds()
    _jump(t, cx - (x0 + x1) / 2, cy - (y0 + y1) / 2, 0)
    fn(t, *args)


def _arrowhead(t, length, width, color):
    """Filled triangle pointing along the turtle's heading."""
    x, y = t.position()
    h = math.radians(t.heading())
    px, py = -math.sin(h), math.cos(h)  # perpendicular
    tip = (x + math.cos(h) * length, y + math.sin(h) * length)
    a = (x + px * width, y + py * width)
    b = (x - px * width, y - py * width)
    t.color(color, color)
    t.penup()
    t.goto(a)
    t.pendown()
    t.begin_fill()
    t.goto(tip)
    t.goto(b)
    t.goto(a)
    t.end_fill()


# ---------------------------------------------------------------------------
# Leaf
# ---------------------------------------------------------------------------
def leaf(t, r, fill=FERN, vein=MOSS, width=2.5):
    """A lens-shaped leaf grown along the turtle's current heading."""
    start = t.position()
    heading = t.heading()
    chord = r * math.sqrt(2)          # base-to-tip length
    offset = r * math.cos(math.radians(45))

    def half_width(s):                # leaf half-width at distance s from base
        inside = r * r - (s - chord / 2) ** 2
        return max(math.sqrt(max(inside, 0)) - offset, 0)

    # Outline + fill: two quarter circles meeting at base and tip.
    t.pensize(width)
    t.color(vein, fill)
    t.pendown()
    t.right(45)
    t.begin_fill()
    t.circle(r, 90)
    t.left(90)
    t.circle(r, 90)
    t.end_fill()
    t.left(135)

    # Midrib with pairs of side veins.
    t.pensize(width * 0.7)
    travelled = 0.0
    angle = 38
    for frac in (0.3, 0.5, 0.7):
        s = chord * frac
        t.forward(s - travelled)
        travelled = s
        v = 0.0
        for _ in range(12):  # solve: vein end sits ~75% of the way to the edge
            v = 0.75 * half_width(s + v * math.cos(math.radians(angle))) / math.sin(math.radians(angle))
        for side in (1, -1):
            t.left(angle * side)
            t.forward(v)
            t.penup()
            t.backward(v)
            t.pendown()
            t.right(angle * side)
    t.forward(chord * 0.9 - travelled)
    t.penup()
    t.goto(start)
    t.setheading(heading)
    t.pendown()


def draw_sprig(t):
    """Low-impact reward: a curved stem with three leaves."""
    _jump(t, 0, -70, 84)
    t.pensize(5)
    t.pencolor(MOSS)
    t.circle(260, 12)
    joint, joint_heading = t.position(), t.heading()
    t.circle(260, 13)
    leaf(t, 72, FERN, MOSS, 3)
    for turn, stem, size, colour in ((50, 14, 44, FERN_LIGHT), (-54, 10, 36, SAGE)):
        _jump(t, joint[0], joint[1], joint_heading + turn)
        t.pensize(4)
        t.pencolor(MOSS)
        t.forward(stem)
        leaf(t, size, colour, MOSS, 2.5)


# ---------------------------------------------------------------------------
# Footprints
# ---------------------------------------------------------------------------
def footprint(t, size=100, fill=GLACIER, mirror=False, tilt=0.0):
    """A footprint centred on the turtle's position (y axis = heel to toe)."""
    cx, cy = t.position()
    a, b = 0.30 * size, 0.55 * size     # half width, half height of the sole
    side = -1 if mirror else 1
    rot = math.radians(tilt)

    def place(x, y):
        x *= side
        return (cx + x * math.cos(rot) - y * math.sin(rot),
                cy + x * math.sin(rot) + y * math.cos(rot))

    points = []
    steps = 64
    for i in range(steps + 1):
        theta = 2 * math.pi * i / steps
        u = math.sin(theta)                       # -1 heel ... +1 ball
        x = a * math.cos(theta) * (0.80 + 0.22 * u)
        if math.cos(theta) > 0:                   # the arch on the inner side
            x *= 1 - 0.42 * math.exp(-((u + 0.05) / 0.40) ** 2)
        points.append(place(x, b * u))

    t.pensize(2.5)
    t.color(shade(fill, -0.35), fill)
    t.penup()
    t.goto(points[0])
    t.pendown()
    t.begin_fill()
    for p in points[1:]:
        t.goto(p)
    t.end_fill()

    # Toes: big toe on the arch side, getting smaller outwards.
    for i in range(5):
        tx = a * (0.72 - 0.40 * i)
        ty = b * (1.22 - 0.06 * i ** 1.5)
        t.penup()
        t.goto(place(tx, ty))
        t.dot(size * (0.19 - 0.024 * i), fill)
    t.penup()
    t.goto(cx, cy)
    t.pendown()


def draw_steps(t):
    """Medium-impact reward: a light pair of steps."""
    _jump(t, -34, -44)
    footprint(t, 96, GLACIER_LIGHT, mirror=False, tilt=6)
    _jump(t, 38, 46)
    footprint(t, 96, GLACIER, mirror=True, tilt=-6)


def draw_deep_step(t):
    """High-impact reward: one heavier footprint with a dashed ground line."""
    _jump(t, -110, -88, 0)
    t.pensize(3)
    t.pencolor(SOIL)
    for _ in range(9):
        t.forward(14)
        t.penup()
        t.forward(10)
        t.pendown()
    _jump(t, 0, 0)
    footprint(t, 150, CLAY, mirror=False, tilt=4)


# ---------------------------------------------------------------------------
# Badge emblems (drawn relative to the turtle so _centered can place them)
# ---------------------------------------------------------------------------
def emblem_star(t, s, c):
    t.color(c, c)
    t.pensize(2)
    t.begin_fill()
    for _ in range(5):
        t.forward(s)
        t.right(144)
    t.end_fill()


def emblem_leaf(t, s, c):
    t.left(62)
    leaf(t, s * 0.78, c, shade(c, -0.45), 2.2)


def emblem_loop(t, s, c):
    t.pencolor(c)
    t.pensize(s * 0.13)
    t.circle(s * 0.42, 290)
    _arrowhead(t, s * 0.26, s * 0.17, c)


def emblem_heart(t, s, c):
    length = s * 0.62
    t.color(c, c)
    t.pensize(2)
    t.begin_fill()
    t.left(140)
    t.forward(length)
    t.circle(-length * 0.513, 200)
    t.left(120)
    t.circle(-length * 0.513, 200)
    t.forward(length)
    t.end_fill()


def emblem_bolt(t, s, c):
    x, y = t.position()
    shape = [(0.10, 0.50), (-0.24, -0.04), (0.0, -0.04), (-0.12, -0.50),
             (0.26, 0.08), (0.02, 0.08), (0.16, 0.50)]
    t.color(c, c)
    t.pensize(2)
    t.begin_fill()
    for px, py in shape + shape[:1]:
        t.goto(x + px * s, y + py * s)
    t.end_fill()


def emblem_sprout(t, s, c):
    x, y = t.position()
    t.pencolor(c)
    t.pensize(s * 0.1)
    t.setheading(90)
    t.forward(s * 0.55)
    top = t.position()
    for turn in (38, -38):
        t.penup()
        t.goto(top)
        t.setheading(90 + turn)
        t.pendown()
        leaf(t, s * 0.34, c, shade(c, -0.45), 1.6)
    t.penup()
    t.goto(x, y)
    t.pendown()


def emblem_check(t, s, c):
    t.pencolor(c)
    t.pensize(s * 0.15)
    t.setheading(-45)
    t.forward(s * 0.34)
    t.left(90)
    t.forward(s * 0.72)


def emblem_swap(t, s, c):
    x, y = t.position()
    t.pencolor(c)
    t.pensize(s * 0.1)
    _jump(t, x - s * 0.4, y + s * 0.18, 0)
    t.pencolor(c)
    t.forward(s * 0.62)
    _arrowhead(t, s * 0.22, s * 0.15, c)
    _jump(t, x + s * 0.4, y - s * 0.18, 180)
    t.pencolor(c)
    t.pensize(s * 0.1)
    t.forward(s * 0.62)
    _arrowhead(t, s * 0.22, s * 0.15, c)


def emblem_arrow(t, s, c):
    t.pencolor(c)
    t.pensize(s * 0.14)
    t.setheading(270)
    t.forward(s * 0.5)
    _arrowhead(t, s * 0.3, s * 0.24, c)


def emblem_footprint(t, s, c):
    footprint(t, s * 1.15, c, mirror=False, tilt=8)


EMBLEMS = {
    "star": emblem_star, "leaf": emblem_leaf, "loop": emblem_loop, "heart": emblem_heart,
    "bolt": emblem_bolt, "sprout": emblem_sprout, "check": emblem_check,
    "swap": emblem_swap, "arrow": emblem_arrow, "footprint": emblem_footprint,
}


def draw_badge(t, color=FERN, emblem="star", radius=80, scallops=14):
    """A ribbon rosette: two tails, a scalloped disc, a ring and an emblem."""
    dark = shade(color, -0.32)
    # Ribbon tails first so the rosette sits on top of them.
    tail = [(-34, -16), (-4, -16), (-20, -132), (-36, -114), (-54, -126)]
    for mirror in (1, -1):
        pts = [(x * mirror, y) for x, y in tail]
        t.pensize(2.5)
        t.color(shade(dark, -0.15), dark)
        t.penup()
        t.goto(pts[0])
        t.pendown()
        t.begin_fill()
        for p in pts[1:] + pts[:1]:
            t.goto(p)
        t.end_fill()

    # Scalloped disc: a semicircle bulging outwards between neighbouring points.
    bump = radius * math.sin(math.pi / scallops)
    t.pensize(2.5)
    t.color(dark, color)
    _jump(t, radius, 0, 180 / scallops)
    t.begin_fill()
    for _ in range(scallops):
        t.circle(bump, 180)
        t.right(180 - 360 / scallops)
    t.end_fill()

    # Inner ring.
    ring = radius * 0.74
    _jump(t, 0, -ring, 0)
    t.pensize(2.5)
    t.pencolor(shade(color, 0.55))
    t.circle(ring)

    # Emblem in the middle.
    _centered(t, EMBLEMS.get(emblem, emblem_star), 0, 0, radius * 0.9, PAPER)


# ---------------------------------------------------------------------------
# The monthly tree
# ---------------------------------------------------------------------------
def _branch(t, length, depth, rng, leaf_colors, leaf_weights):
    t.pensize(max(1.2, depth * 1.5))
    t.pencolor(BARK)
    t.forward(length)
    if depth <= 0 or length < 5:
        t.dot(rng.uniform(8, 13), rng.choices(leaf_colors, leaf_weights)[0])
    else:
        a, b = rng.uniform(16, 32), rng.uniform(16, 32)
        t.left(a)
        _branch(t, length * rng.uniform(0.66, 0.8), depth - 1, rng, leaf_colors, leaf_weights)
        t.right(a + b)
        _branch(t, length * rng.uniform(0.66, 0.8), depth - 1, rng, leaf_colors, leaf_weights)
        t.left(b)
    t.penup()
    t.backward(length)
    t.pendown()


def draw_tree(t, score=None, low=0, medium=0, high=0, seed=11):
    """A recursive tree. Greener months grow deeper trees with greener leaves.

    depth   = 3..8 from the eco score (a sapling if there is no data yet)
    leaves  = green for low-impact buys, ochre for medium, clay for high
    on the ground: one fallen leaf per high-impact purchase
    """
    rng = random.Random(seed)
    depth = 2 if score is None else 3 + round(score / 100 * 5)
    total = low + medium + high
    weights = [low + 0.5, medium, high] if total else [1, 0, 0]

    # A gentle hill.
    _jump(t, -170, -12, 10)
    t.pensize(3)
    t.pencolor(SOIL)
    t.circle(-980, 20)

    # The tree itself.
    _jump(t, 0, 0, 90)

    # Low-impact share becomes a mix of greens so healthy trees look lush.
    palette = [FERN, FERN_LIGHT, SAGE, OCHRE, CLAY]
    palette_w = [weights[0] * 0.5, weights[0] * 0.3, weights[0] * 0.2, weights[1], weights[2]]
    _branch(t, 58 if depth > 2 else 40, depth, rng, palette, palette_w)

    # Fallen leaves: one per high-impact purchase (max 14).
    for i in range(min(high, 14)):
        x = rng.uniform(-140, 140)
        if abs(x) < 14:
            x += 28
        t.penup()
        t.goto(x, rng.uniform(-14, -4))
        t.dot(rng.uniform(7, 10), CLAY)
    t.penup()
    t.goto(0, 0)


# ---------------------------------------------------------------------------
# Rendering entry point for the web app
# ---------------------------------------------------------------------------
def render(kind, **kwargs):
    """Draw `kind` on a fresh SvgTurtle and return the SVG markup."""
    t = SvgTurtle()
    if kind == "sprig":
        draw_sprig(t)
        label = "Turtle drawing of a leafy sprig"
    elif kind == "steps":
        draw_steps(t)
        label = "Turtle drawing of two light footprints"
    elif kind == "deep_step":
        draw_deep_step(t)
        label = "Turtle drawing of a heavy footprint"
    elif kind == "badge":
        draw_badge(t, kwargs.get("color", FERN), kwargs.get("emblem", "star"))
        label = f"Turtle drawing of the {kwargs.get('name', 'badge')} badge"
    elif kind == "tree":
        draw_tree(t, kwargs.get("score"), kwargs.get("low", 0), kwargs.get("medium", 0),
                  kwargs.get("high", 0), kwargs.get("seed", 11))
        label = "Turtle drawing of your monthly tree"
    else:
        raise ValueError(f"Unknown drawing: {kind}")
    return t.to_svg(padding=kwargs.get("padding", 12), label=label)


REWARD_FOR_TIER = {"low": "sprig", "medium": "steps", "high": "deep_step"}
