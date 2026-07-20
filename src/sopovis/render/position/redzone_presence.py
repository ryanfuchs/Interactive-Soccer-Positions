"""Red zone presence overlay — marks when a player is inside the opponent's
red zone on the position-analysis heatmap."""
from __future__ import annotations

import numpy as np
from matplotlib.colors import to_rgb

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.presets import LayerSpec
from sopovis.render.common import meta_from_spec
from sopovis.render.elements import ElementMeta
from sopovis.render.position.context import PositionContext
from sopovis.render.position.elements import PositionElement


class RedzonePresence(PositionElement):
    """Semi-transparent ticks over player rows while in the opponent red zone.

    Uses the row layout the context precomputes, so it works with or without
    the role heatmap layer. Per time bin, opacity scales with the fraction of
    analytics frames the player spent inside the opposing team's red zone;
    bins below ``min_fraction`` stay clear.
    """

    def __init__(
        self,
        meta: ElementMeta,
        color: str = "#d62728",
        max_opacity: float = 0.85,
        min_fraction: float = 0.05,
    ):
        super().__init__(meta)
        self.color = color
        self.max_opacity = float(max_opacity)
        self.min_fraction = float(min_fraction)

    @classmethod
    def from_spec(cls, spec: LayerSpec, bundle: PrecomputedBundle) -> "RedzonePresence":
        return cls(meta_from_spec(spec), **spec.style)

    def build(self, ax, bundle: PrecomputedBundle, ctx: PositionContext) -> None:
        self.reset()
        if not ctx.row_bands:
            return
        inside = bundle.product("redzone").inside_opponent  # (Ta, N) bool
        edges = ctx.edges
        n_bins = len(edges) - 1
        height = int(np.ceil(ctx.total_rows))
        rgba = np.zeros((height, n_bins, 4))
        rgb = to_rgb(self.color)

        # cumulative sum over analytics frames → O(1) per-bin fractions
        cum = np.cumsum(inside.astype(np.int32), axis=0)
        for band in ctx.row_bands:
            cols = band.cols
            in_bin = (
                cum[edges[1:]][:, cols].sum(axis=1)
                - cum[edges[:-1]][:, cols].sum(axis=1)
            ).astype(float)
            frac = in_bin / np.maximum(1, edges[1:] - edges[:-1])
            frac[frac < self.min_fraction] = 0.0
            alpha = np.clip(frac, 0.0, 1.0) * self.max_opacity
            visible = ctx.bin_visible & (alpha > 0)
            y0, y1 = int(round(band.y0)), int(round(band.y1))
            for row in range(y0, min(y1, height)):
                rgba[row, visible, :3] = rgb
                rgba[row, visible, 3] = alpha[visible]

        im = ax.imshow(
            rgba,
            aspect="auto",
            interpolation="nearest",
            extent=(0, bundle.total_frames, height, 0),
            zorder=self.meta.z_order,
        )
        self._register(im)
        ax.set_xlim(ctx.t0, ctx.t1)
