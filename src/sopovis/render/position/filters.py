"""Frame and bin filters shared by position layers."""
from __future__ import annotations

import numpy as np

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.render.position.geometry import BIN_VISIBLE_FRAC

POSSESSION_ALL = "all"
POSSESSION_HOME = "home"  # ball_possession code 1
POSSESSION_AWAY = "away"  # ball_possession code 2
POSSESSION_CONTESTED = "contested"  # code 0 (unknown / contested)


def frame_mask(
    bundle: PrecomputedBundle,
    *,
    ball_in_play: bool,
    possession_filter: str,
) -> np.ndarray:
    """Boolean mask over tracking frames that pass ball/possession filters."""
    n = bundle.total_frames
    mask = np.ones(n, dtype=bool)
    if ball_in_play:
        status = bundle.ball[:, 3]
        mask &= np.isfinite(status) & (status == 1)
    if possession_filter == POSSESSION_HOME:
        mask &= bundle.ball_possession == 1
    elif possession_filter == POSSESSION_AWAY:
        mask &= bundle.ball_possession == 2
    elif possession_filter == POSSESSION_CONTESTED:
        mask &= bundle.ball_possession == 0
    return mask


def bin_visible_mask(
    bundle: PrecomputedBundle,
    edges: np.ndarray,
    frame_mask: np.ndarray,
    *,
    ball_in_play: bool,
    possession_filter: str,
) -> np.ndarray:
    """Per-bin visibility from the fraction of tracking frames that pass filters."""
    indices = bundle.analytics_frame_indices
    n_bins = len(edges) - 1
    visible = np.ones(n_bins, dtype=bool)
    if not (ball_in_play or possession_filter != POSSESSION_ALL):
        return visible
    for b in range(n_bins):
        ta0, ta1 = int(edges[b]), int(edges[b + 1])
        t0 = int(indices[ta0])
        t1 = int(indices[min(ta1, len(indices) - 1)])
        if t1 <= t0:
            t1 = min(t0 + 1, bundle.total_frames)
        segment = frame_mask[t0:t1]
        if len(segment) == 0 or float(segment.mean()) < BIN_VISIBLE_FRAC:
            visible[b] = False
    return visible
