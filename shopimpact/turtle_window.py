"""Draw any ShopImpact reward in a real Python turtle window.

    python -m shopimpact.turtle_window sprig
    python -m shopimpact.turtle_window steps
    python -m shopimpact.turtle_window deep_step
    python -m shopimpact.turtle_window badge star
    python -m shopimpact.turtle_window tree 82

The drawing functions are the same ones the web app renders as SVG — proof
that the app's artwork is genuine turtle graphics. Needs a desktop with Tk.
"""

import sys

from . import drawings


def main(argv):
    import turtle  # imported here so the web server never needs Tk

    kind = argv[0] if argv else "sprig"
    screen = turtle.Screen()
    screen.title(f"ShopImpact turtle — {kind}")
    screen.bgcolor(drawings.PAPER)
    t = turtle.Turtle()
    t.speed(0 if kind == "tree" else 6)
    if kind == "tree":
        screen.tracer(4)

    if kind == "sprig":
        drawings.draw_sprig(t)
    elif kind == "steps":
        drawings.draw_steps(t)
    elif kind == "deep_step":
        drawings.draw_deep_step(t)
    elif kind == "badge":
        drawings.draw_badge(t, drawings.GLACIER, argv[1] if len(argv) > 1 else "star")
    elif kind == "tree":
        score = int(argv[1]) if len(argv) > 1 else 75
        drawings.draw_tree(t, score, low=8, medium=4, high=2, seed=3)
    else:
        print(__doc__)
        return
    t.hideturtle()
    screen.update()
    turtle.done()


if __name__ == "__main__":
    main(sys.argv[1:])
