"""Small SVG coordinates for time-series charts in server-rendered pages."""

from decimal import Decimal


def line_chart(values: list[Decimal | None]) -> dict[str, list]:
    """Connect adjacent known observations; leave missing values as gaps."""
    known = [value for value in values if value is not None]
    if len(known) < 2 or len(values) < 2:
        return {"segments": [], "dots": []}
    low, high = min(known), max(known)
    span = high - low
    dots = []
    segments = []
    current = []
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
