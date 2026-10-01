"""Build docs/APPLICATION_BRAND_GUIDE.html: the visual half of the App guideline.

    python docs/build_brand_guide.py

The written rules live in APPLICATION_BRAND_GUIDE.md; this page shows each of them as a live
specimen (colour, type, cards, controls, fields, lists) and draws every chart type a finance app
may need, marked In the app · Ready to use · Avoid. Values mirror lightning/ui/static/style.css.
Sample figures are illustrative. Pure standard library, no chart library, like the app.
"""
from __future__ import annotations

import html
import math
from pathlib import Path

OUT = Path(__file__).with_name("APPLICATION_BRAND_GUIDE.html")
VERSION = "2.5 · Willow"
UPDATED = "2026-10-01"

# ---- tokens (same values as style.css) ---------------------------------------------------------
T = dict(
    ink="#0D2233", ink2="#304A5C", muted="#5C7483", positive="#097852",
    nile="#0A2442", meadow="#14A874", meadow_dark="#0B8A5F", rose_soft_bar="#E68CA8", rose="#C93D72",
    azure="#0B6DD6", gold="#B8841E", teal="#0A9E96", grey="#7E96A0",
    line="#DDE9E6", line_control="#7E96A0", track="#E6EFEC", hover="#F0F7F4",
    surface="#FFFFFF", paper="#F8FCFA", paper_end="#EFF8F4",
    tint_growth="#EAF8F0", tint_held="#EAF3FD", rose_soft="#FCEEF3", row_field="#F2F8F6",
)
CLASS = [("Cash", "#0B6DD6"), ("Deposits", "#00907F"), ("Money market fund", "#6CC795"),
         ("Fixed income fund", "#2E9CC8"), ("Gold", "#9A6708"), ("Gold fund", "#D6A23A"),
         ("Stocks", "#08744A"), ("Equity fund", "#3EB072"), ("Other", "#687F8B"), ("Other fund", "#A2B4BC")]
IN, SPEND, OVER, HOLD, PLAN, NEUTRAL = T["meadow_dark"], T["rose_soft_bar"], T["rose"], T["azure"], T["meadow"], T["grey"]
MONTHS = ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def money(v: float, dec: int = 2, sign: bool = False) -> str:
    s = f"{abs(v):,.{dec}f}"
    if v < 0:
        return "−" + s
    return ("+" + s) if sign and v > 0 else s


def short(v: float) -> str:
    return f"{v:,.0f}"


# ---- SVG helpers --------------------------------------------------------------------------------
W, H = 360, 200
L, R, TOP, BOT = 48, 12, 14, 28   # plot padding


def svg(body: str, label: str, w: int = W, h: int = H) -> str:
    return (f'<svg class="spec-svg" viewBox="0 0 {w} {h}" role="img" aria-label="{esc(label)}">'
            f"{body}</svg>")


def text(x, y, s, cls="t", anchor="start", fill=None, weight=None, size=None) -> str:
    extra = (f' fill="{fill}"' if fill else "") + (f' font-weight="{weight}"' if weight else "") \
        + (f' font-size="{size}"' if size else "")
    return f'<text class="{cls}" x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}"{extra}>{esc(s)}</text>'


def nice(v: float) -> float:
    if v <= 0:
        return 1
    mag = 10 ** math.floor(math.log10(v))
    for step in (1, 2, 2.5, 5, 10):
        if v <= mag * step:
            return mag * step
    return mag * 10


class Axis:
    """One y axis from lo to hi (zero included), x as evenly spaced categories."""

    def __init__(self, n, lo, hi, w=W, h=H, left=L, band=False):
        self.n, self.w, self.h, self.left, self.band = n, w, h, left, band
        self.hi = nice(hi) if hi > 0 else 0
        self.lo = -nice(-lo) if lo < 0 else 0
        self.x0, self.x1, self.y0, self.y1 = left, w - R, TOP, h - BOT

    def y(self, v):
        return self.y1 - (v - self.lo) / ((self.hi - self.lo) or 1) * (self.y1 - self.y0)

    def x(self, i):
        if self.band:
            step = (self.x1 - self.x0) / self.n
            return self.x0 + step * (i + .5)
        return self.x0 + (self.x1 - self.x0) * (i / (self.n - 1) if self.n > 1 else .5)

    def step(self):
        return (self.x1 - self.x0) / self.n

    def grid(self, labels=None, ticks=None):
        out = []
        vals = ticks or sorted({self.lo, (self.lo + self.hi) / 2, self.hi, 0})
        for v in vals:
            yy = self.y(v)
            out.append(f'<line class="{"g0" if v == 0 else "g"}" x1="{self.x0}" x2="{self.x1}" y1="{yy:.1f}" y2="{yy:.1f}"/>')
            out.append(text(self.x0 - 6, yy + 3.5, short(v), "t", "end"))
        for i, lab in enumerate(labels or []):
            out.append(text(self.x(i), self.h - 9, lab, "t", "middle"))
        return "".join(out)


def poly(points, color, width=2, dash=None, cls="") -> str:
    d = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    extra = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<polyline class="{cls}" points="{d}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"{extra}/>'


def area(points, base_y, color, opacity=.12) -> str:
    d = f"M{points[0][0]:.1f},{base_y:.1f} " + " ".join(f"L{x:.1f},{y:.1f}" for x, y in points) \
        + f" L{points[-1][0]:.1f},{base_y:.1f} Z"
    return f'<path d="{d}" fill="{color}" opacity="{opacity}"/>'


def dot(x, y, color, r=4.5) -> str:
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{color}" stroke="#fff" stroke-width="2"/>'


def rbar(x, y, w, h, color, radius=3, end="right") -> str:
    """A bar with rounded data end only (4px guideline, 3 in viewBox units)."""
    if w <= 0 or h <= 0:
        return ""
    r = min(radius, w / 2, h / 2)
    if end == "right":
        d = f"M{x:.1f},{y:.1f} h{w - r:.1f} a{r},{r} 0 0 1 {r},{r} v{h - 2 * r:.1f} a{r},{r} 0 0 1 -{r},{r} h-{w - r:.1f} Z"
    elif end == "top":
        d = f"M{x:.1f},{y + h:.1f} v-{h - r:.1f} a{r},{r} 0 0 1 {r},-{r} h{w - 2 * r:.1f} a{r},{r} 0 0 1 {r},{r} v{h - r:.1f} Z"
    else:  # bottom (negative columns)
        d = f"M{x:.1f},{y:.1f} v{h - r:.1f} a{r},{r} 0 0 0 {r},{r} h{w - 2 * r:.1f} a{r},{r} 0 0 0 {r},-{r} v-{h - r:.1f} Z"
    return f'<path d="{d}" fill="{color}"/>'


def key(items) -> str:
    return '<div class="legend">' + "".join(
        f'<span><i style="background:{c}"></i>{esc(n)}</span>' if not n.startswith("--")
        else f'<span><i class="dash" style="border-color:{c}"></i>{esc(n[2:])}</span>' for n, c in items) + "</div>"


# ---- chart specimens ----------------------------------------------------------------------------
def c_trend():
    vals = [18200, 21450, 19800, 24300, 22100, 26900]
    plan = 23000
    a = Axis(6, 0, max(vals + [plan]))
    pts = [(a.x(i), a.y(v)) for i, v in enumerate(vals)]
    body = a.grid(MONTHS)
    body += f'<line x1="{a.x0}" x2="{a.x1}" y1="{a.y(plan):.1f}" y2="{a.y(plan):.1f}" stroke="{PLAN}" stroke-width="2" stroke-dasharray="6 5"/>'
    body += poly(pts, HOLD)
    body += "".join(dot(x, y, OVER if v > plan else HOLD) for (x, y), v in zip(pts, vals))
    body += text(pts[-1][0], pts[-1][1] - 10, money(vals[-1]), "v", "end")
    return key([("Money out", HOLD), ("--Plan 23,000.00", PLAN)]) + svg(body, "Money out per month against plan")


def c_area():
    vals = [412000, 418500, 425200, 431900, 429400, 446800]
    a = Axis(6, 0, max(vals))
    pts = [(a.x(i), a.y(v)) for i, v in enumerate(vals)]
    body = a.grid(MONTHS) + area(pts, a.y(0), HOLD) + poly(pts, HOLD)
    body += dot(*pts[-1], HOLD) + text(pts[-1][0], pts[-1][1] - 10, money(vals[-1]), "v", "end")
    return svg(body, "Net worth at each month end")


def c_stacked_area():
    series = [("Cash", CLASS[0][1], [60, 58, 64, 61, 66, 70]), ("Deposits", CLASS[1][1], [150, 150, 150, 155, 155, 155]),
              ("Gold", CLASS[4][1], [80, 84, 83, 88, 92, 95]), ("Stocks", CLASS[6][1], [95, 99, 104, 101, 96, 108])]
    tot = [sum(s[2][i] for s in series) for i in range(6)]
    a = Axis(6, 0, max(tot) * 1000)
    body = a.grid(MONTHS)
    base = [0] * 6
    for name, c, vals in series:
        top = [base[i] + vals[i] for i in range(6)]
        up = [(a.x(i), a.y(top[i] * 1000)) for i in range(6)]
        down = [(a.x(i), a.y(base[i] * 1000)) for i in reversed(range(6))]
        d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in up + down) + " Z"
        body += f'<path d="{d}" fill="{c}" opacity=".85" stroke="#fff" stroke-width="1.5"/>'
        base = top
    return key([(n, c) for n, c, _ in series]) + svg(body, "What you own by class over time")


def c_step():
    vals = [12400, 12400, 3400, 3400, 21400, 18650, 18650, 9650, 9650]
    labels = ["09-01", "", "09-05", "", "09-10", "", "09-18", "", "09-30"]
    a = Axis(9, 0, max(vals))
    pts = []
    for i, v in enumerate(vals):
        if i:
            pts.append((a.x(i), a.y(vals[i - 1])))
        pts.append((a.x(i), a.y(v)))
    body = a.grid([l for l in labels]) + poly(pts, HOLD)
    body += dot(a.x(8), a.y(vals[-1]), HOLD) + text(a.x(8), a.y(vals[-1]) - 10, money(vals[-1]), "v", "end")
    return svg(body, "Account balance through the month")


def c_forecast():
    actual = [34200, 29800, 27400]
    fc = [27400, 21900, 16300, 24100, 19800, 30100]
    labels = ["09-15", "09-30", "10-15", "10-31", "11-15", "11-30", "12-15", "12-31"]
    a = Axis(8, 0, 40000)
    body = a.grid(labels)
    lo = [(a.x(i + 2), a.y(v * (1 - .05 * k))) for k, (i, v) in enumerate(enumerate(fc))]
    hi = [(a.x(i + 2), a.y(v * (1 + .05 * k))) for k, (i, v) in enumerate(enumerate(fc))]
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in hi + lo[::-1]) + " Z"
    body += f'<path d="{d}" fill="{HOLD}" opacity=".12"/>'
    body += poly([(a.x(i), a.y(v)) for i, v in enumerate(actual)], HOLD)
    body += poly([(a.x(i + 2), a.y(v)) for i, v in enumerate(fc)], HOLD, dash="4 4")
    body += f'<line x1="{a.x(2):.1f}" x2="{a.x(2):.1f}" y1="{a.y0}" y2="{a.y1}" stroke="{T["line_control"]}" stroke-width="1"/>'
    body += text(a.x(2) + 4, a.y0 + 8, "Today", "t")
    lx, ly = a.x(4), a.y(16300)
    body += dot(lx, ly, OVER) + text(lx, ly + 16, "Lowest 16,300.00", "v", "middle")
    return key([("Cash you own", HOLD), ("--Forecast", HOLD), ("Likely range", "rgba(11,109,214,.18)")]) + svg(body, "Cash forecast with range and lowest point")


def c_burnup():
    days = 30
    plan = 23000
    spent = [0, 1200, 1900, 4300, 5100, 7800, 9900, 12400, 13100, 15600, 18900]  # every 3 days
    a = Axis(11, 0, 26000)
    body = a.grid(["1", "", "7", "", "13", "", "19", "", "25", "", "30"])
    body += poly([(a.x(0), a.y(0)), (a.x(10), a.y(plan))], PLAN, dash="6 5")
    body += poly([(a.x(i), a.y(v)) for i, v in enumerate(spent)], SPEND)
    body += dot(a.x(10), a.y(spent[-1]), SPEND) + text(a.x(10), a.y(spent[-1]) + 16, "18,900.00 by day 30", "v", "end")
    return key([("Spent so far", SPEND), ("--Even pace to plan", PLAN)]) + svg(body, "Spending pace this month against plan")


def c_columns_in_out():
    inn = [42000, 42000, 45500, 42000, 42800, 48000]
    out = [31200, 35600, 33900, 38100, 36400, 40300]
    a = Axis(6, -45000, 50000, band=True)
    body = a.grid(MONTHS, [-40000, 0, 25000, 50000])
    bw = a.step() * .42
    for i in range(6):
        x = a.x(i) - bw / 2
        body += rbar(x, a.y(inn[i]), bw, a.y(0) - a.y(inn[i]), IN, end="top")
        body += rbar(x, a.y(0), bw, a.y(-out[i]) - a.y(0), SPEND, end="bottom")
        net = inn[i] - out[i]
        body += f'<rect x="{a.x(i) - 7:.1f}" y="{a.y(net) - 1.5:.1f}" width="14" height="3" rx="1.5" fill="{T["nile"]}"/>'
    return key([("Money in", IN), ("Money out", SPEND), ("Net flow", T["nile"])]) + svg(body, "Money in and out per month, net flow marked")


def c_drawdown():
    dd = [0, -1.8, -4.6, -2.1, 0, -0.9, -6.3, -3.2, -1.1, 0, -2.4, -0.6]
    a = Axis(12, -8, 0)
    body = a.grid(["", "Q4", "", "", "Q1", "", "", "Q2", "", "", "Q3", ""], [-8, -4, 0])
    pts = [(a.x(i), a.y(v)) for i, v in enumerate(dd)]
    d = f"M{pts[0][0]:.1f},{a.y(0):.1f} " + " ".join(f"L{x:.1f},{y:.1f}" for x, y in pts) + f" L{pts[-1][0]:.1f},{a.y(0):.1f} Z"
    body += f'<path d="{d}" fill="{SPEND}" opacity=".35"/>' + poly(pts, OVER, 1.5)
    body += text(a.x(6), a.y(-6.3) + 14, "−6.3% worst", "v", "middle")
    return svg(body.replace(">0<", ">0%<").replace(">-4<", ">−4%<").replace(">-8<", ">−8%<"), "Fall from the previous high, by month")


def c_candles():
    rows = [(10.2, 10.8, 9.9, 10.6), (10.6, 11.2, 10.4, 10.5), (10.5, 10.7, 9.6, 9.8), (9.8, 10.9, 9.7, 10.8),
            (10.8, 11.6, 10.7, 11.4), (11.4, 11.5, 10.9, 11.0), (11.0, 11.9, 10.9, 11.8), (11.8, 12.4, 11.5, 12.2)]
    a = Axis(8, 0, 13, band=True)
    lo_v, hi_v = 9, 13
    def yy(v):
        return a.y1 - (v - lo_v) / (hi_v - lo_v) * (a.y1 - a.y0)
    body = ""
    for v in (9, 11, 13):
        body += f'<line class="g" x1="{a.x0}" x2="{a.x1}" y1="{yy(v):.1f}" y2="{yy(v):.1f}"/>' + text(a.x0 - 6, yy(v) + 3.5, f"{v:.2f}", "t", "end")
    for i, (o, h, l, c) in enumerate(rows):
        col = IN if c >= o else SPEND
        x = a.x(i)
        body += f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{yy(h):.1f}" y2="{yy(l):.1f}" stroke="{T["ink2"]}" stroke-width="1"/>'
        body += f'<rect x="{x - 7:.1f}" y="{yy(max(o, c)):.1f}" width="14" height="{max(abs(yy(o) - yy(c)), 1.5):.1f}" rx="2" fill="{col}"/>'
        body += text(x, a.h - 9, f"W{i + 1}", "t", "middle")
    return svg(body, "Weekly open, high, low and close of one price")


def c_calendar():
    import random
    rnd = random.Random(7)
    body = ""
    cell, gap, x0, y0 = 38, 4, 44, 26
    for j, d in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
        body += text(x0 + j * (cell + gap) + cell / 2, 16, d, "t", "middle")
    shades = ["#F7FAF9", "#FBE6EE", "#F4C3D3", "#EC9DB7", "#D9678D"]
    day = 1
    for w in range(5):
        for j in range(7):
            idx = w * 7 + j - 1  # 2026-09-01 is a Tuesday
            if idx < 0 or day > 30:
                continue
            level = rnd.choice([0, 0, 1, 1, 2, 2, 3, 4]) if day != 25 else 4
            x, y = x0 + j * (cell + gap), y0 + w * (26 + gap)
            body += f'<rect x="{x}" y="{y}" width="{cell}" height="26" rx="6" fill="{shades[level]}"><title>2026-09-{day:02d}</title></rect>'
            body += text(x + 5, y + 11, str(day), "t", fill=T["ink"] if level < 4 else "#fff", size=9)
            day += 1
    scale = "".join(f'<i style="background:{c}"></i>' for c in shades)
    return svg(body, "Spending by day in 2026-09", w=W, h=184) + f'<div class="legend ramp"><span>Less</span>{scale}<span>More</span></div>'


def c_small_multiples():
    cats = [("Groceries", [4.1, 4.4, 3.9, 4.6, 4.8, 5.2]), ("Transport", [1.2, 1.1, 1.3, 1.2, 1.0, 1.1]),
            ("Eating out", [2.3, 2.9, 2.1, 3.4, 2.8, 3.9]), ("Home", [6.0, 6.0, 6.2, 6.2, 6.2, 6.5])]
    out = '<div class="multiples">'
    hi = max(v for _, vs in cats for v in vs)
    for name, vs in cats:
        pts = [(4 + i * 18, 40 - v / hi * 34) for i, v in enumerate(vs)]
        body = f'<line class="g" x1="0" x2="100" y1="40" y2="40"/>' + poly(pts, SPEND) + dot(*pts[-1], SPEND, 3)
        out += (f'<div><b>{esc(name)}</b><small>{vs[-1]:.1f}k this month</small>'
                f'<svg class="spec-svg" viewBox="0 0 100 44" role="img" aria-label="{esc(name)} per month">{body}</svg></div>')
    return out + "</div>"


def c_sparkline():
    vals = [3.1, 3.3, 3.0, 3.6, 3.4, 3.9, 4.2]
    pts = [(4 + i * 15.3, 36 - (v - 3) / 1.2 * 30) for i, v in enumerate(vals)]
    body = poly(pts, HOLD) + dot(*pts[-1], HOLD, 3)
    return (f'<div class="spark-demo"><div><small>Holdings value</small><b>94,210.00 <em>EGP</em></b></div>'
            f'<svg class="spec-svg" viewBox="0 0 100 40" role="img" aria-label="Holdings value, last 7 months">{body}</svg></div>')


def html_bars(rows, tone=SPEND, grouped=False):
    top = max(abs(r[1]) for r in rows if len(r) > 1 and not (len(r) > 2 and r[2] == "h"))
    out = '<div class="bars">'
    for r in rows:
        if len(r) > 2 and r[2] == "h":
            out += f'<div class="bar-group"><span>{esc(r[0])}</span><b>{money(r[1])}</b></div>'
            continue
        out += (f'<div class="bar-row{" indent" if grouped else ""}"><span>{esc(r[0])}</span><span class="track">'
                f'<i style="width:{abs(r[1]) / top * 100:.1f}%;background:{tone}"></i></span><b>{money(r[1])}</b></div>')
    return out + "</div>"


def c_bars():
    return html_bars([("Home", 6500), ("Groceries", 5210), ("Eating out", 3940), ("Transport", 1120), ("Health", 860)]) \
        + '<div class="bar-more"><span>3 more</span><b>1,470.00</b></div>'


def c_grouped_bars():
    return html_bars([("Personal", 11270, "h"), ("Groceries", 5210), ("Eating out", 3940), ("Clothes", 2120),
                      ("Home", 7360, "h"), ("Rent", 6500), ("Utilities", 860)], grouped=True)


def c_clustered():
    cats = ["Home", "Groceries", "Eating out", "Transport"]
    now = [6500, 5210, 3940, 1120]
    usual = [6300, 4650, 2780, 1180]
    a = Axis(4, 0, max(now + usual), band=True)
    body = a.grid(cats)
    bw = a.step() * .3
    for i in range(4):
        body += rbar(a.x(i) - bw - 1, a.y(usual[i]), bw, a.y(0) - a.y(usual[i]), "#C9D6D2", end="top")
        body += rbar(a.x(i) + 1, a.y(now[i]), bw, a.y(0) - a.y(now[i]), SPEND, end="top")
    return key([("Usual month", "#C9D6D2"), ("This month", SPEND)]) + svg(body, "This month against your usual month")


def c_dumbbell():
    rows = [("Cash", 18, 10), ("Deposits", 35, 30), ("Gold", 21, 20), ("Stocks", 26, 40)]
    body, y = "", 18
    x0, x1 = 96, 330
    for v in (0, 25, 50):
        xx = x0 + v / 50 * (x1 - x0)
        body += f'<line class="g" x1="{xx:.1f}" x2="{xx:.1f}" y1="6" y2="{len(rows) * 36 + 4}"/>' + text(xx, len(rows) * 36 + 18, f"{v}%", "t", "middle")
    for name, cur, req in rows:
        xc, xr = x0 + cur / 50 * (x1 - x0), x0 + req / 50 * (x1 - x0)
        body += text(x0 - 10, y + 4, name, "l", "end")
        body += f'<line x1="{xc:.1f}" x2="{xr:.1f}" y1="{y}" y2="{y}" stroke="{T["line_control"]}" stroke-width="2"/>'
        body += dot(xc, y, HOLD) + f'<circle cx="{xr:.1f}" cy="{y}" r="4.5" fill="#fff" stroke="{T["nile"]}" stroke-width="2"/>'
        y += 36
    return key([("Current %", HOLD), ("Required %", T["nile"])]) + svg(body, "Current share against required share", h=len(rows) * 36 + 26)


def c_diverging():
    rows = [("Stocks", 26600), ("Deposits", -9200), ("Gold", -1800), ("Cash", -15600)]
    mx = 30000
    cx, half = 190, 108
    body = f'<line x1="{cx}" x2="{cx}" y1="4" y2="{len(rows) * 34 + 2}" stroke="{T["line_control"]}" stroke-width="1"/>'
    y = 10
    for name, v in rows:
        w = abs(v) / mx * half
        if v >= 0:
            body += rbar(cx, y, w, 16, HOLD)
            body += text(cx + w + 6, y + 12, money(v, sign=True), "v")
        else:
            body += f'<path d="M{cx:.1f},{y} h-{w - 3:.1f} a3,3 0 0 0 -3,3 v10 a3,3 0 0 0 3,3 h{w - 3:.1f} Z" fill="{SPEND}"/>'
            body += text(cx - w - 6, y + 12, money(v), "v", "end")
        body += text(cx + (-8 if v >= 0 else 8), y + 12, name, "l", "end" if v >= 0 else "start")
        y += 34
    body += text(cx - half, len(rows) * 34 + 18, "Take out", "t") + text(cx + half, len(rows) * 34 + 18, "Put in", "t", "end")
    return svg(body, "Value to adjust per class to reach the required share", h=len(rows) * 34 + 26)


def c_lollipop():
    rows = [("Rent · Nasr City", 6500), ("Carrefour", 2140), ("Dentist", 1800), ("Vodafone", 950), ("Uber", 610)]
    x0, x1, y = 130, 300, 16
    body = ""
    for name, v in rows:
        xx = x0 + v / 6500 * (x1 - x0)
        body += text(x0 - 10, y + 4, name, "l", "end")
        body += f'<line x1="{x0}" x2="{xx:.1f}" y1="{y}" y2="{y}" stroke="{SPEND}" stroke-width="2"/>' + dot(xx, y, SPEND, 5)
        body += text(xx + 10, y + 4, money(v), "v")
        y += 30
    return svg(body, "Largest payments this month", h=y)


def c_slope():
    rows = [("Stocks", 20, 31, CLASS[6][1]), ("Deposits", 38, 27, CLASS[1][1]), ("Gold", 16, 23, CLASS[4][1]), ("Cash", 26, 19, CLASS[0][1])]
    xa, xb = 110, 250
    def yy(v):
        return 180 - v / 40 * 160
    body = text(xa, 12, "2026-01", "t", "middle") + text(xb, 12, "2026-09", "t", "middle")
    for name, a_, b_, c in rows:
        body += f'<line x1="{xa}" x2="{xb}" y1="{yy(a_):.1f}" y2="{yy(b_):.1f}" stroke="{c}" stroke-width="2"/>'
        body += dot(xa, yy(a_), c, 4) + dot(xb, yy(b_), c, 4)
        body += text(xa - 10, yy(a_) + 4, f"{name} {a_}%", "l", "end") + text(xb + 10, yy(b_) + 4, f"{b_}% {name}", "l")
    return svg(body, "Share of each class at two dates", h=196)


def c_bullet():
    rows = [("Groceries", 5210, 5000), ("Eating out", 3940, 3000), ("Transport", 1120, 1500)]
    out = '<div class="bullets">'
    for name, used, plan in rows:
        mx = max(used, plan) * 1.15
        over = used > plan
        out += (f'<div class="bullet"><div class="head"><b>{esc(name)}</b>'
                + (f'<span class="badge-over">{money(used - plan)} over</span>' if over else f'<small>{money(plan - used)} left</small>')
                + f'</div><div class="btrack"><span class="band" style="width:{plan / mx * 100:.1f}%"></span>'
                f'<i style="width:{used / mx * 100:.1f}%;background:{OVER if over else IN}"></i>'
                f'<em style="left:{plan / mx * 100:.1f}%"></em></div><small>{money(used)} of {money(plan)}</small></div>')
    return out + "</div>"


def donut_svg(parts, center_value, center_label, size=168):
    tot = sum(v for _, v, _ in parts)
    r, cx = 15.915, 21
    off = 25.0
    segs = ""
    for name, v, c in parts:
        share = v / tot * 100
        segs += (f'<circle cx="{cx}" cy="{cx}" r="{r}" fill="none" stroke="{c}" stroke-width="5.2" '
                 f'stroke-dasharray="{max(share - .6, .1):.2f} {100 - max(share - .6, .1):.2f}" stroke-dashoffset="{off:.2f}"><title>{esc(name)}</title></circle>')
        off -= share
    legend = "".join(f'<li><i style="background:{c}"></i><span>{esc(n)}</span><b>{v / tot * 100:.1f}%</b><small>{money(v)}</small></li>' for n, v, c in parts)
    legend += f'<li class="total"><i></i><span>Total</span><b>100%</b><small>{money(tot)}</small></li>'
    return (f'<div class="donut"><div class="ring" style="width:{size}px;height:{size}px"><svg viewBox="0 0 42 42" role="img" aria-label="{esc(center_label)}">'
            f'<circle cx="{cx}" cy="{cx}" r="{r}" fill="none" stroke="{T["track"]}" stroke-width="5.2"/>{segs}</svg>'
            f'<div class="center"><b>{center_value}</b><small>{esc(center_label)}</small></div></div><ul>{legend}</ul></div>')


def c_donut():
    parts = [("Cash", 70200, CLASS[0][1]), ("Deposits", 155000, CLASS[1][1]), ("Money market fund", 24800, CLASS[2][1]),
             ("Gold", 95400, CLASS[4][1]), ("Stocks", 108300, CLASS[6][1]), ("Equity fund", 31600, CLASS[7][1])]
    return donut_svg(parts, "485,300.00", "What you own")


def c_share():
    parts = [("Planned and spent", 18900, IN), ("Bills still due", 2600, HOLD), ("Left in plan", 1500, T["track"])]
    tot = sum(v for _, v, _ in parts)
    bar = "".join(f'<i style="width:{v / tot * 100:.2f}%;background:{c}"></i>' for _, v, c in parts)
    labels = "".join(f'<span><i style="background:{c}"></i>{esc(n)} <b>{money(v)}</b> <small>{v / tot * 100:.1f}%</small></span>' for n, v, c in parts)
    return f'<div class="share"><div class="sbar">{bar}</div><div class="slabels">{labels}</div></div>'


def c_stack100():
    data = [[18, 38, 18, 26], [16, 36, 19, 29], [15, 34, 20, 31], [14, 33, 22, 31], [15, 31, 23, 31], [14, 32, 20, 34]]
    cols = [CLASS[0][1], CLASS[1][1], CLASS[4][1], CLASS[6][1]]
    a = Axis(6, 0, 100, band=True)
    body = ""
    for v in (0, 50, 100):
        body += f'<line class="g" x1="{a.x0}" x2="{a.x1}" y1="{a.y(v):.1f}" y2="{a.y(v):.1f}"/>' + text(a.x0 - 6, a.y(v) + 3.5, f"{v}%", "t", "end")
    bw = a.step() * .56
    for i, row in enumerate(data):
        base = 0
        for v, c in zip(row, cols):
            y1, y2 = a.y(base + v), a.y(base)
            body += f'<rect x="{a.x(i) - bw / 2:.1f}" y="{y1 + 1:.1f}" width="{bw:.1f}" height="{max(y2 - y1 - 2, 0):.1f}" fill="{c}" rx="1.5"/>'
            base += v
        body += text(a.x(i), a.h - 9, MONTHS[i], "t", "middle")
    return key(list(zip(["Cash", "Deposits", "Gold", "Stocks"], cols))) + svg(body, "Allocation by month, as shares")


def c_treemap():
    items = [("Home", 7360), ("Groceries", 5210), ("Eating out", 3940), ("Clothes", 2120), ("Transport", 1120), ("Health", 860), ("Gifts", 610)]
    shades = ["#D9678D", "#E27FA0", "#E68CA8", "#ECA3BA", "#F1B8CA", "#F5CCD9", "#F8DCE5"]
    total = sum(v for _, v in items)
    body = ""

    def lay(items, x, y, w, h, i0):
        nonlocal body
        if not items:
            return
        if len(items) == 1:
            n, v = items[0]
            body += f'<rect x="{x + 1:.1f}" y="{y + 1:.1f}" width="{w - 2:.1f}" height="{h - 2:.1f}" rx="6" fill="{shades[i0]}"/>'
            if w > len(n) * 7 + 14 and h > 36:
                fg = "#fff" if i0 < 2 else T["ink"]
                body += text(x + 8, y + 17, n, "l", fill=fg, weight=700) + text(x + 8, y + 31, money(v, 0), "t", fill=fg)
            return
        s = sum(v for _, v in items)
        acc, k = 0, 0
        for k, (_, v) in enumerate(items):
            acc += v
            if acc >= s / 2:
                break
        first, rest = items[:k + 1], items[k + 1:]
        f = sum(v for _, v in first) / s
        if w >= h:
            lay(first, x, y, w * f, h, i0)
            lay(rest, x + w * f, y, w * (1 - f), h, i0 + len(first))
        else:
            lay(first, x, y, w, h * f, i0)
            lay(rest, x, y + h * f, w, h * (1 - f), i0 + len(first))

    lay(items, 0, 0, W, 190, 0)
    return svg(body, f"Spending by category, total {money(total)}", h=190)


def c_waffle():
    rate = 23
    cells = ""
    for i in range(100):
        r, c = divmod(i, 10)
        col = IN if i < rate else T["track"]
        cells += f'<rect x="{c * 17}" y="{r * 17}" width="14" height="14" rx="3" fill="{col}"/>'
    return (f'<div class="waffle"><svg class="spec-svg" viewBox="0 0 167 167" role="img" aria-label="Savings rate 23 of 100">{cells}</svg>'
            f'<div><b class="big">23%</b><small>Savings rate · 2026-09</small><p>Of every 100.00 that came in, 23.00 stayed.</p></div></div>')


def c_waterfall():
    rows = [("Cash you own", 70200, "total"), ("Reserves", -30000, "down"), ("Bills due", -6400, "down"), ("Free cash", 33800, "end")]
    mx = 70200
    out, run = '<div class="fall">', 0
    for name, v, kind in rows:
        if kind == "total":
            left, width, run = 0, v / mx * 100, v
        elif kind == "end":
            left, width = 0, v / mx * 100
        else:
            after = run + v
            left, width, run = after / mx * 100, -v / mx * 100, after
        col = {"total": HOLD, "down": SPEND, "up": IN, "end": T["meadow_dark"]}[kind]
        out += (f'<div class="fall-row{" end" if kind == "end" else ""}"><span>{esc(name)}</span><span class="track">'
                f'<i style="margin-left:{left:.1f}%;width:{width:.1f}%;background:{col}"></i></span><b>{money(v)}</b></div>')
    return out + "</div>"


def c_breakdown():
    return ('<div class="breakdown"><div><span>Money in</span><b>48,000.00</b></div><div><span>Money out</span><b>−40,300.00</b></div>'
            '<div class="band"><span>Net flow</span><b>+7,700.00</b></div><div><span>Price change on what you hold</span><b>+3,420.00</b></div>'
            '<div class="band"><span>Change in what you own</span><b>+11,120.00</b></div></div>')


def c_sankey():
    left = [("Salary", 42000, IN), ("Side work", 6000, IN)]
    right = [("Home", 7360, SPEND), ("Personal", 11270, SPEND), ("Bills", 9800, SPEND), ("Loans", 11870, SPEND), ("Kept", 7700, HOLD)]
    tot, hgt, gap, top = 48000, 150, 6, 22
    sc = (hgt - gap * (len(right) - 1)) / tot
    body, hub_y = "", top + (hgt - tot * sc) / 2
    body += f'<rect x="166" y="{hub_y:.1f}" width="10" height="{tot * sc:.1f}" rx="2" fill="{IN}"/>' + text(171, hub_y - 6, "Money in 48.0k", "l", "middle")
    for side, items, x in (("l", left, 70), ("r", right, 262)):
        colh = sum(v * sc for _, v, _ in items) + gap * (len(items) - 1)
        y, hy = top + (hgt - colh) / 2, hub_y
        for n, v, c in items:
            h = v * sc
            body += f'<rect x="{x}" y="{y:.1f}" width="10" height="{h:.1f}" rx="2" fill="{c}"/>'
            body += text(x - 6, y + h / 2 + 4, n, "l", "end") if side == "l" else text(x + 16, y + h / 2 + 4, f"{n} {short(v)}", "l")
            x1, y1, x2, y2 = (x + 10, y, 166, hy) if side == "l" else (176, hy, x, y)
            mx = (x1 + x2) / 2
            body += (f'<path d="M{x1},{y1:.1f} C{mx},{y1:.1f} {mx},{y2:.1f} {x2},{y2:.1f} L{x2},{y2 + h:.1f} C{mx},{y2 + h:.1f} {mx},{y1 + h:.1f} {x1},{y1 + h:.1f} Z" '
                     f'fill="{c}" opacity=".24"/>')
            y += h + gap
            hy += h
    return svg(body, "Where money in went this month", w=W, h=190)


def c_meter():
    return c_bullet().replace('class="bullets"', 'class="bullets meters"').replace('<span class="band"', '<span class="band none"')


def c_ring():
    months, target = 4.2, 6
    share = months / target * 100
    return (f'<div class="ringdemo"><div class="ring" style="width:120px;height:120px"><svg viewBox="0 0 42 42" role="img" aria-label="Emergency fund 4.2 of 6 months">'
            f'<circle cx="21" cy="21" r="15.915" fill="none" stroke="{T["track"]}" stroke-width="4.5"/>'
            f'<circle cx="21" cy="21" r="15.915" fill="none" stroke="{IN}" stroke-width="4.5" stroke-linecap="round" '
            f'stroke-dasharray="{share:.1f} {100 - share:.1f}" stroke-dashoffset="25"/></svg>'
            f'<div class="center"><b>4.2</b><small>of 6 months</small></div></div>'
            f'<div><b>Emergency fund</b><small>25,200.00 to go · at 3,000.00 a month, 2027-05</small></div></div>')


def spark_svg(values, color):
    lo, hi = min(values), max(values)
    pts = [(4 + 92 * i / (len(values) - 1), 90 - (v - lo) / ((hi - lo) or 1) * 80) for i, v in enumerate(values)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"M{pts[0][0]:.1f},100 " + " ".join(f"L{x:.1f},{y:.1f}" for x, y in pts) + f" L{pts[-1][0]:.1f},100 Z"
    return (f'<span class="tvis"><svg viewBox="0 0 100 100" preserveAspectRatio="none"><path d="{area}" fill="{color}" opacity=".1"/>'
            f'<polyline points="{line}" fill="none" stroke="{color}" stroke-width="2" vector-effect="non-scaling-stroke" opacity=".75"/></svg>'
            f'<i style="left:{pts[-1][0]:.1f}%;top:{pts[-1][1]:.1f}%;background:{color}"></i></span>')


def tile(surface, label, chip, chip_tone, value, unit, sub, figure="", spark=None, meter=None):
    arrow = {"up": "↑ ", "down": "↓ "}.get(chip_tone, "")
    vis = spark_svg(*spark) if spark else ""
    bar = f'<span class="tmeter"><i style="width:{meter[0]}%;background:{meter[1]}"></i></span>' if meter else ""
    fig = f'<b class="{"pos" if figure.startswith("+") else "neg"}">{esc(figure)}</b> ' if figure else ""
    return (f'<a class="tile {surface}"><span class="thead"><span>{esc(label)}</span><em class="tchip {chip_tone}">{arrow}{esc(chip)}</em></span>{vis}'
            f'<b class="tval">{esc(value)}<small>{esc(unit)}</small></b><span class="tsub">{fig}{esc(sub)}</span>{bar}</a>')


def tiles_row():
    return ('<div class="tiles">'
            + tile("lead", "Change in net worth", "2026-09", "up", "+24,669.53", "EGP", "Net worth 166,059.11",
                   spark=([118000, 126500, 131200, 141390, 166059], HOLD))
            + tile("white", "Savings rate", "2026-09", "up", "47.1", "%", "kept of 46,833.33 money in", "+22,079.53",
                   spark=([18, 31, 26, 40, 47.1], IN))
            + tile("mint", "Investing rate", "2026-09", "up", "18.4", "%", "money added", "+8,600.00", meter=(18.4, HOLD))
            + tile("white", "Left in plan · 2026-09", "62% used", "flat", "9,120.00", "EGP", "of 24,000.00 planned", meter=(62, IN))
            + "</div>")


def c_stat():
    return tiles_row().replace('<div class="tiles">', '<div class="tiles two">', 1).split('<a class="tile mint">')[0] + "</div>"


def c_colfall():
    cols = [("Money in", 48000, "total"), ("Personal", -30100, "down"), ("Work", -10200, "down"), ("Net flow", 7700, "end")]
    top, run, out = 48000, 0, '<div class="cfall">'
    for name, v, kind in cols:
        if kind == "total":
            base, h, run = 0, v / top * 100, v
        elif kind == "end":
            base, h = 0, v / top * 100
        else:
            after = run + v
            base, h, run = after / top * 100, -v / top * 100, after
        col = {"total": IN, "down": SPEND, "end": HOLD}[kind]
        sign = "−" if v < 0 else ""
        out += (f'<div class="ccol"><i style="bottom:{base:.1f}%;height:{h:.1f}%;background:{col}"></i>'
                f'<b style="bottom:calc({base + h:.1f}% + 4px)">{sign}{money(abs(v))}</b><span>{esc(name)}</span></div>')
    return out + "</div>"


def c_histogram():
    bins = [("<100", 34), ("<250", 48), ("<500", 28), ("<1k", 17), ("<2.5k", 9), ("<5k", 4), ("5k+", 2)]
    a = Axis(7, 0, 50, band=True)
    body = a.grid([b for b, _ in bins], [0, 25, 50])
    bw = a.step() - 3
    for i, (_, v) in enumerate(bins):
        body += rbar(a.x(i) - bw / 2, a.y(v), bw, a.y(0) - a.y(v), SPEND, end="top")
    return svg(body, "Number of payments by size, last 90 days")


def c_range():
    rows = [("Groceries", 3900, 5200, 4550, 5210), ("Eating out", 2100, 3400, 2780, 3940), ("Transport", 1000, 1300, 1180, 1120), ("Home", 6000, 6500, 6300, 6500)]
    x0, x1, mx = 96, 330, 7000
    body, y = "", 18
    for v in (0, 3500, 7000):
        xx = x0 + v / mx * (x1 - x0)
        body += f'<line class="g" x1="{xx:.1f}" x2="{xx:.1f}" y1="4" y2="{len(rows) * 34 + 2}"/>' + text(xx, len(rows) * 34 + 16, short(v), "t", "middle")
    for name, lo, hi, med, now in rows:
        xa, xb, xm, xn = (x0 + v / mx * (x1 - x0) for v in (lo, hi, med, now))
        body += text(x0 - 10, y + 4, name, "l", "end")
        body += f'<rect x="{xa:.1f}" y="{y - 6}" width="{xb - xa:.1f}" height="12" rx="6" fill="{T["track"]}"/>'
        body += f'<line x1="{xm:.1f}" x2="{xm:.1f}" y1="{y - 7}" y2="{y + 7}" stroke="{T["ink2"]}" stroke-width="2"/>'
        body += dot(xn, y, OVER if now > hi else SPEND)
        y += 34
    return key([("Usual range (12 months)", T["track"]), ("Middle month", T["ink2"]), ("This month", SPEND)]) + svg(body, "This month against the usual range", h=len(rows) * 34 + 24)


def c_scatter():
    pts = [("Stocks A", 14, 22, CLASS[6][1]), ("Equity fund", 11, 16, CLASS[7][1]), ("Gold", 12, 9, CLASS[4][1]),
           ("Gold fund", 9, 11, CLASS[5][1]), ("Deposits", 21, 1, CLASS[1][1]), ("Money market", 17, 3, CLASS[2][1])]
    a = Axis(2, 0, 24)
    def x(v):
        return a.x0 + v / 25 * (a.x1 - a.x0)
    body = a.grid(None, [0, 12, 24])
    for v in (0, 12.5, 25):
        body += text(x(v), a.h - 9, f"{v:g}%", "t", "middle")
    for n, ret, vol, c in pts:
        left = n == "Deposits"
        body += dot(x(ret), a.y(vol), c, 5) + text(x(ret) + (-8 if left else 8), a.y(vol) + (-6 if left else 4), n, "l", "end" if left else "start")
    body = body.replace(">24<", ">24%<").replace(">12<", ">12%<")
    return svg(body, "Return a year (across) against how much it moves (up)") + '<p class="note">Across: return a year. Up: how much it moves.</p>'


def c_heatmap():
    cats = ["Groceries", "Eating out", "Transport", "Home"]
    vals = [[4.1, 4.4, 3.9, 4.6, 4.8, 5.2], [2.3, 2.9, 2.1, 3.4, 2.8, 3.9], [1.2, 1.1, 1.3, 1.2, 1.0, 1.1], [6.0, 6.0, 6.2, 6.2, 6.2, 6.5]]
    shades = ["#FBE6EE", "#F4C3D3", "#EC9DB7", "#D9678D"]
    body = ""
    cw, ch, x0 = 46, 30, 86
    for j, m in enumerate(MONTHS):
        body += text(x0 + j * cw + cw / 2, 12, m[2:], "t", "middle")
    for i, (cat, row) in enumerate(zip(cats, vals)):
        body += text(x0 - 8, 24 + i * ch + 16, cat, "l", "end")
        base = sum(row) / 6
        for j, v in enumerate(row):
            ratio = v / base
            lvl = 0 if ratio < .95 else 1 if ratio < 1.05 else 2 if ratio < 1.2 else 3
            body += f'<rect x="{x0 + j * cw + 2}" y="{20 + i * ch + 2}" width="{cw - 4}" height="{ch - 4}" rx="5" fill="{shades[lvl]}"/>'
            body += text(x0 + j * cw + cw / 2, 20 + i * ch + 19, f"{v:.1f}k", "t", "middle", fill=T["ink"] if lvl < 3 else "#fff")
    return svg(body, "Spending per category per month", h=20 + len(cats) * ch + 6)


def c_amortization():
    years = ["2026", "2027", "2028", "2029", "2030"]
    principal = [9100, 21400, 23600, 26100, 16800]
    interest = [4900, 9800, 7600, 5100, 1900]
    a = Axis(5, 0, 35000, band=True)
    body = a.grid(years)
    bw = a.step() * .5
    for i in range(5):
        yp = a.y(principal[i])
        body += f'<rect x="{a.x(i) - bw / 2:.1f}" y="{yp:.1f}" width="{bw:.1f}" height="{a.y(0) - yp:.1f}" fill="{HOLD}"/>'
        yt = a.y(principal[i] + interest[i])
        body += rbar(a.x(i) - bw / 2, yt, bw, yp - yt - 1.5, "#9CC3EE", end="top")
    return key([("Principal", HOLD), ("Interest", "#9CC3EE")]) + svg(body, "Loan payments per year, principal and interest")


def c_loan_balance():
    vals = [97000, 88000, 66600, 43000, 16900, 0]
    labels = ["2026", "2027", "2028", "2029", "2030", "2031"]
    a = Axis(6, 0, 100000)
    pts = [(a.x(i), a.y(v)) for i, v in enumerate(vals)]
    body = a.grid(labels) + area(pts, a.y(0), HOLD, .08) + poly(pts, HOLD)
    body += dot(*pts[-1], IN) + text(a.x(3.15), a.y(9000), "Paid off 2031-02 \u2198", "v")
    return svg(body, "Loan still to pay, by year")


def c_timeline():
    items = [(2, "Internet", 450), (5, "Rent", 6500), (9, "Car loan", 3200), (14, "School", 4800), (21, "Gym", 600), (27, "Salary", 42000)]
    x0, x1 = 16, 344
    body = f'<line x1="{x0}" x2="{x1}" y1="70" y2="70" stroke="{T["line_control"]}" stroke-width="1.5"/>'
    for d in (0, 10, 20, 30):
        xx = x0 + d / 30 * (x1 - x0)
        body += f'<line x1="{xx:.1f}" x2="{xx:.1f}" y1="66" y2="74" stroke="{T["line_control"]}"/>' + text(xx, 92, f"+{d}d" if d else "Today", "t", "middle")
    for k, (d, n, v) in enumerate(items):
        xx = x0 + d / 30 * (x1 - x0)
        up = k % 2 == 0
        col = IN if n == "Salary" else SPEND
        body += f'<line x1="{xx:.1f}" x2="{xx:.1f}" y1="{70 - (22 if up else -2)}" y2="70" stroke="{col}" stroke-width="1.5"/>' if up else ""
        body += dot(xx, 70, col, 5)
        ty = 30 if up else 116
        body += text(xx, ty, n, "l", "middle") + text(xx, ty + 13, ("+" if n == "Salary" else "−") + money(v), "t", "middle")
    return svg(body, "Bills and income in the next 30 days", h=136)


def c_table():
    rows = [("2026-07", "38,100.00", "42,000.00"), ("2026-08", "36,400.00", "42,800.00"), ("2026-09", "40,300.00", "48,000.00")]
    body = "".join(f"<tr><td>{a}</td><td class='num'>{b}</td><td class='num'>{c}</td></tr>" for a, b, c in rows)
    return (f'<details class="numbers" open><summary>Show the numbers</summary><table><thead><tr><th>Month</th>'
            f'<th class="num">Money out</th><th class="num">Money in</th></tr></thead><tbody>{body}</tbody></table></details>')


def c_pie_avoid():
    return ('<p class="note">A pie hides small differences and has no centre for the total. '
            'Use the donut, six slices at most.</p>')


# name, status, job, draw, use, rules, where
CHARTS = [
    ("Over time", [
        ("Trend line", "app", c_trend, "A value at comparable dates: money out, a category, a price.",
         "One series in azure, a plan as the dashed green line, a dot over plan turns strong rose. Label the last value only. Under two months it says “Not enough history yet”.",
         "Expense analysis · When did it change; Budget"),
        ("Area trend", "app", c_area, "One total that builds up: net worth, what you own.",
         "One series, a 12% fill of its line colour down to zero, the end value on the line. Never stack two areas as if they were one total.",
         "Overview · Net worth › Over time"),
        ("Stacked area", "ready", c_stacked_area, "How a total is made of parts over time: what you own by class.",
         "Asset class colours in donut order, a 1.5px white seam between layers, four layers at most, a legend above. The top edge is the total.",
         "Investments · allocation history"),
        ("Step line", "ready", c_step, "A balance that jumps on each transaction: an account through the month.",
         "Flat until a transaction, then a vertical step. Azure. Mark the last balance only.",
         "Account page · balance"),
        ("Forecast with range", "ready", c_forecast, "What comes next: the cash forecast, a goal date.",
         "Solid for what happened, dashed for the forecast, a light azure band for the likely range, a thin “Today” line. Mark the lowest point in strong rose with its value.",
         "Cash planning · Plan (today a list)"),
        ("Pace (burn-up)", "ready", c_burnup, "Is spending on pace this month?",
         "Cumulative spending in soft rose against a dashed green line from zero to the plan. No second axis.",
         "Budget · this month"),
        ("Columns: in and out", "ready", c_columns_in_out, "Money in above zero, money out below it, per month.",
         "Green up, soft rose down, from one zero line; net flow as a short Nile mark on the same axis. Never a second axis for net.",
         "Overview · Cash flow by month (stashed, see 16)"),
        ("Drawdown", "ready", c_drawdown, "How far a portfolio fell from its high.",
         "Area below zero in soft rose with a strong-rose edge; label the worst point. Needs month-end values for a year or more.",
         "Investments · risk"),
        ("Candlestick", "avoid", c_candles, "Open, high, low and close of a traded price.",
         "Reference only. Lightning keeps one price per month-end, so a candle would invent data. Use a trend line.",
         "Not used"),
        ("Calendar heatmap", "ready", c_calendar, "Which days the money went out.",
         "One hue (rose) from light to dark, five steps, a Less → More key, the day number in each cell. Weeks start on Monday.",
         "Expense analysis · by day"),
        ("Small multiples", "app", c_small_multiples, "The same trend for several categories, side by side.",
         "Same scale in every panel, no axes, the name and this month's value above each.",
         "Expense analysis · usual month (sparklines per row)"),
        ("Sparkline", "app", c_sparkline, "A trend inside a card, next to its number.",
         "No axes or labels, 2px line, a dot on the last point, two points or more.",
         "Overview · stat cards; Expense analysis rows"),
    ]),
    ("Compare and rank", [
        ("Horizontal bars", "app", c_bars, "Ranking categories, payees or accounts.",
         "Largest first, from zero, value at the end, six bars then “N more” with its total. Soft rose for spending, green for money in, azure for money held. Each bar opens its transactions.",
         "Expense analysis · Where did it go, Who you paid, Paid from"),
        ("Grouped bars (L1 · L2)", "app", c_grouped_bars, "Categories under their parent.",
         "The parent as a bold header row with its total, its children indented under it, one shared scale, groups largest first.",
         "Expense analysis · by category"),
        ("Clustered columns", "ready", c_clustered, "Two values per category: this month against usual.",
         "Two series at most, the reference in neutral grey-green, the current in its meaning colour, from zero.",
         "Expense analysis · usual month"),
        ("Dumbbell", "ready", c_dumbbell, "Where you are against where you want to be: current % against required %.",
         "Filled azure dot for now, hollow Nile dot for the target, a grey line between them. Rows in a fixed class order.",
         "Investments · Target allocation"),
        ("Diverging bars", "ready", c_diverging, "Differences both ways from zero: value to adjust per class.",
         "Azure to the right (put in), soft rose to the left (take out), a centre line, the value at the end with its sign. Never green for “good” here: both directions are neutral.",
         "Investments · Target allocation"),
        ("Lollipop", "ready", c_lollipop, "A ranked list where the exact value matters more than the bar: largest payments.",
         "Thin 2px stem, 5px head, value to the right.",
         "Expense analysis · Largest payments (today a list)"),
        ("Slope chart", "ready", c_slope, "How shares moved between two dates.",
         "Two columns only, labels at both ends, class colours.",
         "Investments · this year"),
        ("Bullet (actual against plan)", "ready", c_bullet, "Spent against a plan with the plan marked.",
         "A light band up to the plan, the actual bar in green (strong rose when over), a Nile tick at the plan. Over first in the list.",
         "Budget · categories"),
    ]),
    ("Parts of a whole", [
        ("Donut", "app", c_donut, "Allocation: what you own by class.",
         "Six slices at most (the rest folds into Other), class colours in family order, a 0.6 gap between slices, the total in the middle, a legend with % and value and a Total row.",
         "Overview · What it is made of; Investments"),
        ("Share bar", "app", c_share, "Two to four parts of one whole in one line.",
         "A 2px surface gap between parts, labels under it with value and %. More than four parts is a bar chart.",
         "Budget · plan used; Overview"),
        ("100% stacked columns", "ready", c_stack100, "Shares over time, when the total doesn't matter.",
         "Four parts at most, class colours, a 2px seam, 0% to 100% axis.",
         "Investments · allocation by month"),
        ("Treemap", "ready", c_treemap, "Many parts of one whole at once: all categories, all holdings.",
         "One hue from dark (largest) to light, the name and value in each tile big enough to hold them, a 2px gap.",
         "Expense analysis · all categories"),
        ("Waffle", "ready", c_waffle, "A single share people should feel: savings rate.",
         "100 squares, the share in its meaning colour, the rest in track grey, the % beside it.",
         "Overview · Savings rate"),
        ("Pie", "avoid", c_pie_avoid, "—", "Use the donut.", "Not used"),
    ]),
    ("How a number is built", [
        ("Waterfall", "app", c_waterfall, "From a start value to a result: cash you own to free cash.",
         "The start in azure, what comes off in soft rose, what adds in green, the result in Meadow dark and bold. Each step sits where the running total was. Zero is never “up”.",
         "Overview · Free cash › How it is built"),
        ("Column waterfall", "app", c_colfall, "The same path when it reads left to right: money in, what each kind of spending took, net flow.",
         "Money in green from zero, each step soft rose floating where the running total was, net flow azure from zero (strong rose when short). A dashed link joins each column to the next; values sit on the columns; one zero line, no axis.",
         "Overview · Cash flow › From money in to net flow"),
        ("Breakdown list", "app", c_breakdown, "The waterfall as rows, when the labels are long.",
         "Each result on a soft band, signs on every step, no bars.",
         "Overview · Cash flow; Investments"),
        ("Sankey", "app", c_sankey, "Where money in went: income by category, through money in, out to spending categories and what you kept.",
         "Three columns: sources in green, one Money in hub, uses in soft rose and Kept in azure; “From what you had” in strong rose when money out is larger. Flows at 22% of their colour, never from a source straight to a use (the ledger does not say which income paid which bill). Three sources and five uses at most, the rest folded into Other; labels pushed apart so none overlap; a table under it.",
         "Overview · Cash flow › Where money in went"),
    ]),
    ("Progress and single values", [
        ("Meter", "app", c_meter, "Spent of plan, saved of a target.",
         "“925.00 over” badge or “380.00 left” on the right, the track under it, “used of plan” under that. Green within plan, strong rose over. Over first.",
         "Budget; Cash planning · reserves; Overview · stat cards"),
        ("Progress ring", "ready", c_ring, "One goal's progress with its number in the middle.",
         "One ring per card, green on track grey, the value and unit in the middle, what's left and when beside it.",
         "Cash planning · Emergency fund"),
        ("Stat card", "app", c_stat, "A number that needs no chart, with a quiet sparkline or meter.", "See Cards › Stat cards.", "Overview · four stat cards; Expense analysis · summary"),
    ]),
    ("Spread and relationships", [
        ("Histogram", "ready", c_histogram, "How your payments are spread by size.",
         "Touching columns (1.5px gap), bins that read as money ranges, one hue.",
         "Expense analysis · payment sizes"),
        ("Usual range", "ready", c_range, "Is this month normal for each category?",
         "The 12-month range as a pill, the middle month as a tick, this month as a dot (strong rose above the range).",
         "Expense analysis · usual month"),
        ("Scatter", "ready", c_scatter, "Two measures per holding: return against how much it moves.",
         "Labelled dots in class colours, both axes from zero, no trend line unless it means something. Needs a year of month-end prices.",
         "Investments · risk and return"),
        ("Heatmap table", "ready", c_heatmap, "Category by month, to spot the unusual months.",
         "Cells shaded against each row's own average (four steps of rose), the value in every cell.",
         "Expense analysis"),
    ]),
    ("Loans and schedules", [
        ("Principal and interest", "ready", c_amortization, "What each year of a loan costs.",
         "Stacked columns: principal in azure, interest in light azure on top, from zero.",
         "Cash planning · Loans"),
        ("Loan balance", "ready", c_loan_balance, "How much is left and when it ends.",
         "Azure line down to zero, a green dot and label at the payoff date.",
         "Cash planning · Loans"),
        ("Timeline", "ready", c_timeline, "Bills and income in the next 30 days.",
         "One date axis from Today, dots with name and amount, income green, bills soft rose, labels alternating above and below.",
         "Cash planning · Next 30 days (today a list)"),
    ]),
    ("Numbers behind every chart", [
        ("Show the numbers", "app", c_table, "Every chart's data as a table.",
         "Closed by default under the chart, one quiet summary line, numbers right-aligned in tabular figures.",
         "Every trend"),
    ]),
]

AVOID = [
    ("Two y-axes", "Two scales on one chart invite false comparisons. Use two charts or index both to 100."),
    ("3D, shadows or gradients inside marks", "They distort size and add nothing."),
    ("Gauges and speedometers", "A lot of ink for one number. Use a meter or a stat card."),
    ("Radar charts", "Area depends on axis order. Use bars."),
    ("Pies, and donuts over six slices", "Fold the rest into Other, or use bars."),
    ("Sunburst and funnel", "Hard to read and nothing in personal finance needs them. Use grouped bars."),
    ("Rainbow palettes and cycled colours", "Colour follows meaning or the asset class, never the position."),
    ("A number on every point", "Label the last value and the ones that matter; the table has the rest."),
    ("Charts for empty or one-month data", "Say what's missing instead."),
]


# ---- page sections ------------------------------------------------------------------------------
def swatch(name, value, use, shown=None):
    return (f'<div class="sw"><span class="chip" style="background:{value}"></span><div><b>{esc(name)}</b>'
            f'<code>{esc(shown or value)}</code><small>{esc(use)}</small></div></div>')


def sec(id_, num, title, intro, body):
    return (f'<section class="gsec" id="{id_}"><div class="gsec-head"><span class="num">{num}</span><div><h2>{esc(title)}</h2>'
            f'{f"<p>{intro}</p>" if intro else ""}</div></div>{body}</section>')


STATUS = {"app": ("In the app", "st-app"), "ready": ("Ready to use", "st-ready"), "avoid": ("Avoid", "st-avoid")}


def chart_card(name, status, draw, use, rules, where):
    label, cls = STATUS[status]
    return (f'<article class="spec {"is-avoid" if status == "avoid" else ""}"><header><h4>{esc(name)}</h4><span class="status {cls}">{label}</span></header>'
            f'<div class="spec-body">{draw()}</div><dl><dt>Use for</dt><dd>{esc(use)}</dd><dt>Rules</dt><dd>{esc(rules)}</dd>'
            f'<dt>{"Where" if status != "avoid" else "Instead"}</dt><dd>{esc(where)}</dd></dl></article>')


ICON = {
    "up": '<svg viewBox="0 0 24 24"><path d="M22 7 13.5 15.5l-5-5L2 17"/><path d="M16 7h6v6"/></svg>',
    "down": '<svg viewBox="0 0 24 24"><path d="m22 17-8.5-8.5-5 5L2 7"/><path d="M16 17h6v-6"/></svg>',
    "wallet": '<svg viewBox="0 0 24 24"><path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"/><path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/></svg>',
    "pie": '<svg viewBox="0 0 24 24"><path d="M21 12A9 9 0 0 0 12 3v9z"/><path d="M21.2 15.9A10 10 0 1 1 8 2.8"/></svg>',
    "alert": '<svg viewBox="0 0 24 24"><path d="m21.7 18-8-14a2 2 0 0 0-3.4 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3"/><path d="M12 9v4M12 17h.01"/></svg>',
    "good": '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg>',
    "info": '<svg viewBox="0 0 24 24"><path d="M9 18h6M10 22h4"/><path d="M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.3 1 2.3h6c0-1 .4-1.8 1-2.3A7 7 0 0 0 12 2Z"/></svg>',
    "attention": '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/></svg>',
}


def note(tone, label, figure, textv, link="See details", icon=None):
    return (f'<article class="keynote tone-{tone}"><div class="khead"><span class="kicon">{ICON[icon or tone]}</span>{esc(label)}</div>'
            f'<b class="kfig">{esc(figure)}</b><p>{esc(textv)}</p>{f"<a>{esc(link)}</a>" if link else ""}</article>')


def build() -> str:
    s = []
    # 1 principles
    s.append(sec("rules", "01", "Seven rules behind every screen", "", """
<ol class="rules">
<li><b>Lead on the left.</b> The most important card of a section sits on the left, on the soft lead gradient.</li>
<li><b>Support on the right.</b> A white card beside it explains or extends the lead with a list, bars or a breakdown.</li>
<li><b>Position, then activity.</b> What you have on a date comes before what changed in a period. The period control sits only above what it changes.</li>
<li><b>One name per number.</b> A figure has one name and one home page (the Glossary). Other pages show it once and link there.</li>
<li><b>Three control sizes.</b> 48px for page controls, 36px inside cards and for chips, 30px for fields inside a register row. Nothing else.</li>
<li><b>Colour means something.</b> Green in and growing, soft rose out, azure held, strong rose needs you. Asset classes keep their own colours.</li>
<li><b>Honest numbers.</b> Estimates say “estimate”. Nothing is annualised from under a year or compared with an empty period.</li>
</ol>"""))
    # 2 colour
    text_sw = "".join(swatch(*x) for x in [("Ink", T["ink"], "Headings, amounts, primary text"), ("Ink 2", T["ink2"], "Secondary text, and the only one on tints"),
                                            ("Muted", T["muted"], "Labels, hints, codes; white and paper only"), ("Positive", T["positive"], "Small money-in and gain amounts in lists")])
    act_sw = "".join(swatch(*x) for x in [("Nile", T["nile"], "Primary button, selected chip, info tip"), ("Meadow dark", T["meadow_dark"], "Money-in marks, within plan, focus ring"),
                                           ("Meadow", T["meadow"], "Plan line (dashed)"), ("Soft rose", T["rose_soft_bar"], "Money-out marks; never text"),
                                           ("Strong rose", T["rose"], "Over plan, negative balance, errors"), ("Azure", T["azure"], "Money you hold, links, trend lines")])
    surf_sw = "".join(swatch(*x) for x in [("Canvas", "linear-gradient(160deg,#E3F6EC,#E6F4F1,#E1EEFB)", "Page background, 160°", "#E3F6EC → #E1EEFB"),
                                            ("Paper (white card)", f"linear-gradient(180deg,{T['paper']},{T['paper_end']})", "Support cards, top to bottom", "#F8FCFA → #EFF8F4"),
                                            ("Surface", T["surface"], "Entry cards, fields, chips, popups"),
                                            ("Lead", "linear-gradient(135deg,#E0F5E9,#DCF1F0 52%,#D7ECF7)", "Lead cards, lead stat card, 135°", "#E0F5E9 → #DCF1F0 → #D7ECF7"),
                                            ("Wide", "linear-gradient(100deg,#E0F5E9 0%,#E3F4EF 26%,#F7FCF9 52%,#FFF 72%)", "Full-width cards, 100°, white by 72%", "#E0F5E9 → #FFFFFF"),
                                            ("Row field", T["row_field"], "Fields in a register add row"),
                                            ("Tint growth", T["tint_growth"], "Growth badges, active nav"), ("Tint held", T["tint_held"], "Row being edited, info icons"),
                                            ("Rose soft", T["rose_soft"], "Overage badges, error alerts"), ("Line", T["line"], "Hairlines between rows"),
                                            ("Line control", T["line_control"], "Field, button and chip borders"), ("Track", T["track"], "Empty part of meters and rings")])
    s.append(sec("colour", "02", "Colour", "Most of the screen is canvas and paper. Nile is the one strong control colour. The vivid Meadow gradient is for the logo and the Investment planner button only.",
                 f'<h3>Text</h3><div class="sws">{text_sw}</div><h3>Action and meaning</h3><div class="sws">{act_sw}</div>'
                 f'<h3>Surfaces</h3><div class="sws">{surf_sw}</div>'
                 f'<h3>Vivid Meadow</h3><div class="vivid"><span></span><p><code>#0C9B63 → #0A9E96 → #0B6DD6</code> Logo bolt and the Investment planner button. Never a card.</p></div>'
                 '<table class="plain"><thead><tr><th>Text</th><th>Use on</th><th>Never on</th><th>Contrast</th></tr></thead><tbody>'
                 '<tr><td>Ink</td><td>Every card, tint, chip and the canvas</td><td>Nile fills</td><td>13:1 or more</td></tr>'
                 '<tr><td>Ink 2</td><td>All of the above, including lead and key-note cards</td><td>Nile fills</td><td>7.6:1 or more</td></tr>'
                 '<tr><td>Positive</td><td>Small amounts on white, tints, result bands</td><td>The big lead number</td><td>4.5:1 or more</td></tr>'
                 '<tr><td>Muted</td><td>White and paper cards</td><td>Lead, tints, canvas</td><td>4.0–4.4:1 there</td></tr>'
                 '<tr><td>Azure, strong rose</td><td>White cards; links on lead cards</td><td>Body text on tints</td><td>3.9–4.4:1</td></tr>'
                 '<tr><td>White</td><td>Nile and the vivid gradient</td><td>Anything light</td><td>12:1 on Nile</td></tr></tbody></table>'))
    # 3 type
    rows = [("Lead amount", "Bricolage 800 · 40", "26,900.00", "num-lead"), ("Card figure", "Bricolage 800 · 30", "12,085.00", "num-card"),
            ("Tile figure", "Bricolage 800 · 24", "40,300.00", "num-tile"), ("Page title", "Bricolage 700 · 28", "Expense analysis", "page"),
            ("Section title", "Bricolage 700 · 20", "Your position", "section"), ("Card title", "Bricolage 700 · 17", "Where did it go?", "card"),
            ("Note title", "Manrope 700 · 15", "Groceries up 12%", "note"), ("Body", "Manrope 500 · 14", "Money you hold across every account.", "body"),
            ("Secondary", "Manrope 500 · 13", "By category, largest first", "second"), ("Label", "Manrope 700 · 13", "Amount", "label"),
            ("Meta", "Manrope 600 · 12", "As of 2026-09-30 · CIB-1284", "meta")]
    tbody = "".join(f'<tr><td>{a}</td><td><code>{b}</code></td><td><span class="ty-{c}">{esc(d)}</span></td></tr>' for a, b, d, c in rows)
    s.append(sec("type", "03", "Type", "Two fonts. Bricolage Grotesque carries numbers and titles, Manrope everything you read and press. Every amount uses tabular figures. Nothing under 12px; use the <code>--fs-*</code> and <code>--num-*</code> variables, never a new size.",
                 f'<table class="plain type"><thead><tr><th>Style</th><th>Font · px</th><th>Sample</th></tr></thead><tbody>{tbody}</tbody></table>'
                 '<div class="dos"><div><h4>Numbers</h4><p><b>12,085.00</b> two decimals, thousands separators · <b>−5,000.00</b> true minus, no space · <b>+2,400.00</b> only for money in and gains · <b>26,900.00 <small>EGP</small></b> the currency once, small, beside a card’s main number · <b>60 shares</b>, <b>12.500 g</b> · numbers and dates never wrap.</p></div>'
                 '<div><h4>Dates and casing</h4><p><b>2026-09-30</b>, months <b>2026-09</b>, ranges “2026-09-01 to 2026-09-30”. Never “30 Sep 2026” or “31/1”. Sentence case everywhere: “Cash and bank”, not “CASH &amp; BANK”.</p></div></div>'))
    # 4 cards
    cards = f"""
<div class="cardgrid">
  <div class="card lead"><div class="chead"><div><h4>Free cash</h4><p>Cash you own, less what is set aside</p></div><a class="quiet">Plan</a></div>
    <div class="lead-num">33,800.00 <small>EGP</small></div>
    <div class="trow"><span>Cash you own</span><b>70,200.00</b></div><div class="trow"><span>Reserves</span><b>−30,000.00</b></div><div class="trow"><span>Bills due</span><b>−6,400.00</b></div>
    <div class="spec-cap">Lead card · soft lead gradient, 135° · one per section, on the left</div></div>
  <div class="card white"><div class="chead"><div><h4>Where did it go?</h4><p>By category, largest first</p></div></div>
    {c_bars()}
    <div class="spec-cap">White (support) card · paper wash, white 1px edge, soft shadow</div></div>
</div>
<div class="card wide"><div class="split"><section><h4>What it is made of</h4><div class="card-num">485,300.00 <small>EGP</small></div><p class="sub">Cash, deposits, gold and holdings you own</p></section>
  <section><h4>If you sold today (estimate)</h4><div class="card-num">466,900.00 <small>EGP</small></div><p class="sub">After sale factors, 95% when unset</p></section></div>
  <div class="spec-cap">Wide card · lead green on the left fading to white by 72% · full width · may split in two with a divider</div></div>
<div class="cardgrid">
  <div class="card entry"><h4>New transaction</h4><label>Amount</label><div class="f amount">−1,250.00</div><label>Counterparty</label><div class="f">Carrefour</div>
    <div class="btns"><span class="btn primary">Save</span><span class="btn">Cancel</span></div><div class="spec-cap">Entry card · white with a 1px line border · the only bordered card · one primary button</div></div>
  <div class="card white"><h4>Needs you</h4><div class="alert rose"><b>Personal over plan</b><span>925.00 over · 2,300.00 of 1,375.00</span></div><div class="alert held"><b>2 prices are older than a month</b><span>Update them before you read the result.</span></div>
    <div class="spec-cap">Alerts live inside the card they concern; never page-wide banners</div></div>
</div>
<h3>Stat cards: one number, up to four in a row</h3>
{tiles_row()}
<ul class="bul"><li><b>Order:</b> label (15px Bricolage, ink) top left; a period chip top right (24px pill, an arrow when the number went up or down: green tint up, rose tint down, strong rose filled for <i>Over plan</i>, quiet grey otherwise); <b>one big figure</b> (30px, ink; strong rose when it is a shortfall) at the bottom; one 13px line under it with its supporting figure in green or rose.</li>
<li><b>One quiet visual</b> in the band between the label and the figure, right side: a sparkline (2px line at 75%, a 10% fill, a dot on the last point) for a figure with history, or an 8px meter for a share of a whole. Never both, never axes.</li>
<li><b>Surfaces alternate</b> so a row never reads as one block: lead green (the period’s headline), white, mint, white. Every card has a 1px line in its own shade and the card shadow; the whole card is the link.</li>
<li>164px tall; four in a row on wide screens, two from 1,100px, one on phones. The Overview uses exactly these four: Change in net worth (or Change in what you own when you owe nothing), Savings rate, Investing rate and Left in plan for the period’s month.</li></ul>
<h3>Key notes: the number first</h3>
<div class="notes">{note("info", "Safe to spend until 2026-10-27", "12,400.00", "Free cash less what is due before your next income.", "See the plan", "wallet")}{note("info", "Home · share of money out", "38%", "15,300.00 of 40,300.00.", "See Home", "pie")}{note("attention", "Categories over plan", "2", "Personal and Eating out.", "See categories", "alert")}</div>
<p class="note">The number is the highlight. Up to three under the page title, each in this order: a small tone icon with a short label (15px, ink 2), <b>one big figure</b> (30px Bricolage; green for good, strong rose for needs you, ink for info), one 13px line of context, and at most one 32px pill button in the tone colour. The card is a full tint of its tone with a 1px tone border. A note with no figure (\u201cNothing needs you today\u201d) shows its sentence as the label.</p>
<h3>Special buttons</h3>
<div class="btnrow"><span class="btn planner">↗ Investment planner</span><span class="info-tip" title="XIRR: yearly return that accounts for when you added money.">?</span><span class="page-back">‹ Back</span></div>
"""
    s.append(sec("cards", "04", "Cards", "Every card has a 20px radius and 24px padding (16/18 for stat cards). A card never sits inside a card. Cards align to the top; side-by-side support cards stretch to equal height, a lead never does.", cards))
    # 5 sections
    s.append(sec("sections", "05", "Sections and pages", "A section groups the cards that share one date: a line on the canvas, one pair of cards under it, 48px of canvas before the next.", """
<div class="pagemock"><div class="pm-top"><div><b>Overview</b><small>Your money on 2026-09-30</small></div><span class="btn primary">Add transaction</span></div>
<div class="pm-notes"><i></i><i></i><i></i></div>
<div class="pm-line"><b>Your position</b><small>As of 2026-09-30</small></div>
<div class="pm-pair"><i class="l"></i><i class="w"></i></div>
<div class="pm-line"><b>Cash flow</b><small>Month · 2026-09</small></div>
<div class="pm-wide"></div></div>
<ul class="bul"><li>Title left in sentence case; its date right (“As of” for position; the range under the title for activity).</li>
<li>One hairline 12px under the text and 16px above the cards; lead + support in 6 + 6 columns with 16px between, or one wide card.</li>
<li>A page has two to four sections, answers one question, and never repeats a number from another section.</li>
<li>Full pages opened from somewhere get one Back button in the header; popups get a full-page button beside close.</li>
<li>On phones the line wraps, the pair stacks lead first, tabs scroll on one line.</li></ul>"""))
    # 6 controls
    s.append(sec("controls", "06", "Controls", "Pills for pressing, 16px corners for typing. Selected always looks the same: a Nile fill.", """
<div class="ctl"><span class="btn primary">Add transaction</span><span class="btn">Review</span><span class="btn quiet">See all</span><span class="btn danger">Deactivate</span></div>
<div class="ctl"><span class="btn small primary">Save</span><span class="btn small">Today</span><span class="chipx on">Personal</span><span class="chipx">Home</span><span class="chipx">+ Add</span></div>
<div class="ctl"><div class="seg"><span class="on">Buy</span><span>Sell</span><span>Dividend</span><span>Already own</span></div></div>
<div class="ctl"><div class="seg"><span>All time</span><span>YTD</span><span class="on">Monthly</span><span>Custom</span></div><span class="btn small">‹</span><span class="f month">2026-09</span><span class="btn small">›</span></div>
<div class="monthpop"><div class="yr"><span>‹</span><b>2026</b><span>›</span></div><div class="mgrid">""" + "".join(
        f'<span class="{"on" if m == "Sep" else "off" if m in ("Oct", "Nov", "Dec") else ""}">{m}</span>' for m in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]) + """</div></div>
<div class="toggle"><div class="thead"><span>Personal</span><b>11,270.00</b><i>›</i></div><div class="titem"><span>Groceries</span><b>5,210.00</b></div><div class="titem"><span>Eating out</span><b>3,940.00</b></div><div class="titem"><span>2 more</span><b>2,120.00</b></div></div>
<ul class="bul"><li><b>Primary</b> (Nile) once per page; <b>Secondary</b> for the second action and every “Review”; <b>Quiet</b> for card-header actions and “Show more”; <b>Danger</b> only for deleting or deactivating.</li>
<li>Labels start with a verb, one to three words, no arrows. A page header holds Primary + Secondary + ⋯ at most.</li>
<li><b>Chips</b> (36px) filter or fill in values; they are not actions. <b>Segments</b> offer two to four choices of one thing.</li>
<li>The <b>period control</b> is one component (All time · YTD · Monthly · Custom). Every month box opens the <b>month picker</b>: a year row, twelve months, future months disabled.</li>
<li><b>Toggle rows</b> are 48px, name and total left, chevron right; items indented and adding up to the row. They start closed, except the first group on the page that owns the number.</li></ul>"""))
    # 7 fields
    s.append(sec("fields", "07", "Fields", "Three kinds: form fields on white, the one big Amount field, and soft fields inside register rows. Choosing from your own data is always type-and-pick, never a dropdown. Browser history suggestions are off everywhere.", f"""
<div class="fgrid">
<div class="card entry"><h4>Form fields · 48px</h4>
  <label>Counterparty</label><div class="f">Carrefour</div><small class="help">Type to pick, or create a new one</small>
  <label>Date <span class="m">yyyy-mm-dd</span></label><div class="frow"><div class="f">2026-09-30</div><span class="btn small">Today</span><span class="btn small">Yesterday</span></div>
  <label>Notes</label><div class="f focus">Weekly shop|</div><small class="help">Focus: the green ring</small>
  <label>Units</label><div class="f error">12,5</div><small class="err">Use a dot for decimals, like 12.5</small>
</div>
<div class="card entry"><h4>Amount · 72px, first in the drawer</h4><div class="f amount big">−1,250.00 <small>EGP</small></div><small class="help">Accepts −, commas and Arabic-Indic digits (١٢٥٠)</small>
  <h4 style="margin-top:20px">Pick field</h4><div class="f">Gro|</div><div class="menu"><span class="grp">Used before</span><span class="on">Personal › Groceries</span><span>Personal › Gifts</span><span class="grp">Create</span><span>+ New category “Gro”</span></div>
</div></div>
<h3>Soft fields in a register row</h3>
<div class="ledger">
  <div class="lh"><span></span><span>Date</span><span>Counterparty</span><span>Category</span><span>Notes</span><span class="r">Amount</span><span></span></div>
  <div class="lr add"><span class="m">New</span><span class="sf">2026-09-30</span><span class="sf ph">Counterparty</span><span class="sf ph">Category</span><span class="sf ph">Notes</span><span class="sf r ph">0.00</span><span class="btn tiny primary">Add</span></div>
  <div class="lr"><span></span><span>2026-09-29</span><span>Carrefour</span><span>Groceries</span><span class="m">Weekly shop</span><span class="r">−1,250.00</span><span></span></div>
  <div class="lr edit"><span></span><span class="sf w">2026-09-28</span><span class="sf w focus">Uber|</span><span class="sf w">Transport</span><span class="sf w"></span><span class="sf w r">−185.00</span><span class="btn tiny primary">Save</span>
    <div class="cmenu"><span>Save</span><span>Details and history</span><span>Cancel edit</span><hr><span class="d">Delete</span></div></div>
  <div class="lr"><span></span><span>2026-09-27</span><span>Salary</span><span>Income</span><span></span><span class="r pos">+42,000.00</span><span></span></div>
</div>
<ul class="bul"><li><b>Add row:</b> fields 30px tall (a line entry’s height, so nothing jumps), fill <code>#F2F8F6</code>, no border until hover, 8px corners, 13px text. The field you are in turns a deeper shade (<code>#E8F3EE</code>) with a green edge, never white.</li>
<li><b>Row being edited:</b> the row takes the held tint <code>#EAF3FD</code>; its fields are a lighter shade of it (<code>#F3F8FE</code>, border <code>#D9E6F6</code>), and the field you are in a deeper one (<code>#E3EEFB</code>) with the green edge. Only Save shows in the row. <b>Right-click</b> opens Save, Details and history, Cancel edit and Delete; Enter saves and Esc cancels.</li>
<li>Row fields never carry labels; the column header names them once. Inline number fields (Required % on Target allocation) are 34px, right-aligned, and save on Enter or blur without reloading the page.</li>
<li>Errors say what to type instead. Arabic text gets <code>dir="auto"</code>. Month boxes open the month picker; months are never typed.</li></ul>"""))
    # 8 lists
    s.append(sec("lists", "08", "Lists, tables and status", "Two-line rows replace wide tables; a table has five columns at most.", """
<div class="card white"><div class="dayhead">2026-09-29</div>
<div class="row2"><span class="av out">↗</span><div><b>Carrefour</b><small>Groceries · CIB current</small></div><div class="r"><b>−1,250.00</b><small>Balance 18,650.00</small></div></div>
<div class="row2"><span class="av in">↙</span><div><b>Salary</b><small>Income · CIB current</small></div><div class="r"><b class="pos">+42,000.00</b><small>Balance 19,900.00</small></div></div>
<div class="row2"><span class="av trf">⇄</span><div><b>To THNDR</b><small>Transfer</small></div><div class="r"><b>6,350.00</b><small>Balance 13,550.00</small></div></div>
<div class="statusrow"><span class="st"><i class="g"></i>Reconciled</span><span class="st"><i class="a"></i>Needs a price</span><span class="st"><i class="r"></i>Over plan</span><span class="badge-over">925.00 over</span><span class="badge-grow">+4.2%</span></div>
<div class="empty"><b>No transactions in this period</b><span>Try a longer period, or add one.</span><span class="btn small">Add transaction</span></div></div>
<ul class="bul"><li>Who or what on the left with details under it; the amount and one figure under it on the right. Registers group rows under day headers.</li>
<li>Money in is green with +; money out is ink with −; transfers carry no sign. Clicking a row edits it in place or opens the drawer.</li>
<li>Status is a word with a dot, or one sentence in an alert. No empty tables with headers; an empty state offers the next useful action.</li></ul>"""))
    # 9 charts
    chart_html = ('<div class="chartrules"><div><h4>Colour roles</h4>' + key([("Money in", IN), ("Money out", SPEND), ("Over plan", OVER), ("Money you hold", HOLD), ("--Plan", PLAN), ("Reference", "#C9D6D2")]) +
                  '<p>Asset classes use their own colours (section 15). Sequential data uses one hue light to dark; diverging data two hues with a neutral centre.</p></div>'
                  '<div><h4>Marks</h4><p>2px lines, 10px dots with a 2px white ring, 12px bars with a rounded data end, 2px seams between stacked parts, recessive hairline grid, one axis, from zero.</p></div>'
                  '<div><h4>Labels</h4><p>On the marks, not in a legend, when they fit; the last value only on trends. Months read <code>2026-09</code>. Tooltips on every dot and bar, and a “Show the numbers” table under every trend.</p></div>'
                  '<div><h4>Honesty</h4><p>Under two points says “Not enough history yet”. Missing data stays missing. Negative values never produce negative sizes or vanish.</p></div></div>')
    counts = {"app": 0, "ready": 0, "avoid": 0}
    for _, items in CHARTS:
        for it in items:
            counts[it[1]] += 1
    chart_html += (f'<p class="legend-status"><span class="status st-app">In the app</span> {counts["app"]} built in <code>lightning/ui/charts.py</code> '
                   f'<span class="status st-ready">Ready to use</span> {counts["ready"]} specified here, build when a page needs it '
                   f'<span class="status st-avoid">Avoid</span> reference only</p>')
    for group, items in CHARTS:
        chart_html += f'<h3>{esc(group)}</h3><div class="specs">' + "".join(chart_card(*it) for it in items) + "</div>"
    chart_html += '<h3>Never</h3><div class="avoid">' + "".join(f'<div><b>{esc(a)}</b><span>{esc(b)}</span></div>' for a, b in AVOID) + "</div>"
    s.append(sec("charts", "09", "Charts", "Hand-drawn SVG and CSS, no chart library. Pick the form from the job the data does (over time, rank, parts, build-up, progress, spread); sometimes the answer is a stat card, not a chart.", chart_html))
    # 10 words
    s.append(sec("words", "10", "Words", "Clear, encouraging, concrete, honest and local. Speak to “you”. The Glossary holds every figure’s one name.", """
<table class="plain"><thead><tr><th>Say</th><th>Instead of</th></tr></thead><tbody>
<tr><td>Free cash</td><td>Available cash · Estimated available value</td></tr>
<tr><td>Net gain or loss</td><td>Result · Period result</td></tr>
<tr><td>Personal over plan</td><td>Budget exceeded: Personal</td></tr>
<tr><td>No earlier spending to compare</td><td>44,420.00 more · Previously 0.00 EGP</td></tr>
<tr><td>Investments if sold (estimate)</td><td>Estimated liquid investments after liquidation factors</td></tr>
<tr><td>Held for others</td><td>Money from others · Cash held for others</td></tr>
<tr><td>6,350.00 is in THNDR. Move it before you spend it.</td><td>Includes 6,350.00 EGP in brokerage cash; transfer it…</td></tr>
<tr><td>Review 3 items</td><td>An unexplained metric</td></tr></tbody></table>
<p class="note">No explanation toggles: a figure’s name explains itself. One exception: a “?” info tip for a technical term (XIRR). Red means a shortfall or overspend, not simply a negative number.</p>"""))
    # 11 spacing
    sp = "".join(f'<div><i style="width:{v}px"></i><b>{v}</b><small>{u}</small></div>' for v, u in [(4, "tight"), (8, "label gap"), (12, "bar and note gap"), (16, "card gap"), (20, "block gap"), (24, "card padding"), (32, "page top"), (48, "between sections")])
    s.append(sec("space", "11", "Spacing, shape and layout", "A 4px base. Content up to 1,120px beside a 272px sidebar, 12 columns with 16px gutters. Phones: one column, 16px sides, no sideways scroll at 390px.",
                 f'<div class="spacing">{sp}</div><div class="radii"><div style="border-radius:8px"><b>8</b><small>row fields</small></div><div style="border-radius:12px"><b>12</b><small>rows, menus</small></div><div style="border-radius:16px"><b>16</b><small>fields, key notes</small></div><div style="border-radius:20px"><b>20</b><small>cards</small></div><div style="border-radius:999px"><b>pill</b><small>anything you press</small></div></div>'
                 '<table class="plain"><thead><tr><th>Height</th><th>Where</th></tr></thead><tbody><tr><td>72px</td><td>The Amount field</td></tr><tr><td>48px</td><td>Page buttons, form fields, segments, toggle rows, the period control</td></tr><tr><td>36px</td><td>Buttons in cards, chips, card actions</td></tr><tr><td>30px</td><td>Fields and buttons inside a register row; the horizon picker in a holdings row</td></tr></tbody></table>'))
    # 12 access
    s.append(sec("access", "12", "Accessibility", "", """<ul class="bul"><li>Text contrast 4.5:1 on its ground; borders, icons and the focus ring 3:1.</li>
<li>Colour is never the only signal: amounts carry signs, states carry words, chart series carry labels or a legend.</li>
<li>Targets 44px or more (row fields sit in a 36px+ row). Esc closes popups and menus; disclosures work from the keyboard and report open or closed.</li>
<li>Every chart has an aria-label and a table view. Reduced motion turns transitions off.</li></ul>"""))
    # 13 icons
    s.append(sec("icons", "13", "Icons and logo", "", """<div class="icons"><span class="bolt"><svg viewBox="0 0 32 32" width="30" height="30"><defs><linearGradient id="bb" x1="0" y1="0" x2=".35" y2="1"><stop offset="0" stop-color="#45A9E8"/><stop offset=".55" stop-color="#1FB5A8"/><stop offset="1" stop-color="#34BF8C"/></linearGradient></defs><path d="M18.2 3.5 7.6 17.4c-.6.8 0 1.9 1 1.9h5.9l-1.6 8.3c-.2 1.1 1.2 1.7 1.9.8l10.6-13.9c.6-.8 0-1.9-1-1.9h-5.9l1.6-8.3c.2-1.1-1.2-1.7-1.9-.8Z" fill="url(#bb)"/></svg><b>Lightning</b></span></div>
<ul class="bul"><li>Lucide icons at 1.75 stroke, 20px, in the current colour; no emoji or icon fonts. Key-note icons: check (good), bulb (info), alert circle (needs you).</li>
<li>The bolt sits beside the wordmark and is never recoloured by hand.</li></ul>"""))
    # 14 checklist
    s.append(sec("check", "14", "Before a screen ships, it has none of these", "", """<ul class="bul cross"><li>All-caps labels, including in the sidebar.</li><li>A vivid gradient card, or two leads in one section.</li>
<li>More than five table columns, or an empty table with headers.</li><li>Strong rose or green text for everyday amounts, or grey spending bars.</li>
<li>The lead on the right, or stretched to its neighbour’s height; white panels inside a lead card.</li><li>Text links with arrows (“Review →”); dropdowns for your own data.</li>
<li>White, bordered fields in a register row; a fourth control height.</li><li>Dates like “30 Sep 2026”; “– 5,000.00” or “-455.00”.</li>
<li>A period control above figures it doesn’t change; the same number under two names.</li><li>A chart from the Never list, or a chart for data under two points.</li></ul>"""))
    # 15 classes
    cls_rows = "".join(f'<div class="sw"><span class="chip" style="background:{c}"></span><div><b>{esc(n)}</b><code>{c}</code></div></div>' for n, c in CLASS)
    s.append(sec("classes", "15", "Asset class colours", "One hue family per kind of asset, a lighter shade for the fund version (<code>--class-*</code> in style.css). The order is the donut order and passes the palette validator for neighbouring slices. Some shades are under 3:1 on white, so charts always keep visible labels.", f'<div class="sws">{cls_rows}</div>'))
    # 16 visuals in use
    def vis_rows(rows):
        return "".join(f"<tr><td>{esc(a)}</td><td>{esc(b)}</td><td>{esc(c)}</td></tr>" for a, b, c in rows)
    active = [("Overview · stat cards", "Sparkline (Change in net worth, Savings rate) · Meter (Investing rate, Left in plan)", "stat_tiles"),
              ("Overview · Net worth", "Area trend, beside its breakdown list", "trend"),
              ("Overview · Free cash", "Waterfall (How it is built), beside its list", "waterfall"),
              ("Overview · What it is made of", "Donut", "donut"),
              ("Overview · Cash flow", "Column waterfall (From money in to net flow), beside its list", "column_waterfall"),
              ("Overview · Where money in went", "Sankey", "sankey"),
              ("Overview · Investments", "Donut (What you hold) · gain-or-loss bars by asset class · movers list", "donut"),
              ("Expense analysis", "Stat card · trend line with plan · grouped bars · bars (Who you paid, Paid from) · sparkline rows", "trend, bars, sparkline"),
              ("Budget; Cash planning · reserves", "Meter", "meter"),
              ("Cash planning · Plan", "Forecast trend", "trend"),
              ("Investments", "Area trend (portfolio value) · donut", "trend, donut"),
              ("Cash planning · Recurring", "Bars", "bars")]
    stashed = [("Month by month (money in and money out per month)", "Two-line trend under a toggle on the Overview", "Removed in 2.5: no chart hides behind a toggle. visuals.flow_trend is kept; bring it back as a Columns: in and out chart, always open."),
               ("Where it went (grouped spending bars on the Overview)", "Grouped bars", "Replaced by the Sankey in 2.5. visuals.spending_bars is kept; Expense analysis still uses grouped bars."),
               ("Money in and money out comparison bars", "Two meters", "Replaced by the Cash flow list and column waterfall in 2.5."),
               ("Savings ring", "Progress ring on the Cash flow card", "Replaced by the Savings rate stat card in 2.5."),
               ("Safe to spend key note on the Overview", "Key note", "Moved off the Overview in 2.5; Safe to spend stays the lead of Cash planning."),
               ("Share bar", "charts.share / share_bar macro", "Built, used by no screen."),
               ("Line chart (older helper)", "charts.line_chart", "Kept for the investments and Birdview helpers that still call it.")]
    s.append(sec("visuals", "16", "Visuals: active and stashed", "Every visual the app draws, and the ones it has built but set aside. Update this list in the same change that adds, moves or removes a chart.",
                 '<h3>Active: on a screen now</h3><table class="plain vis"><thead><tr><th>Where</th><th>Visual</th><th>Macro</th></tr></thead><tbody>' + vis_rows(active) + '</tbody></table>'
                 '<h3>Stashed: built, not on any screen</h3><table class="plain vis stashed"><thead><tr><th>Visual</th><th>Form</th><th>Why, and how to bring it back</th></tr></thead><tbody>' + vis_rows(stashed) + '</tbody></table>'
                 '<p class="note">Stashed code stays tested and keeps its spec in section 09, so it can come back without a redesign. Desktop (Windows) uses WebView2, the same Chromium engine as the browser, so every active visual renders the same there.</p>'))
    # 17 versions
    s.append(sec("versions", "17", "Versions", "", """<table class="plain"><thead><tr><th>Version</th><th>Date</th><th>What changed</th></tr></thead><tbody>
<tr><td>2.5 · Willow</td><td>2026-10-01</td><td>Overview rebuilt as wide split cards: numbers and toggle lists on the left, the visual on the right (net worth trend, free cash waterfall, the new column waterfall for cash flow). The Sankey replaces Where it went. Investments gets its own section; no chart sits behind a toggle; Month by month is stashed. Stat cards redesigned: four in a row on alternating green and white surfaces, a period chip, one big figure and a quiet sparkline or meter. New figures Change in net worth and Investing rate. New section 16, Visuals: active and stashed</td></tr>
<tr><td>2.4 · Meadowlark</td><td>2026-10-01</td><td>Key notes put the number first: label, one big figure in the tone colour, one line, one pill button</td></tr>
<tr><td>2.3 · Glade</td><td>2026-10-01</td><td>Key notes stand out: a full tone tint, a tone border and a solid icon tile with an icon chosen by meaning. Register fields are soft shades of their row, never white, with a green edge on the field you are in. Row actions move to the right-click menu</td></tr>
<tr><td>2.2 · Grove</td><td>2026-09-30</td><td>One unified guideline with a visual page. Soft register fields and the 30px row height; stat cards; key notes with tone tints and an edge; the wide gradient card; the 20px card radius; the waterfall in azure, soft rose and green; a full chart catalogue (In the app, Ready to use, Avoid)</td></tr>
<tr><td>2.1 · Bloom</td><td>2026-09-29</td><td>Soft rose for money out; the lead number always ink; strong rose only for over plan and errors</td></tr>
<tr><td>2.0 · Clearing</td><td>2026-09-29</td><td>Lead left, white support right; the vivid gradient leaves cards; toggle lists; Sections</td></tr>
<tr><td>1.1</td><td>2026-09-29</td><td>Meadow light by default; a faint wash on white cards; a soft band under results</td></tr>
<tr><td>1.0</td><td>2026-09-29</td><td>First app guideline</td></tr></tbody></table>"""))
    nav = "".join(f'<a href="#{i}">{n} {t}</a>' for i, n, t in [("rules", "01", "Rules"), ("colour", "02", "Colour"), ("type", "03", "Type"), ("cards", "04", "Cards"), ("sections", "05", "Sections"),
                                                              ("controls", "06", "Controls"), ("fields", "07", "Fields"), ("lists", "08", "Lists"), ("charts", "09", "Charts"), ("words", "10", "Words"),
                                                              ("space", "11", "Spacing"), ("access", "12", "Accessibility"), ("icons", "13", "Icons"), ("check", "14", "Checklist"), ("classes", "15", "Asset classes"), ("visuals", "16", "Visuals"), ("versions", "17", "Versions")])
    return PAGE.replace("{{VERSION}}", VERSION).replace("{{UPDATED}}", UPDATED).replace("{{NAV}}", nav).replace("{{BODY}}", "".join(s))


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lightning app guideline</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600..800&family=Manrope:wght@400..800&display=swap">
<style>
:root{--ink:#0D2233;--ink2:#304A5C;--muted:#5C7483;--pos:#097852;--nile:#0A2442;--meadow:#14A874;--md:#0B8A5F;--rose:#C93D72;--rosebar:#E68CA8;--azure:#0B6DD6;
--line:#DDE9E6;--lc:#7E96A0;--track:#E6EFEC;--hover:#F0F7F4;--paper:#F8FCFA;--paper2:#EFF8F4;--tg:#EAF8F0;--th:#EAF3FD;--rs:#FCEEF3;
--lead:linear-gradient(135deg,#E0F5E9,#DCF1F0 52%,#D7ECF7);--wide:linear-gradient(100deg,#E0F5E9 0%,#E3F4EF 26%,#F7FCF9 52%,#FFF 72%);
--shadow:0 14px 34px -24px rgba(10,36,66,.42);--display:"Bricolage Grotesque","Segoe UI",system-ui,sans-serif;--body:Manrope,"Segoe UI",system-ui,sans-serif;color-scheme:light}
*{box-sizing:border-box}body{margin:0;background:linear-gradient(160deg,#E3F6EC 0%,#E6F4F1 50%,#E1EEFB 100%) fixed;color:var(--ink);font:500 14px/1.55 var(--body);-webkit-font-smoothing:antialiased}
code{font:500 12px/1.4 ui-monospace,Consolas,monospace;background:rgba(255,255,255,.7);padding:1px 5px;border-radius:6px;color:var(--ink2)}
.wrap{display:grid;grid-template-columns:230px minmax(0,1fr);max-width:1320px;margin:0 auto}
nav.side{position:sticky;top:0;height:100vh;overflow:auto;padding:28px 16px;border-right:1px solid var(--line);background:linear-gradient(180deg,rgba(248,252,250,.96),rgba(239,248,244,.92))}
nav.side .brand{display:flex;gap:8px;align-items:center;font:800 19px/1 var(--display);margin:0 8px 6px}nav.side small{display:block;margin:0 8px 18px;color:var(--muted)}
nav.side a{display:block;padding:7px 10px;border-radius:10px;color:var(--ink2);text-decoration:none;font-weight:600;font-size:13px}nav.side a:hover{background:var(--tg);color:var(--ink)}
main{padding:32px 32px 80px;min-width:0}
header.hero h1{font:700 34px/1.1 var(--display);letter-spacing:-.03em;margin:0}header.hero p{max-width:760px;color:var(--ink2);margin:8px 0 0}
.gsec{margin-top:48px}.gsec-head{display:flex;gap:14px;align-items:flex-start;border-bottom:1px solid var(--line);padding-bottom:12px;margin-bottom:18px}
.gsec-head .num{font:800 13px/1 var(--display);color:#fff;background:var(--nile);border-radius:999px;padding:7px 10px;margin-top:2px}
.gsec h2{font:700 24px/1.2 var(--display);letter-spacing:-.02em;margin:0}.gsec-head p{margin:4px 0 0;color:var(--ink2);max-width:820px}
.gsec h3{font:700 17px/1.3 var(--display);margin:28px 0 12px}h4{font:700 15px/1.3 var(--display);margin:0 0 4px}
.note{color:var(--ink2);font-size:13px;max-width:820px}.bul{padding-left:18px;max-width:880px;color:var(--ink2)}.bul li{margin:6px 0}.bul b{color:var(--ink)}
.bul.cross{list-style:none;padding:0}.bul.cross li::before{content:"\\2715";color:var(--rose);font-weight:800;margin-right:10px}
.rules{padding-left:22px;max-width:900px}.rules li{margin:8px 0;color:var(--ink2)}.rules b{color:var(--ink)}
.sws{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px}
.sw{display:flex;gap:12px;align-items:center;background:#fff;border-radius:14px;padding:10px;box-shadow:var(--shadow)}.sw .chip{flex:none;width:52px;height:44px;border-radius:10px;border:1px solid rgba(13,34,51,.08)}
.sw b{display:block;font-size:13px}.sw small{display:block;color:var(--muted);font-size:12px;line-height:1.35}.sw code{font-size:11px;padding:0;background:none}
.vivid{display:flex;gap:14px;align-items:center}.vivid span{width:160px;height:40px;border-radius:999px;background:linear-gradient(135deg,#0C9B63,#0A9E96 52%,#0B6DD6)}
table.plain{border-collapse:collapse;width:100%;max-width:900px;margin-top:18px;background:#fff;border-radius:16px;overflow:hidden;box-shadow:var(--shadow)}
table.plain th,table.plain td{text-align:left;padding:9px 14px;border-bottom:1px solid var(--line);vertical-align:top}table.plain th{font-size:12px;color:var(--muted);font-weight:700}
table.plain tr:last-child td{border-bottom:0}
.ty-num-lead{font:800 40px/1.1 var(--display)}.ty-num-card{font:800 30px/1.1 var(--display)}.ty-num-tile{font:800 24px/1.1 var(--display)}.ty-page{font:700 28px/1.15 var(--display);letter-spacing:-.03em}
.ty-section{font:700 20px/1.3 var(--display)}.ty-card{font:700 17px/1.3 var(--display)}.ty-note{font:700 15px/1.35 var(--body)}.ty-body{font:500 14px/1.5 var(--body)}
.ty-second{font:500 13px/1.45 var(--body);color:var(--ink2)}.ty-label{font:700 13px/1.35 var(--body)}.ty-meta{font:600 12px/1.3 var(--body);color:var(--muted)}
[class^="ty-num"]{font-variant-numeric:tabular-nums}
.dos{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px;max-width:900px}.dos>div{background:#fff;border-radius:16px;padding:16px;box-shadow:var(--shadow)}.dos p{margin:0;color:var(--ink2)}.dos b{color:var(--ink);font-variant-numeric:tabular-nums}
.dos small{color:var(--muted);font-size:11px}
.card{position:relative;border-radius:20px;padding:24px;box-shadow:var(--shadow);min-width:0}
.card.lead{background:var(--lead)}.card.white{background:linear-gradient(180deg,var(--paper),var(--paper2));border:1px solid rgba(255,255,255,.94)}
.card.wide{background:var(--wide);margin:16px 0}.card.entry{background:#fff;border:1px solid var(--line);box-shadow:none}
.cardgrid{display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start;margin-top:16px}
.chead{display:flex;justify-content:space-between;gap:12px;padding-bottom:12px;border-bottom:1px solid rgba(13,34,51,.12);margin-bottom:12px}.chead p{margin:2px 0 0;color:var(--ink2);font-size:13px}
.quiet{color:var(--azure);font-weight:700;font-size:13px}
.lead-num{font:800 40px/1.1 var(--display);font-variant-numeric:tabular-nums;margin:6px 0 10px}.lead-num small,.card-num small,.stat b small{font:600 12px/1 var(--body);color:var(--muted);margin-left:4px}
.card-num{font:800 30px/1.1 var(--display);font-variant-numeric:tabular-nums;margin:6px 0}.sub{color:var(--ink2);font-size:13px;margin:0}
.trow{display:flex;justify-content:space-between;padding:10px 0;border-top:1px solid rgba(13,34,51,.12)}.trow b{font-variant-numeric:tabular-nums}
.spec-cap{margin-top:14px;padding-top:10px;border-top:1px dashed rgba(13,34,51,.18);font-size:12px;color:var(--muted)}
.split{display:grid;grid-template-columns:1fr 1fr}.split section{padding:0 24px}.split section:first-child{padding-left:0}.split section+section{border-left:1px solid var(--line)}
.card.entry label{display:block;font:700 13px/1.35 var(--body);margin:14px 0 6px}.card.entry label .m{color:var(--muted);font-weight:500;font-size:12px}
.f{height:48px;border:1px solid var(--lc);border-radius:16px;background:#fff;padding:0 16px;display:flex;align-items:center;font:500 15px/1 var(--body);font-variant-numeric:tabular-nums}
.f.amount{font:800 20px/1 var(--display)}.f.amount.big{height:72px;font-size:30px}.f.amount small{font:600 12px var(--body);color:var(--muted);margin-left:8px}
.f.focus{border-color:var(--md);box-shadow:0 0 0 2px #fff,0 0 0 5px rgba(11,138,95,.28)}.f.error{border-color:var(--rose)}.f.month{height:36px;width:110px;justify-content:center;border-radius:12px}
.frow{display:flex;gap:8px;align-items:center}.frow .f{flex:1}.help{display:block;color:var(--muted);font-size:12px;margin-top:4px}.err{display:block;color:var(--rose);font-size:12px;margin-top:4px;font-weight:600}
.menu{margin-top:6px;border-radius:12px;background:#fff;box-shadow:0 24px 48px -16px rgba(10,36,66,.35);padding:6px;display:grid}.menu span{padding:8px 10px;border-radius:8px}.menu .on{background:var(--hover)}.menu .grp{font-size:12px;color:var(--muted);font-weight:700;padding:6px 10px 2px}
.btns{display:flex;gap:8px;margin-top:18px}
.btn{display:inline-flex;align-items:center;justify-content:center;height:48px;padding:0 22px;border-radius:999px;border:1px solid var(--lc);background:#fff;font:700 15px/1 var(--body);color:var(--ink);white-space:nowrap}
.btn.primary{background:var(--nile);border-color:var(--nile);color:#fff}.btn.quiet{border-color:transparent;background:transparent;color:var(--azure)}.btn.danger{color:var(--rose);border-color:#F2C9D8}
.btn.small{height:36px;padding:0 14px;font-size:13px}.btn.tiny{height:30px;padding:0 12px;font-size:13px}.btn.planner{border:0;color:#fff;background:linear-gradient(135deg,#0C9B63,#0A9E96 52%,#0B6DD6);box-shadow:0 10px 22px -14px rgba(10,110,120,.8)}
.btnrow,.ctl{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:10px 0}
.info-tip{display:inline-grid;place-items:center;width:20px;height:20px;border-radius:50%;border:1px solid var(--lc);background:#fff;color:var(--ink2);font:700 12px/1 var(--body)}
.page-back{display:inline-flex;align-items:center;height:36px;padding:0 14px 0 10px;border-radius:999px;border:1px solid var(--lc);background:#fff;font-weight:700;font-size:13px}
.chipx{display:inline-flex;align-items:center;height:36px;padding:0 14px;border-radius:999px;border:1px solid var(--lc);background:#fff;font-weight:700;font-size:13px}.chipx.on{background:var(--nile);border-color:var(--nile);color:#fff}
.seg{display:inline-flex;background:#fff;border:1px solid var(--lc);border-radius:999px;padding:3px;gap:2px}.seg span{height:40px;display:inline-flex;align-items:center;padding:0 16px;border-radius:999px;font-weight:700;font-size:13px}.seg .on{background:var(--nile);color:#fff}
.monthpop{width:260px;background:#fff;border-radius:16px;box-shadow:0 24px 48px -16px rgba(10,36,66,.35);padding:12px;margin:12px 0}.monthpop .yr{display:flex;justify-content:space-between;align-items:center;padding:4px 8px 10px;font-weight:700}
.mgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}.mgrid span{text-align:center;padding:8px 0;border-radius:10px;font-weight:600;font-size:13px}.mgrid .on{background:var(--nile);color:#fff}.mgrid .off{color:#B7C6CC}
.toggle{max-width:420px;background:linear-gradient(180deg,var(--paper),var(--paper2));border-radius:20px;padding:8px 24px 14px;box-shadow:var(--shadow);margin:14px 0}
.thead{display:flex;align-items:center;gap:10px;height:48px;font-weight:700}.thead span{flex:1}.thead i{font-style:normal;transform:rotate(90deg);color:var(--muted)}
.titem{display:flex;justify-content:space-between;padding:6px 0 6px 16px;color:var(--ink2);font-size:13px}.titem b{color:var(--ink);font-variant-numeric:tabular-nums}
.fgrid{display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start}
.ledger{background:linear-gradient(180deg,var(--paper),var(--paper2));border-radius:20px;padding:10px 16px;box-shadow:var(--shadow);overflow:auto}
.ledger>div{display:grid;grid-template-columns:62px 104px 1.3fr 1.1fr 1.2fr 110px 70px;gap:6px;align-items:center;min-width:760px}
.lh{font:700 12px var(--body);color:var(--muted);padding:6px 4px;border-bottom:1px solid var(--line)}.lr{padding:3px 4px;border-bottom:1px solid var(--line);font-size:13px;min-height:37px}
.lr .r,.lh .r{text-align:right;font-variant-numeric:tabular-nums}.lr .m{color:var(--muted);font-size:12px}.lr .pos{color:var(--pos);font-weight:700}.lr .lk{color:var(--azure);font-size:12px;font-weight:600}
.sf{height:30px;display:flex;align-items:center;padding:0 10px;border-radius:8px;background:#F2F8F6;border:1px solid transparent;font-size:13px}.sf.r{justify-content:flex-end}.sf.ph{color:#8AA0AA}
.lr.edit{position:relative;background:var(--th);border-radius:10px}.lr.edit .sf.w{background:#F3F8FE;border-color:#D9E6F6}.lr.add .sf.focus{background:#E8F3EE}.sf.focus{border-color:var(--md)!important;background:#E3EEFB;box-shadow:0 0 0 3px rgba(11,138,95,.12)}
.cmenu{position:absolute;z-index:2;left:150px;top:32px;width:200px;display:grid;padding:6px;background:#fff;border-radius:12px;box-shadow:0 24px 48px -16px rgba(10,36,66,.35)}.cmenu span{padding:9px 12px;border-radius:8px;font-weight:600;font-size:13px}.cmenu span:first-child{background:var(--hover)}.cmenu hr{border:0;border-top:1px solid var(--line);margin:4px 6px}.cmenu .d{color:var(--rose)}.ledger{padding-bottom:150px!important}
.row2{display:grid;grid-template-columns:36px 1fr auto;gap:12px;align-items:center;padding:10px 0;border-bottom:1px solid var(--line)}.row2 small{display:block;color:var(--muted);font-size:12px}
.row2 .r{text-align:right;font-variant-numeric:tabular-nums}.row2 .pos{color:var(--pos)}.av{width:36px;height:36px;border-radius:12px;display:grid;place-items:center;font-weight:800}.av.out{background:var(--rs);color:var(--rose)}.av.in{background:var(--tg);color:var(--md)}.av.trf{background:var(--th);color:var(--azure)}
.dayhead{font:700 12px var(--body);color:var(--muted);padding-bottom:4px;border-bottom:1px solid var(--line)}
.statusrow{display:flex;gap:16px;align-items:center;flex-wrap:wrap;padding:14px 0}.st{display:inline-flex;gap:6px;align-items:center;font-weight:600;font-size:13px}.st i{width:8px;height:8px;border-radius:50%}.st .g{background:var(--md)}.st .a{background:#D6A23A}.st .r{background:var(--rose)}
.badge-over{font-size:12px;font-weight:700;background:var(--rs);border-radius:999px;padding:2px 10px;white-space:nowrap}.badge-grow{font-size:12px;font-weight:700;background:var(--tg);color:var(--pos);border-radius:999px;padding:2px 10px}
.empty{display:grid;gap:4px;justify-items:start;padding:16px;border-radius:14px;background:rgba(255,255,255,.6)}.empty span{color:var(--ink2);font-size:13px}
.alert{display:grid;padding:10px 14px;border-radius:12px;margin:8px 0}.alert span{font-size:13px;color:var(--ink2)}.alert.rose{background:var(--rs)}.alert.held{background:var(--th)}
.tiles{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:6px 0 14px}.tiles.two{grid-template-columns:repeat(2,minmax(0,1fr))}
.tile{position:relative;display:flex;flex-direction:column;min-height:164px;padding:18px 20px 16px;border-radius:20px;border:1px solid var(--line);box-shadow:var(--shadow);color:var(--ink);text-decoration:none;overflow:hidden}
.tile.lead{background:linear-gradient(135deg,#D3F0DF 0%,#DCF1F0 55%,#E4F1FA 100%);border-color:#BFE3CF}.tile.mint{background:linear-gradient(160deg,#EAF8F0,#F6FCF8);border-color:#CFEADB}.tile.white{background:#fff}
.thead{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}.thead>span{font:700 14px/1.35 var(--display)}
.tchip{flex:none;height:24px;display:inline-flex;align-items:center;padding:0 9px;border-radius:999px;font:700 12px/1 var(--body);font-style:normal;background:rgba(10,36,66,.06);color:var(--ink2)}
.tchip.up{background:var(--tg);color:var(--pos)}.lead .tchip.up,.mint .tchip.up{background:#fff}.tchip.down{background:var(--rs);color:#C93D72}.tchip.over{background:#C93D72;color:#fff}
.tvis{position:absolute;right:16px;top:52px;width:46%;height:40px}.tvis svg{width:100%;height:100%;overflow:visible}.tvis i{position:absolute;width:8px;height:8px;margin:-4px 0 0 -4px;border-radius:50%;box-shadow:0 0 0 2px #fff}
.tval{margin-top:auto;padding-top:18px;font:800 30px/1.1 var(--display);letter-spacing:-.025em;font-variant-numeric:tabular-nums}.tval small{margin-left:5px;font:600 12px/1 var(--body);color:var(--muted);letter-spacing:0}
.tsub{margin-top:4px;font:500 13px/1.4 var(--body);color:var(--ink2)}.tsub b.pos{color:var(--pos)}.tsub b.neg{color:#C93D72}
.tmeter{display:block;height:8px;margin-top:12px;border-radius:4px;background:var(--track);overflow:hidden}.mint .tmeter{background:#fff}.tmeter i{display:block;height:100%;border-radius:4px}
.cfall{position:relative;display:flex;height:170px;margin:26px 0 22px;border-bottom:1px solid var(--lc)}.ccol{position:relative;flex:1}.ccol i{position:absolute;left:20%;right:20%;border-radius:6px}
.ccol b{position:absolute;left:50%;transform:translateX(-50%);font:700 11px/1 var(--body);white-space:nowrap;font-variant-numeric:tabular-nums}.ccol span{position:absolute;top:calc(100% + 6px);left:0;right:0;text-align:center;font:500 11px/1.2 var(--body);color:var(--ink2)}
table.vis td:first-child{font-weight:700;white-space:nowrap}table.vis.stashed td{color:var(--ink2)}table.vis.stashed td:first-child{color:var(--muted)}
.statrow{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.statrow.one{grid-template-columns:minmax(0,320px)}
.stat{display:flex;flex-direction:column;justify-content:space-between;gap:4px;min-height:118px;padding:16px 18px;border-radius:20px;box-shadow:var(--shadow);text-decoration:none;color:var(--ink)}
.stat.lead{background:var(--lead)}.stat span{font:500 15px/1.35 var(--body);color:var(--ink2)}.stat b{font:800 24px/1.15 var(--display);font-variant-numeric:tabular-nums}.stat em{font:650 13px var(--body);color:var(--azure);font-style:normal}
.notes{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.keynote{display:flex;flex-direction:column;align-items:flex-start;gap:4px;padding:16px 18px;border-radius:20px;min-height:118px;border:1px solid var(--edge);box-shadow:0 10px 26px -20px var(--ic);background:linear-gradient(135deg,var(--tint) 0%,var(--tint2) 100%)}.khead{display:flex;align-items:center;gap:8px;color:var(--ink2);font:500 15px/1.35 var(--body)}.kfig{font:800 30px/1.1 var(--display);letter-spacing:-.02em;font-variant-numeric:tabular-nums;white-space:nowrap;color:var(--ink)}.keynote.tone-good .kfig{color:var(--pos)}.keynote.tone-attention .kfig{color:var(--rose)}

.keynote.tone-good{--tint:#D6F1E1;--tint2:#EDF9F2;--edge:#BDE5CD;--ic:#0B8A5F;--lk:#08744A}.keynote.tone-info{--tint:#D9E8FB;--tint2:#EEF5FE;--edge:#C2D8F4;--ic:#0B6DD6;--lk:#0A5AB0}.keynote.tone-attention{--tint:#F8DAE5;--tint2:#FDEFF4;--edge:#F0C0D1;--ic:#C93D72;--lk:#A02E5A}
.kicon{flex:none;display:grid;place-items:center;width:28px;height:28px;border-radius:9px;background:var(--ic);color:#fff}.kicon svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.keynote p{margin:0;font-size:13px;color:var(--ink2)}.keynote a,.pill{display:inline-flex;align-items:center;height:32px;margin-top:8px;padding:0 14px;border-radius:999px;background:var(--ic);color:#fff;font:700 13px/1 var(--body);font-style:normal}.pill.nile{background:var(--nile);color:#fff!important;align-self:flex-start}
.pagemock{max-width:620px;background:rgba(255,255,255,.35);border-radius:20px;padding:18px;border:1px dashed rgba(13,34,51,.2)}
.pm-top{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line);padding-bottom:10px}.pm-top b{font:700 20px var(--display)}.pm-top small{display:block;color:var(--muted)}.pm-top .btn{height:36px;font-size:13px}
.pm-notes{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:12px 0}.pm-notes i{height:34px;border-radius:12px;background:linear-gradient(135deg,#E1EEFC,#fff 70%);box-shadow:var(--shadow)}
.pm-line{display:flex;justify-content:space-between;border-bottom:1px solid var(--line);padding:14px 0 6px;margin-bottom:10px}.pm-line small{color:var(--muted)}
.pm-pair{display:grid;grid-template-columns:1fr 1fr;gap:10px}.pm-pair i{height:80px;border-radius:16px;box-shadow:var(--shadow)}.pm-pair .l{background:var(--lead)}.pm-pair .w{background:linear-gradient(180deg,var(--paper),var(--paper2))}.pm-wide{height:70px;border-radius:16px;background:var(--wide);box-shadow:var(--shadow)}
.chartrules{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.chartrules>div{background:#fff;border-radius:16px;padding:14px;box-shadow:var(--shadow)}.chartrules p{margin:6px 0 0;color:var(--ink2);font-size:13px}
.legend-status{display:flex;gap:10px;align-items:center;flex-wrap:wrap;color:var(--ink2);font-size:13px;margin-top:16px}
.specs{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:16px}
.spec{background:linear-gradient(180deg,var(--paper),var(--paper2));border:1px solid rgba(255,255,255,.94);border-radius:20px;padding:18px 20px;box-shadow:var(--shadow);min-width:0;display:flex;flex-direction:column}
.spec.is-avoid{background:repeating-linear-gradient(135deg,#FBF6F8,#FBF6F8 10px,#F7EEF2 10px,#F7EEF2 20px)}
.spec header{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:12px}.spec h4{margin:0;font-size:16px}
.status{font:700 11px/1 var(--body);border-radius:999px;padding:5px 9px;white-space:nowrap}.st-app{background:var(--tg);color:var(--pos)}.st-ready{background:var(--th);color:#0A5AB0}.st-avoid{background:var(--rs);color:#A02E5A}
.spec-body{flex:1;min-height:120px}.spec dl{display:grid;grid-template-columns:70px 1fr;gap:4px 10px;margin:14px 0 0;padding-top:12px;border-top:1px solid var(--line);font-size:12.5px}
.spec dt{color:var(--muted);font-weight:700}.spec dd{margin:0;color:var(--ink2)}
.spec-svg{display:block;width:100%;height:auto;overflow:visible}.spec-svg .t{font:500 10px var(--body);fill:var(--muted)}.spec-svg .v{font:700 10.5px var(--body);fill:var(--ink)}.spec-svg .l{font:600 11px var(--body);fill:var(--ink)}
.spec-svg .g{stroke:var(--line);stroke-width:1}.spec-svg .g0{stroke:var(--lc);stroke-width:1}
.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--ink2);margin:0 0 8px}.legend span{display:inline-flex;gap:6px;align-items:center}.legend i{width:10px;height:10px;border-radius:3px;display:inline-block}
.legend i.dash{width:16px;height:0;border-top:2px dashed;border-radius:0}.legend.ramp{gap:3px;align-items:center}.legend.ramp i{width:22px;height:10px;border-radius:3px}.legend.ramp span{margin:0 6px}
.bars{display:grid;gap:2px}.bar-row{display:grid;grid-template-columns:minmax(90px,34%) minmax(0,1fr) auto;gap:12px;align-items:center;min-height:36px;font-size:14px}.bar-row.indent span:first-child{padding-left:12px}
.track{height:12px}.track i{display:block;height:100%;min-width:4px;border-radius:0 4px 4px 0}.bar-row b,.bar-group b,.bar-more b{font-variant-numeric:tabular-nums}
.bar-group{display:flex;justify-content:space-between;padding:10px 0 4px;border-bottom:1px solid var(--line);font-weight:700}.bar-group:first-child{padding-top:0}
.bar-more{display:flex;justify-content:space-between;padding:8px 0 0;border-top:1px solid var(--line);color:var(--muted);font-size:13px;margin-top:4px}
.bullets{display:grid;gap:14px}.bullet .head{display:flex;justify-content:space-between;align-items:baseline;font-size:14px}.bullet small{color:var(--muted);font-size:12px}
.btrack{position:relative;height:12px;border-radius:6px;background:var(--track);margin:6px 0 4px;overflow:hidden}.btrack .band{position:absolute;left:0;top:0;bottom:0;background:#D5E4DF}.btrack .band.none{display:none}
.btrack i{position:absolute;left:0;top:3px;bottom:3px;border-radius:0 3px 3px 0}.meters .btrack i{top:0;bottom:0}.btrack em{position:absolute;top:0;bottom:0;width:2px;background:var(--nile)}.meters .btrack em{display:none}
.donut{display:grid;grid-template-columns:auto 1fr;gap:18px;align-items:center}.ring{position:relative}.ring svg{width:100%;height:100%;transform:none}
.ring .center{position:absolute;inset:0;display:grid;place-content:center;text-align:center}.ring .center b{font:800 13px/1.1 var(--display);font-variant-numeric:tabular-nums}.ring .center small{font-size:11px;color:var(--muted)}
.donut ul{list-style:none;margin:0;padding:0;display:grid;gap:4px;font-size:12.5px}.donut li{display:grid;grid-template-columns:10px 1fr auto auto;gap:8px;align-items:center}.donut li i{width:10px;height:10px;border-radius:3px}
.donut li small{color:var(--muted);font-variant-numeric:tabular-nums}.donut li b{font-variant-numeric:tabular-nums}.donut li.total{border-top:1px solid var(--line);padding-top:6px;font-weight:700}
.share .sbar{display:flex;gap:2px;height:12px;border-radius:6px;overflow:hidden;background:var(--track)}.share .sbar i{display:block;height:100%}.slabels{display:grid;gap:6px;margin-top:12px;font-size:13px}
.slabels span{display:flex;gap:8px;align-items:center}.slabels i{width:10px;height:10px;border-radius:3px}.slabels small{color:var(--muted)}
.fall{display:grid;gap:8px}.fall-row{display:grid;grid-template-columns:110px minmax(0,1fr) auto;gap:10px;align-items:center;font-size:13px}.fall-row span:first-child{color:var(--ink2)}
.fall-row .track{height:10px;border-radius:5px;background:var(--track);overflow:hidden}.fall-row .track i{border-radius:5px}.fall-row b{font-variant-numeric:tabular-nums}.fall-row.end span:first-child,.fall-row.end b{font-weight:800;color:var(--ink)}
.breakdown{display:grid;font-size:13px}.breakdown div{display:flex;justify-content:space-between;padding:8px 10px}.breakdown .band{background:linear-gradient(90deg,var(--tg),var(--th));border-radius:10px;font-weight:700}.breakdown b{font-variant-numeric:tabular-nums}
.multiples{display:grid;grid-template-columns:1fr 1fr;gap:12px}.multiples div{background:#fff;border-radius:12px;padding:10px}.multiples b{display:block;font-size:13px}.multiples small{color:var(--muted);font-size:11px}
.spark-demo{display:grid;grid-template-columns:1fr 120px;gap:12px;align-items:center;background:#fff;border-radius:14px;padding:14px}.spark-demo small{color:var(--muted);display:block}.spark-demo b{font:800 22px var(--display);font-variant-numeric:tabular-nums}.spark-demo em{font:600 11px var(--body);color:var(--muted);font-style:normal}
.waffle{display:grid;grid-template-columns:140px 1fr;gap:18px;align-items:center}.waffle .big{font:800 36px/1 var(--display)}.waffle small{display:block;color:var(--muted)}.waffle p{margin:6px 0 0;color:var(--ink2);font-size:13px}
.ringdemo{display:flex;gap:18px;align-items:center}.ringdemo small{display:block;color:var(--muted);font-size:12px}
.numbers summary{cursor:pointer;color:var(--muted);font-weight:600;font-size:13px}.numbers table{width:100%;border-collapse:collapse;margin-top:6px;font-size:13px}.numbers th,.numbers td{padding:6px 4px;border-bottom:1px solid var(--line);text-align:left}
.numbers .num{text-align:right;font-variant-numeric:tabular-nums}.numbers th{color:var(--muted);font-size:12px}
.avoid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px}.avoid div{background:#fff;border-radius:14px;padding:12px 14px;box-shadow:var(--shadow);border-left:4px solid var(--rose)}.avoid b{display:block}.avoid span{font-size:13px;color:var(--ink2)}
.spacing{display:grid;gap:6px;max-width:520px}.spacing div{display:grid;grid-template-columns:60px 34px 1fr;gap:10px;align-items:center;font-size:13px}.spacing i{display:block;height:12px;background:var(--md);border-radius:3px}.spacing small{color:var(--muted)}
.radii{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0}.radii div{width:110px;height:76px;background:#fff;box-shadow:var(--shadow);display:grid;place-content:center;text-align:center;border:1px solid var(--line)}.radii small{color:var(--muted);font-size:11px}
.icons .bolt{display:inline-flex;gap:8px;align-items:center;font:800 22px var(--display);background:#fff;border-radius:16px;padding:12px 18px;box-shadow:var(--shadow)}
@media (max-width:980px){.wrap{grid-template-columns:1fr}nav.side{position:static;height:auto;display:flex;flex-wrap:wrap;gap:4px;padding:16px}nav.side .brand,nav.side small{width:100%}
main{padding:20px 16px 60px}.tiles,.tiles.two,.cardgrid,.fgrid,.dos,.split,.statrow,.notes,.chartrules{grid-template-columns:1fr}.split section{padding:0!important;border:0!important}.split section+section{border-top:1px solid var(--line)!important;margin-top:14px;padding-top:14px!important}
.specs{grid-template-columns:1fr}table.plain{display:block;overflow-x:auto}.ty-num-lead{font-size:32px}.donut{grid-template-columns:1fr;justify-items:center}}
</style></head><body><div class="wrap">
<nav class="side" aria-label="Guideline sections"><div class="brand"><svg width="22" height="22" viewBox="0 0 32 32"><defs><linearGradient id="nb" x1="0" y1="0" x2=".35" y2="1"><stop offset="0" stop-color="#45A9E8"/><stop offset=".55" stop-color="#1FB5A8"/><stop offset="1" stop-color="#34BF8C"/></linearGradient></defs><path d="M18.2 3.5 7.6 17.4c-.6.8 0 1.9 1 1.9h5.9l-1.6 8.3c-.2 1.1 1.2 1.7 1.9.8l10.6-13.9c.6-.8 0-1.9-1-1.9h-5.9l1.6-8.3c.2-1.1-1.2-1.7-1.9-.8Z" fill="url(#nb)"/></svg>Lightning</div><small>App guideline {{VERSION}}</small>{{NAV}}</nav>
<main><header class="hero"><h1>App guideline</h1><p><b>{{VERSION}}</b> · updated {{UPDATED}}. How every screen looks, reads and adds up. The written rules are in <code>APPLICATION_BRAND_GUIDE.md</code>; this page shows each one. Built by <code>docs/build_brand_guide.py</code> from the same values as <code>style.css</code>. Sample figures are illustrative. Light theme only; dark is not wired in yet.</p></header>
{{BODY}}</main></div></body></html>
"""

if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")
