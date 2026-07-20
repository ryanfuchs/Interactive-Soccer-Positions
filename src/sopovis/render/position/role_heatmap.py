"""Role heatmap — time × player-row tactical colours."""
from __future__ import annotations

import numpy as np
from matplotlib.colors import to_rgb

from sopovis.analytics.roles import ROLE_COLORS_X, ROLE_COLORS_Y
from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.presets import LayerSpec
from sopovis.render.common import meta_from_spec
from sopovis.render.elements import ElementMeta
from sopovis.render.position.context import PositionContext, TeamBlock
from sopovis.render.position.elements import PositionElement
from sopovis.render.position.geometry import (
    PLAYER_BAND,
    PLAYER_GAP,
    TEAM_GAP_ROWS,
)


class RoleHeatmap(PositionElement):
    """Stacked team blocks: upper strip = depth role, lower = lateral role.

    Row layout (blocks, bands, labels) comes precomputed from the context;
    this element only fills in the role colors.
    """

    def __init__(self, meta: ElementMeta):
        super().__init__(meta)

    @classmethod
    def from_spec(cls, spec: LayerSpec, bundle: PrecomputedBundle) -> "RoleHeatmap":
        return cls(meta_from_spec(spec))

    def build(self, ax, bundle: PrecomputedBundle, ctx: PositionContext) -> None:
        self.reset()
        n_bins = len(ctx.edges) - 1
        team_gap = np.ones((TEAM_GAP_ROWS * (PLAYER_BAND + PLAYER_GAP), n_bins, 3))
        parts: list[np.ndarray] = []
        for i, block in enumerate(ctx.blocks):
            if i > 0:
                parts.append(team_gap)
            parts.append(self._team_image(bundle, ctx, block))

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

    def _team_image(
        self, bundle: PrecomputedBundle, ctx: PositionContext, block: TeamBlock
    ) -> np.ndarray:
        counts = bundle.role_counts
        band_cols = block.band_cols
        n_rows, n_bins = len(band_cols), len(ctx.edges) - 1
        row_stride = PLAYER_BAND + PLAYER_GAP
        img_h = max(0, n_rows * row_stride - (PLAYER_GAP if n_rows else 0))
        img = np.ones((img_h, n_bins, 3))
        y_colors = (
            list(reversed(ROLE_COLORS_Y)) if block.mirror_lateral else ROLE_COLORS_Y
        )
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
        return img
