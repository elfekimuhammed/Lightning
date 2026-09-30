"""Chart geometry for server-rendered pages (App guideline 2.1 · 08 Data visuals).

Hand-drawn SVG and CSS, no chart library. This module only turns figures that services already
computed into positions and percentages; it never computes a financial figure. The markup lives
in templates/partials/charts.html. Rules from the guideline and the data-visualization checks:

- colours follow meaning: money in green, money out soft rose, over plan strong rose, money you
  hold azure; asset classes cash azure, deposits teal, gold gold, equity green, other grey
  (in that order around a donut, so similar hues never touch);
- bars start at zero, values sit on the marks, one axis only;
- a trend with fewer than two points says so instead of drawing;
- every chart has a table view with the same numbers.
"""
from __future__ import annotations

from decimal import Decimal

ZERO = Decimal(0)

# Asset class code (root or child) -> chart tone. Order is the donut order.
CLASS_TONES = [("CASH", "cash"), ("DEPOSIT", "deposits"), ("FUND.FIXED_INCOME", "deposits"),
               ("FUND.MONEY_MARKET", "deposits"), ("GOLD", "gold"), ("FUND.GOLD", "gold"),
               ("STOCK", "equity"), ("FUND", "equity"), ("OTHER", "other")]
TONE_ORDER = ["cash", "deposits", "gold", "equity", "other"]


def class_tone(code: str) -> str:
    """The chart colour for an asset class code: the most specific match wins."""
    best = ("", "other")
    for prefix, tone in CLASS_TONES:
        if (code == prefix or code.startswith(prefix + ".")) and len(prefix) > len(best[0]):
            best = (prefix, tone)
    return best[1]


def _nice_ceiling(value: Decimal) -> Decimal:
    """Round a maximum up to a clean axis number (1, 2, 2.5 or 5 × a power of ten)."""
    if value <= 0:
        return Decimal(1)
    magnitude = Decimal(10) ** (len(str(int(value))) - 1)
    for step in (1, 2, Decimal("2.5"), 5, 10):
        if value <= magnitude * step:
            return magnitude * step
    return magnitude * 10


def trend(labels: list[str], series: list[dict], plan: Decimal | None = None,
          min_points: int = 2) -> dict:
    """Lines over time on one axis.

    ``series``: [{"name", "tone", "values": [Decimal | None, ...]}], values aligned with ``labels``.
    Returns positions in percent of the plot box (x left→right, y top→bottom), ticks, and a
    ``too_short`` flag when no series has ``min_points`` known values.
    """
    known = [v for s in series for v in s["values"] if v is not None]
    points_per_series = [sum(1 for v in s["values"] if v is not None) for s in series]
    if not labels or max(points_per_series, default=0) < min_points:
        return {"too_short": True, "labels": labels, "series": series}
    low = min([ZERO, *known] + ([plan] if plan is not None else []))
    high = max([*known] + ([plan] if plan is not None else []) + [ZERO])
    top = _nice_ceiling(high) if high > 0 else ZERO
    bottom = -_nice_ceiling(-low) if low < 0 else ZERO
    span = (top - bottom) or Decimal(1)

    def y(value: Decimal) -> float:
        return float((top - value) / span * 100)

    def x(index: int) -> float:
        return 50.0 if len(labels) == 1 else 4 + 92 * index / (len(labels) - 1)

    drawn = []
    for s in series:
        pts = [(x(i), y(v), v, labels[i]) for i, v in enumerate(s["values"]) if v is not None]
        line = " ".join(f"{px:.2f},{py:.2f}" for px, py, _, _ in pts)
        zero_y = y(max(bottom, ZERO)) if bottom < 0 <= top else y(bottom)
        area = (f"M{pts[0][0]:.2f},{zero_y:.2f} " + " ".join(f"L{px:.2f},{py:.2f}" for px, py, _, _ in pts)
                + f" L{pts[-1][0]:.2f},{zero_y:.2f} Z") if pts else ""
        over = s.get("over")  # per month, when each month has its own plan
        dots = [{"x": px, "y": py, "value": v, "label": lab,
                 "over": bool(over[labels.index(lab)]) if over is not None
                 else plan is not None and s.get("plan_applies", True) and v > plan} for px, py, v, lab in pts]
        drawn.append({**s, "line": line, "area": area if s.get("area") else "", "dots": dots,
                      "last": dots[-1] if dots else None})
    ticks = [{"value": v, "y": y(v)} for v in sorted({top, (top + bottom) / 2, bottom, ZERO}, reverse=True)
             if bottom <= v <= top]
    return {"too_short": False, "labels": [{"text": lab, "x": x(i)} for i, lab in enumerate(labels)],
            "series": drawn, "ticks": ticks, "plan": None if plan is None else {"value": plan, "y": y(plan)},
            "zero_y": y(ZERO) if bottom < 0 else None}


def bars(rows: list[dict], limit: int = 6) -> dict:
    """Horizontal bars, largest first, from zero. rows: [{"label", "value", "href"?}]."""
    ordered = sorted((r for r in rows if r["value"]), key=lambda r: -abs(r["value"]))
    shown, rest = ordered[:limit], ordered[limit:]
    scale = max((abs(r["value"]) for r in shown), default=ZERO) or Decimal(1)
    return {"rows": [{**r, "width": float(abs(r["value"]) / scale * 100)} for r in shown],
            "more": len(rest), "more_total": sum((r["value"] for r in rest), ZERO)}


def meter(used: Decimal, total: Decimal | None) -> dict:
    """Spent of plan (or saved of target). Over plan fills the track in strong rose."""
    if not total or total <= 0:
        return {"width": 0.0, "over": used > 0, "left": None}
    return {"width": float(min(used / total, Decimal(1)) * 100), "over": used > total,
            "left": total - used, "share": float(used / total * 100)}


def donut(slices: list[dict], limit: int = 6) -> dict:
    """Parts of one whole: at most ``limit`` slices, the rest folded into "Other".

    slices: [{"label", "value", "tone"}]; ordered by tone (cash, deposits, gold, equity, other) so
    that neighbouring hues stay distinct. Returns stroke-dash segments on a circle of
    circumference 100, with a small gap between slices.
    """
    parts = sorted((s for s in slices if s["value"] and s["value"] > 0), key=lambda s: -s["value"])
    folded = None
    if len(parts) > limit:  # keep the largest, fold the smallest
        parts, rest = parts[:limit - 1], parts[limit - 1:]
        folded = {"label": "Other", "value": sum((s["value"] for s in rest), ZERO), "tone": "other"}
    parts.sort(key=lambda s: (TONE_ORDER.index(s["tone"]) if s["tone"] in TONE_ORDER else 99, -s["value"]))
    if folded:
        parts.append(folded)
    total = sum((s["value"] for s in parts), ZERO)
    if not total:
        return {"segments": [], "total": ZERO}
    gap = 0.6 if len(parts) > 1 else 0.0
    offset, segments = 25.0, []  # start at 12 o'clock
    for s in parts:
        share = float(s["value"] / total * 100)
        segments.append({**s, "share": share, "dash": max(share - gap, 0.1), "offset": offset})
        offset -= share
    return {"segments": segments, "total": total}


def share(parts: list[dict]) -> dict:
    """Two to four parts of one whole in a single line."""
    shown = [p for p in parts if p["value"] and p["value"] > 0]
    total = sum((p["value"] for p in shown), ZERO)
    return {"parts": [{**p, "share": float(p["value"] / total * 100)} for p in shown] if total else [],
            "total": total}


def sparkline(values: list[Decimal | None]) -> dict:
    """A small trend with no axes; only with two known points or more."""
    known = [v for v in values if v is not None]
    if len(known) < 2:
        return {"points": ""}
    low, high = min(known), max(known)
    span = (high - low) or Decimal(1)
    pts = [(4 + 92 * i / (len(values) - 1), 90 - float((v - low) / span) * 80)
           for i, v in enumerate(values) if v is not None]
    return {"points": " ".join(f"{x:.2f},{y:.2f}" for x, y in pts), "last": pts[-1]}


def line_chart(values: list[Decimal | None]) -> dict[str, list]:
    """Older helper kept for the investments page: connect adjacent known observations."""
    known = [value for value in values if value is not None]
    if len(known) < 2 or len(values) < 2:
        return {"segments": [], "dots": []}
    low, high = min(known), max(known)
    span = high - low
    dots, segments, current = [], [], []
    for index, value in enumerate(values):
        if value is None:
            if len(current) > 1:
                segments.append(" ".join(current))
            current = []
            continue
        x = Decimal(5) + Decimal(90 * index) / Decimal(len(values) - 1)
        y = Decimal(50) if span == 0 else Decimal(85) - Decimal(70) * (value - low) / span
        point = f"{x:.2f},{y:.2f}"
        current.append(point)
        dots.append((f"{x:.2f}", f"{y:.2f}"))
    if len(current) > 1:
        segments.append(" ".join(current))
    return {"segments": segments, "dots": dots}
