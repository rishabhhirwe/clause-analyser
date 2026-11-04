"""Draws the rating as a half-circle gauge in PDFs, matching the gauge on the card."""
from __future__ import annotations

import math

from reportlab.graphics.shapes import Drawing, PolyLine, String
from reportlab.lib import colors

TRACK_COLOUR = "#e2e0d9"
CAPTION_COLOUR = "#6b6a65"
# The card's SVG gauge is drawn in a 116 x 78 box: centre (58, 64), radius 48, stroke 10.
BOX_WIDTH, BOX_HEIGHT = 116, 78
CENTRE_X, CENTRE_FROM_BOTTOM, RADIUS, STROKE = 58, 14, 48, 10
ARC_STEPS = 48


def _arc(scale: float, share: float) -> list[float]:
    """Points along the top half of the circle, from the left end to the given share of the way round."""
    count = max(2, int(ARC_STEPS * share) + 1)
    points: list[float] = []
    for i in range(count):
        angle = math.pi - math.pi * share * i / (count - 1)
        points += [(CENTRE_X + RADIUS * math.cos(angle)) * scale, (CENTRE_FROM_BOTTOM + RADIUS * math.sin(angle)) * scale]
    return points


def _line(points: list[float], colour: str, scale: float) -> PolyLine:
    return PolyLine(points, strokeColor=colors.HexColor(colour), strokeWidth=STROKE * scale, strokeLineCap=1, strokeLineJoin=1)


def gauge(rating: int | float | None, out_of: int, colour: str, width: float, caption: bool = True) -> Drawing:
    """A gauge filled up to the rating (2.5 fills halfway between 2 and 3), with the number inside.

    caption adds "out of 5" under the number; leave it off for small gauges in tables.
    """
    scale = width / BOX_WIDTH
    drawing = Drawing(width, BOX_HEIGHT * scale)
    drawing.add(_line(_arc(scale, 1.0), TRACK_COLOUR, scale))
    share = 0.0 if rating is None else max(0.0, min(1.0, rating / out_of))
    if share:
        drawing.add(_line(_arc(scale, share), colour, scale))
    number = "-" if rating is None else str(rating)
    drawing.add(String(CENTRE_X * scale, 16 * scale, number, fontName="Times-Bold", fontSize=30 * scale,
                       fillColor=colors.HexColor(colour), textAnchor="middle"))
    if caption:
        drawing.add(String(CENTRE_X * scale, 2 * scale, f"out of {out_of}", fontName="Times-Bold",
                           fontSize=10 * scale, fillColor=colors.HexColor(CAPTION_COLOUR), textAnchor="middle"))
    return drawing
