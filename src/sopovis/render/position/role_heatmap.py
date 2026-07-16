"""Role heatmap — time × player-row tactical colours."""
from __future__ import annotations

import numpy as np
from matplotlib.colors import to_rgb

from sopovis.analytics.roles import ROLE_COLORS_X, ROLE_COLORS_Y
from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.presets import LayerSpec
from sopovis.render.common import meta_from_spec
from sopovis.render.elements import ElementMeta
from sopovis.render.position.context import PositionContext, RowBand
from sopovis.render.position.elements import PositionElement
from sopovis.render.position.geometry import (
    PLAYER_BAND,
    PLAYER_GAP,
    TEAM_GAP_ROWS,
)


class RoleHeatmap(PositionElement):
    """Stacked team blocks: upper strip = depth role, lower = lateral role."""

    def __init__(self, meta: ElementMeta):
        super().__init__(meta)

    @classmethod
    def from_spec(cls, spec: LayerSpec, bundle: PrecomputedBundle) -> "RoleHeatmap":
        return cls(meta_from_spec(spec))

    def build(self, ax, bundle: PrecomputedBundle, ctx: PositionContext) -> None:
        self.reset()
        ctx.row_bands.clear()
        ctx.yticks.clear()
        ctx.ylabels.clear()

        home, away = bundle.meta.home_team_id, bundle.meta.guest_team_id
        blocks: list[tuple[str, bool, bool]] = []
        if ctx.team_focus == "both":
            if ctx.home_at_bottom:
                blocks = [(away, True, False), (home, False, True)]
            else:
                blocks = [(home, True, False), (away, False, True)]
        elif ctx.team_focus == "home":
            blocks = [(home, not ctx.home_at_bottom, not ctx.home_at_bottom)]
        else:
            blocks = [(away, ctx.home_at_bottom, ctx.home_at_bottom)]

        n_bins = len(ctx.edges) - 1
        team_gap = np.ones((TEAM_GAP_ROWS * (PLAYER_BAND + PLAYER_GAP), n_bins, 3))
        parts: list[np.ndarray] = []
        offset = 0.0
        row_stride = PLAYER_BAND + PLAYER_GAP

        for i, (tid, reverse_rows, mirror_lateral) in enumerate(blocks):
            img, labels, band_cols = self._team_block(
                bundle, ctx, tid, reverse_rows=reverse_rows, mirror_lateral=mirror_lateral
            )
            if i > 0:
                parts.append(team_gap)
                offset += team_gap.shape[0]
            parts.append(img)
            for r, (label, cols) in enumerate(zip(labels, band_cols)):
                y0 = offset + r * row_stride
                y1 = y0 + PLAYER_BAND
                ctx.row_bands.append(RowBand(y0=y0, y1=y1, cols=cols))
                ctx.yticks.append(y0 + PLAYER_BAND / 2.0)
                ctx.ylabels.append(label)
            offset += img.shape[0]

        stacked = np.concatenate(parts, axis=0) if parts else np.ones((1, n_bins, 3))
        im = ax.imshow(
            stacked,
            aspect="auto",
            interpolation="nearest",
            extent=(0, bundle.total_frames, stacked.shape[0], 0),
            zorder=self.meta.z_order,
        )
        self._register(im)
        ax.set_xlim(ctx.t0, ctx.t1)

    def _team_block(
        self,
        bundle: PrecomputedBundle,
        ctx: PositionContext,
        team_id: str,
        *,
        reverse_rows: bool,
        mirror_lateral: bool,
    ) -> tuple[np.ndarray, list[str], list[list[int]]]:
        counts = bundle.role_counts
        band_cols: list[list[int]] = []
        labels: list[str] = []
        row_map: dict[int, list[int]] = {}
        for pid, row in bundle.player_row_order.items():
            if bundle.team_map.get(pid) == team_id:
                row_map.setdefault(row, []).append(bundle.player_index[pid])
        row_keys = sorted(row_map)
        if reverse_rows:
            row_keys = list(reversed(row_keys))
        for row in row_keys:
            cols = row_map[row]
            band_cols.append(cols)
            shirts = [
                str(bundle.player_registry[bundle.player_ids[c]].shirt_number)
                for c in cols
            ]
            labels.append("/".join(shirts))

        n_rows, n_bins = len(band_cols), len(ctx.edges) - 1
        row_stride = PLAYER_BAND + PLAYER_GAP
        img_h = max(0, n_rows * row_stride - (PLAYER_GAP if n_rows else 0))
        img = np.ones((img_h, n_bins, 3))
        y_colors = list(reversed(ROLE_COLORS_Y)) if mirror_lateral else ROLE_COLORS_Y
        edges = ctx.edges
        for r, cols in enumerate(band_cols):
            sel = np.ix_(edges[1:], cols)
            sel_prev = np.ix_(edges[:-1], cols)
            deltas = counts[sel].astype(np.int64) - counts[sel_prev].astype(np.int64)
            total = deltas.sum(axis=(1, 2))
            flat = deltas.sum(axis=1)
            best = flat.argmax(axis=1)
            base = r * row_stride
            for b in range(n_bins):
                if not ctx.bin_visible[b] or total[b] == 0:
                    continue
                x_role, y_role = best[b] // 5 - 2, best[b] % 5 - 2
                img[base, b] = to_rgb(ROLE_COLORS_X[x_role + 2])
                img[base + 1, b] = to_rgb(y_colors[y_role + 2])
        return img, labels, band_cols
