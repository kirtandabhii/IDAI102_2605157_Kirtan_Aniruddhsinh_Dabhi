"""Altair charts for the Streamlit app, themed to match the design system."""

import altair as alt
import pandas as pd

from .theme import chart_colors

FONT_MONO = "Martian Mono, ui-monospace, monospace"
FONT_BODY = "Figtree, system-ui, sans-serif"


def _style(chart, c, height):
    return (chart.properties(height=height, background="transparent")
            .configure_view(stroke=None)
            .configure_axis(labelFont=FONT_MONO, labelFontSize=10, labelColor=c["ink-3"], titleColor=c["ink-3"],
                            gridColor=c["line"], domain=False, tickColor=c["line"])
            .configure_legend(disable=True))


def month_curve(summary, theme):
    """Running CO2 total through the month, with budget, projection and hover details."""
    c = chart_colors(theme)
    s = summary
    last_day = s["today"] if s["is_current"] else s["days_in_month"]
    rows = [{"day": 0, "cum": 0.0, "co2": 0.0, "count": 0}] + [d for d in s["daily"] if d["day"] <= last_day]
    df = pd.DataFrame(rows)
    df["over"] = df["cum"] > s["budget"]
    top = max(s["budget"] * 1.08, s["projected"] or 0, s["co2"], 10)
    x = alt.X("day:Q", scale=alt.Scale(domain=[0, s["days_in_month"]], nice=False),
              axis=alt.Axis(values=[1, 8, 15, 22, s["days_in_month"]], title=None))
    y = alt.Y("cum:Q", scale=alt.Scale(domain=[0, top], nice=True), axis=alt.Axis(title=None, tickCount=3))

    base = alt.Chart(df).encode(x=x)
    area = base.mark_area(interpolate="monotone", opacity=1, color=alt.Gradient(
        gradient="linear", stops=[alt.GradientStop(color=c["accent"], offset=0), alt.GradientStop(color=c["surface"], offset=1)],
        x1=1, x2=1, y1=0, y2=1)).encode(y=y)
    area = area.encode(opacity=alt.value(0.28))
    line = base.mark_line(interpolate="monotone", strokeWidth=2.6, color=c["accent"]).encode(y=y)
    dots = base.transform_filter(alt.datum.count > 0).mark_circle(stroke=c["accent"], strokeWidth=2, fill=c["surface"], opacity=1).encode(
        y=y, size=alt.Size("count:Q", scale=alt.Scale(range=[40, 120]), legend=None),
        color=alt.condition(alt.datum.over, alt.value(c["high"]), alt.value(c["accent"])))
    budget = alt.Chart(pd.DataFrame({"b": [s["budget"]], "label": [f'budget {s["budget"]:,.0f} kg']})).encode(y=alt.Y("b:Q"))
    budget_rule = budget.mark_rule(strokeDash=[5, 5], color=c["ink-3"], strokeWidth=1.5)
    budget_text = budget.mark_text(align="right", baseline="bottom", dy=-4, font=FONT_MONO, fontSize=10, color=c["ink-2"]).encode(
        x=alt.value("width"), text="label:N")
    layers = [area, line, budget_rule, budget_text, dots]

    if s["is_current"] and s["count"] and last_day < s["days_in_month"]:
        proj = pd.DataFrame({"day": [last_day, s["days_in_month"]], "cum": [s["co2"], s["projected"]]})
        layers.append(alt.Chart(proj).mark_line(strokeDash=[2, 5], strokeWidth=2, color=c["accent"], opacity=.8).encode(x=x, y=y))
        layers.append(alt.Chart(pd.DataFrame({"day": [last_day]})).mark_rule(color=c["line"], strokeWidth=1).encode(x="day:Q"))

    hover = alt.selection_point(fields=["day"], nearest=True, on="pointerover", clear="pointerout", empty=False)
    hits = base.mark_rule(color=c["ink-2"], strokeWidth=1).encode(
        opacity=alt.condition(hover, alt.value(0.6), alt.value(0)),
        tooltip=[alt.Tooltip("day:Q", title="Day"), alt.Tooltip("co2:Q", title="Added (kg)", format=",.1f"),
                 alt.Tooltip("count:Q", title="Purchases"), alt.Tooltip("cum:Q", title="Running total (kg)", format=",.1f")],
    ).add_params(hover)
    layers.append(hits)
    return _style(alt.layer(*layers), c, 250)


def history(rows, current_month, theme):
    """Six-month CO2 bars; the month on screen is highlighted."""
    c = chart_colors(theme)
    df = pd.DataFrame(rows)
    df["current"] = df["month"] == current_month
    bars = alt.Chart(df).mark_bar(cornerRadiusTopLeft=8, cornerRadiusTopRight=8).encode(
        x=alt.X("label:N", sort=None, axis=alt.Axis(title=None, labelAngle=0, labelFont=FONT_BODY, labelFontSize=12)),
        y=alt.Y("co2:Q", axis=None),
        color=alt.condition(alt.datum.current, alt.value(c["accent"]), alt.value(c["ink-3"])),
        opacity=alt.condition(alt.datum.current, alt.value(1), alt.value(0.45)),
        tooltip=[alt.Tooltip("month:N", title="Month"), alt.Tooltip("co2:Q", title="kg CO₂e", format=",.1f"),
                 alt.Tooltip("count:Q", title="Purchases"), alt.Tooltip("score:Q", title="Eco score")])
    labels = alt.Chart(df).mark_text(dy=-8, font=FONT_MONO, fontSize=10, color=c["ink-3"]).encode(
        x=alt.X("label:N", sort=None), y="co2:Q", text=alt.Text("co2:Q", format=",.0f"))
    return _style(alt.layer(bars, labels), c, 190)
