"""Vertical pitch display orientation.

Tracking data is goal-aligned metres: ``x`` is the signed lateral offset from
the axis through the goal centers, ``y`` the longitudinal distance from the
reference goal line. The UI draws a vertical pitch via mplsoccer
``VerticalPitch``, whose data space is non-negative — ``[0, width]``
horizontally and ``[0, length]`` vertically with the goals at the bottom and
top. Display therefore only shifts the lateral axis by half the pitch width:
``(display_x, display_y) = (x + width/2, y)``.

``home_at_bottom`` controls which end is at the bottom of the figure:
- True  (default): the reference goal (y = 0) sits at the bottom
- False: pitch is flipped 180° so the opposite end sits at the bottom
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
    half_w = bundle.meta.pitch_width / 2.0
    if home_at_bottom:
        return x + half_w, y
    return half_w - x, bundle.meta.pitch_length - y


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
    half_w = bundle.meta.pitch_width / 2.0
    if home_at_bottom:
        return display_x - half_w, display_y
    return half_w - display_x, bundle.meta.pitch_length - display_y


def to_display_delta(
    dx: float | np.ndarray,
    dy: float | np.ndarray,
    home_at_bottom: bool = True,
) -> tuple[float | np.ndarray, float | np.ndarray]:
    """Map a tracking-space displacement into display space."""
    if home_at_bottom:
        return dx, dy
    return -dx, -dy
