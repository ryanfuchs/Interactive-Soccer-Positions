"""PositionContext — shared state for one position redraw.

Every overlay reads the same *view parameters* (resolution, filters, team
focus, orientation, visible time window) and the precomputed bin geometry
(``edges``, ``bin_visible``). Layers may write back into the context —
``RoleHeatmap`` publishes row bands and axis labels; ``SubstitutionMarkers``
registers vline artists for hover emphasis.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.render.position.filters import (
    bin_visible_mask,
    frame_mask,
)


@dataclass
class RowBand:
    """One player row in image-row coordinates (for hover + highlight)."""

    y0: float
    y1: float
    cols: list[int]


@dataclass
class PositionContext:
    resolution: int
    team_focus: str  # "home" | "away" | "both"
    home_at_bottom: bool
    ball_in_play: bool
    possession_filter: str
    t0: int
    t1: int  # exclusive tracking-frame end of visible window

    edges: np.ndarray = field(default_factory=lambda: np.array([], dtype=int))
    bin_visible: np.ndarray = field(default_factory=lambda: np.array([], dtype=bool))
    row_bands: list[RowBand] = field(default_factory=list)
    yticks: list[float] = field(default_factory=list)
    ylabels: list[str] = field(default_factory=list)
    sub_lines: dict[int, object] = field(default_factory=dict)

    @property
    def time_window(self) -> tuple[int, int]:
        return self.t0, self.t1

    def resolution_seconds(self, bundle: PrecomputedBundle) -> float:
        return self.resolution * bundle.analytics_stride / bundle.frame_rate

    @classmethod
    def prepare(
        cls,
        bundle: PrecomputedBundle,
        *,
        resolution: int,
        team_focus: str,
        home_at_bottom: bool,
        ball_in_play: bool,
        possession_filter: str,
        time_window: tuple[int, int],
    ) -> "PositionContext":
        t0, t1 = time_window
        res = max(1, int(resolution))
        ta_total = bundle.total_analytics_frames
        n_bins = max(1, ta_total // res)
        edges = np.linspace(0, ta_total - 1, n_bins + 1).astype(int)
        mask = frame_mask(
            bundle, ball_in_play=ball_in_play, possession_filter=possession_filter
        )
        visible = bin_visible_mask(
            bundle,
            edges,
            mask,
            ball_in_play=ball_in_play,
            possession_filter=possession_filter,
        )
        return cls(
            resolution=res,
            team_focus=team_focus,
            home_at_bottom=home_at_bottom,
            ball_in_play=ball_in_play,
            possession_filter=possession_filter,
            t0=int(t0),
            t1=int(t1),
            edges=edges,
            bin_visible=visible,
        )
