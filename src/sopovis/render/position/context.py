"""PositionContext — shared state for one position redraw.

Every overlay reads the same *view parameters* (resolution, filters, team
focus, orientation, visible time window), the precomputed bin geometry
(``edges``, ``bin_visible``), and the row layout (``blocks``, ``row_bands``,
axis labels). The layout is computed here, not by ``RoleHeatmap``, so every
row-aligned overlay works even when the heatmap layer is disabled. Layers may
still write back into the context — ``SubstitutionMarkers`` registers vline
artists for hover emphasis.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.render.position.filters import (
    bin_visible_mask,
    frame_mask,
)
from sopovis.render.position.geometry import PLAYER_BAND, PLAYER_GAP, TEAM_GAP_ROWS


@dataclass
class RowBand:
    """One player row in image-row coordinates (for hover + highlight)."""

    y0: float
    y1: float
    cols: list[int]


@dataclass
class TeamBlock:
    """One team's stacked rows: layout inputs plus its first image row."""

    team_id: str
    reverse_rows: bool
    mirror_lateral: bool
    band_cols: list[list[int]]
    labels: list[str]
    y_offset: float


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
    blocks: list[TeamBlock] = field(default_factory=list)
    row_bands: list[RowBand] = field(default_factory=list)
    total_rows: float = 0.0
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
        ctx = cls(
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
        ctx._compute_row_layout(bundle)
        return ctx

    def _compute_row_layout(self, bundle: PrecomputedBundle) -> None:
        """Team blocks, row bands, and axis labels for the current view."""
        home, away = bundle.meta.home_team_id, bundle.meta.guest_team_id
        if self.team_focus == "both":
            if self.home_at_bottom:
                specs = [(away, True, False), (home, False, True)]
            else:
                specs = [(home, True, False), (away, False, True)]
        elif self.team_focus == "home":
            specs = [(home, not self.home_at_bottom, not self.home_at_bottom)]
        else:
            specs = [(away, self.home_at_bottom, self.home_at_bottom)]

        row_stride = PLAYER_BAND + PLAYER_GAP
        offset = 0.0
        for i, (tid, reverse_rows, mirror_lateral) in enumerate(specs):
            row_map: dict[int, list[int]] = {}
            for pid, row in bundle.player_row_order.items():
                if bundle.team_map.get(pid) == tid:
                    row_map.setdefault(row, []).append(bundle.player_index[pid])
            row_keys = sorted(row_map)
            if reverse_rows:
                row_keys = list(reversed(row_keys))
            band_cols = [row_map[row] for row in row_keys]
            labels = [
                "/".join(
                    str(bundle.player_registry[bundle.player_ids[c]].shirt_number)
                    for c in cols
                )
                for cols in band_cols
            ]

            if i > 0:
                offset += TEAM_GAP_ROWS * row_stride
            self.blocks.append(
                TeamBlock(tid, reverse_rows, mirror_lateral, band_cols, labels, offset)
            )
            for r, (label, cols) in enumerate(zip(labels, band_cols)):
                y0 = offset + r * row_stride
                self.row_bands.append(RowBand(y0=y0, y1=y0 + PLAYER_BAND, cols=cols))
                self.yticks.append(y0 + PLAYER_BAND / 2.0)
                self.ylabels.append(label)
            n_rows = len(band_cols)
            offset += max(0, n_rows * row_stride - (PLAYER_GAP if n_rows else 0))
        self.total_rows = offset
