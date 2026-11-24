"""SvgTurtle — the Python turtle API, recorded and rendered as SVG.

Python's built-in `turtle` module draws into a Tk window, which does not exist
on a web server. SvgTurtle mirrors the same commands (forward, left, circle,
begin_fill, dot, ...) but records every stroke in drawing order. The front end
then replays those strokes one by one with a little turtle cursor, so the user
watches the drawing happen exactly as a turtle would draw it.

Because the API matches, every function in drawings.py also runs unchanged on
a real `turtle.Turtle()` — see turtle_window.py.
"""

import math


def _fmt(value):
    """Compact number formatting for SVG output."""
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


class SvgTurtle:
    def __init__(self, pencolor="#1E3B2F", fillcolor="#4E8A57", width=2.0):
        self._x = 0.0
        self._y = 0.0
        self._heading = 0.0            # degrees, 0 = east, counter-clockwise
        self._down = True
        self._pencolor = pencolor
        self._fillcolor = fillcolor
        self._width = float(width)
        self._elements = []            # strokes, dots and fills in creation order
        self._line = None              # the polyline currently being extended
        self._fill = None              # the fill polygon currently being recorded
        self._animated = 0             # number of strokes/dots so far (for fill timing)

    # -- state ---------------------------------------------------------------
    def position(self):
        return (self._x, self._y)

    pos = position

    def xcor(self):
        return self._x

    def ycor(self):
        return self._y

    def heading(self):
        return self._heading

    def isdown(self):
        return self._down

    def filling(self):
        return self._fill is not None

    # -- pen control ---------------------------------------------------------
    def penup(self):
        self._down = False
        self._line = None

    pu = up = penup

    def pendown(self):
        self._down = True

    pd = down = pendown

    def pensize(self, width=None):
        if width is None:
            return self._width
        self._width = float(width)
        self._line = None

    width = pensize

    def pencolor(self, color=None):
        if color is None:
            return self._pencolor
        self._pencolor = color
        self._line = None

    def fillcolor(self, color=None):
        if color is None:
            return self._fillcolor
        self._fillcolor = color

    def color(self, *args):
        if not args:
            return self._pencolor, self._fillcolor
        if len(args) == 1:
            self.pencolor(args[0])
            self.fillcolor(args[0])
        else:
            self.pencolor(args[0])
            self.fillcolor(args[1])

    # Compatibility no-ops: these matter on screen, not in a recording.
    def speed(self, *_):
        return 0

    def hideturtle(self):
        pass

    ht = hideturtle

    def showturtle(self):
        pass

    st = showturtle

    def shape(self, *_):
        pass

    # -- movement ------------------------------------------------------------
    def _move_to(self, x, y):
        if self._down:
            if self._line is None:
                self._line = {"kind": "stroke", "pts": [(self._x, self._y)],
                              "color": self._pencolor, "width": self._width}
                self._elements.append(self._line)
                self._animated += 1
            self._line["pts"].append((x, y))
        if self._fill is not None:
            self._fill["pts"].append((x, y))
        self._x, self._y = x, y

    def forward(self, distance):
        rad = math.radians(self._heading)
        self._move_to(self._x + distance * math.cos(rad), self._y + distance * math.sin(rad))

    fd = forward

    def backward(self, distance):
        self.forward(-distance)

    bk = back = backward

    def left(self, angle):
        self._heading = (self._heading + angle) % 360

    lt = left

    def right(self, angle):
        self.left(-angle)

    rt = right

    def setheading(self, angle):
        self._heading = angle % 360

    seth = setheading

    def goto(self, x, y=None):
        if y is None:
            x, y = x
        self._move_to(float(x), float(y))

    setpos = setposition = goto

    def setx(self, x):
        self.goto(x, self._y)

    def sety(self, y):
        self.goto(self._x, y)

    def home(self):
        self.goto(0, 0)
        self.setheading(0)

    def circle(self, radius, extent=None, steps=None):
        """Same algorithm as turtle.circle: the centre is `radius` units to the left."""
        if extent is None:
            extent = 360
        if steps is None:
            frac = abs(extent) / 360
            steps = 1 + int(min(11 + abs(radius) / 6.0, 59.0) * frac)
            steps *= 2  # a little smoother than the Tk version
        w = extent / steps
        w2 = 0.5 * w
        length = 2.0 * radius * math.sin(math.radians(w2))
        if radius < 0:
            length, w, w2 = -length, -w, -w2
        self.left(w2)
        for _ in range(steps):
            self.forward(length)
            self.left(w)
        self.left(-w2)

    def dot(self, size=None, color=None):
        if size is None:
            size = max(self._width + 4, self._width * 2)
        self._elements.append({"kind": "dot", "x": self._x, "y": self._y,
                               "size": float(size), "color": color or self._pencolor})
        self._animated += 1
        self._line = None  # keep drawing order exact

    # -- filling -------------------------------------------------------------
    def begin_fill(self):
        # The fill sits *behind* the outline that follows it, so it is placed
        # in the element list now and revealed once the outline is finished.
        self._fill = {"kind": "fill", "pts": [(self._x, self._y)],
                      "color": self._fillcolor, "reveal": None}
        self._elements.append(self._fill)

    def end_fill(self):
        if self._fill is not None:
            self._fill["reveal"] = self._animated
            self._fill = None

    def write(self, *_, **__):
        pass  # text is rendered by the app, not the turtle

    # -- output --------------------------------------------------------------
    def bounds(self):
        xs, ys = [], []
        for el in self._elements:
            if el["kind"] == "dot":
                r = el["size"] / 2
                xs += [el["x"] - r, el["x"] + r]
                ys += [el["y"] - r, el["y"] + r]
            else:
                for x, y in el["pts"]:
                    xs.append(x)
                    ys.append(y)
        if not xs:
            return (0, 0, 0, 0)
        return (min(xs), min(ys), max(xs), max(ys))

    def to_svg(self, padding=10, css_class="turtle-art", label="Turtle drawing"):
        """Render recorded moves as SVG. Turtle's y axis points up; SVG's points down."""
        min_x, min_y, max_x, max_y = self.bounds()
        width = max(max_x - min_x, 1) + 2 * padding
        height = max(max_y - min_y, 1) + 2 * padding
        view = f"{_fmt(min_x - padding)} {_fmt(-max_y - padding)} {_fmt(width)} {_fmt(height)}"

        parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}" '
                 f'class="{css_class}" role="img" aria-label="{label}">']
        seq = 0
        for el in self._elements:
            if el["kind"] == "fill":
                if len(el["pts"]) < 3:
                    continue
                d = "M" + " L".join(f"{_fmt(x)} {_fmt(-y)}" for x, y in el["pts"]) + " Z"
                reveal = el["reveal"] if el["reveal"] is not None else seq
                parts.append(f'<path class="t-fill" d="{d}" fill="{el["color"]}" data-at="{reveal}"/>')
            elif el["kind"] == "stroke":
                if len(el["pts"]) < 2:
                    seq += 1
                    continue
                d = "M" + " L".join(f"{_fmt(x)} {_fmt(-y)}" for x, y in el["pts"])
                parts.append(f'<path class="t-stroke" d="{d}" fill="none" stroke="{el["color"]}" '
                             f'stroke-width="{_fmt(el["width"])}" stroke-linecap="round" '
                             f'stroke-linejoin="round" data-seq="{seq}"/>')
                seq += 1
            else:  # dot
                parts.append(f'<circle class="t-dot" cx="{_fmt(el["x"])}" cy="{_fmt(-el["y"])}" '
                             f'r="{_fmt(el["size"] / 2)}" fill="{el["color"]}" data-seq="{seq}"/>')
                seq += 1
        parts.append("</svg>")
        return "".join(parts)
