"""Vertical pitch display orientation.

Tracking data stays corner-origin metres: ``x`` along length, ``y`` along width.
The UI draws a vertical pitch via mplsoccer ``VerticalPitch``, which plots
``(display_x, display_y) = (y, x)`` so length runs bottom→top on screen.

``home_at_bottom`` controls which end is at the bottom of the figure:
- True  (default): home attacks upward when attacking +x in first half
- False: pitch is flipped 180° so the opposite team sits at the bottom
"""
from __future__ import annotations

import numpy as np

from sopovis.bundle.bundle import PrecomputedBundle


def to_display_xy(
    x: float | np.ndarray,
    y: float | np.ndarray,
    bundle: PrecomputedBundle,
    home_at_bottom: bool = True,
) -> tuple[float | np.ndarray, float | np.ndarray]:
    """Map tracking (x, y) → VerticalPitch plot coordinates."""
    if home_at_bottom:
        return y, x
    return bundle.meta.pitch_y - y, bundle.meta.pitch_x - x


def to_display_points(
    xy: np.ndarray,
    bundle: PrecomputedBundle,
    home_at_bottom: bool = True,
) -> np.ndarray:
    """``(..., 2)`` tracking coords → display coords (same shape)."""
    out = np.empty_like(xy, dtype=float)
    dx, dy = to_display_xy(xy[..., 0], xy[..., 1], bundle, home_at_bottom)
    out[..., 0] = dx
    out[..., 1] = dy
    return out


def to_tracking_xy(
    display_x: float,
    display_y: float,
    bundle: PrecomputedBundle,
    home_at_bottom: bool = True,
) -> tuple[float, float]:
    """Inverse of ``to_display_xy`` for hit-testing."""
    if home_at_bottom:
        return display_y, display_x
    return bundle.meta.pitch_x - display_y, bundle.meta.pitch_y - display_x


def to_display_delta(
    dx: float | np.ndarray,
    dy: float | np.ndarray,
    home_at_bottom: bool = True,
) -> tuple[float | np.ndarray, float | np.ndarray]:
    """Map a tracking-space displacement into display space."""
    if home_at_bottom:
        return dy, dx
    return -dy, -dx
