"""Shape-graph edges per team."""
from __future__ import annotations

import numpy as np
from matplotlib.collections import LineCollection

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.presets import LayerSpec
from sopovis.render.common import meta_from_spec, team_ids
from sopovis.render.elements import DynamicElement, ElementMeta
from sopovis.render.orientation import to_display_points


class ShapeGraphOverlay(DynamicElement):
    """Shape-graph edges from bundle.shape_edges_at(t) — one collection per team."""

    def __init__(self, meta: ElementMeta, team="both", color="#A9A9A9", line_width=2.0, opacity=0.8):
        super().__init__(meta)
        self.team = team
        self.color = color
        self.line_width = line_width
        self.opacity = opacity
        self._collections: dict[str, LineCollection] = {}

    @classmethod
    def from_spec(cls, spec: LayerSpec, bundle: PrecomputedBundle) -> "ShapeGraphOverlay":
        return cls(meta_from_spec(spec), **spec.style)

    def _draw(self, ax, bundle: PrecomputedBundle, t: int) -> None:
        for tid in team_ids(bundle, self.team):
            if tid not in self._collections:
                lc = LineCollection(
                    [], colors=self.color, linewidths=self.line_width, alpha=self.opacity
                )
                ax.add_collection(lc)
                self._register(lc)
                self._collections[tid] = lc
            edges = bundle.shape_edges_at(t, tid)
            xy = to_display_points(bundle.frames[t, :, :2], bundle, home_at_bottom=True)
            segments = [
                (xy[a], xy[b])
                for a, b in edges
                if np.isfinite(xy[a]).all() and np.isfinite(xy[b]).all()
            ]
            self._collections[tid].set_segments(segments)
