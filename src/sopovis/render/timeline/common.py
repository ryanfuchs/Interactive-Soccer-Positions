"""Shared helpers for timeline layers."""
from __future__ import annotations

from sopovis.render.timeline.geometry import TIMELINE_BG


def _luminance(hex_color: str) -> float:
    value = hex_color.lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    r, g, b = (int(value[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def team_label_color(main: str, secondary: str, background: str = TIMELINE_BG) -> str:
    """Pick a team colour that stays readable on the timeline background."""
    bg = _luminance(background)
    for color in (main, secondary, "#333333"):
        if color and abs(_luminance(color) - bg) >= 55:
            return color
    return "#333333"
