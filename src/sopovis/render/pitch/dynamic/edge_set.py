"""Generic renderer for edge-valued analytics products (player relations)."""
from __future__ import annotations

import numpy as np
from matplotlib.collections import LineCollection

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.presets import LayerSpec
from sopovis.render.common import meta_from_spec, team_ids
from sopovis.render.elements import DynamicElement, ElementMeta
from sopovis.render.orientation import to_display_points


class EdgeSetOverlay(DynamicElement):
    """Line segments between related players — one collection per team.

    ``relation`` names any product whose value is
    ``team_id → per-analytics-frame (E, 2)`` player-column pairs
    (shape graph, proximity, passing options, …). The relation is data,
    this class is only its visual encoding.
    """

    def __init__(
        self,
        meta: ElementMeta,
        relation="shape_graph",
        team="both",
        color="#A9A9A9",
        line_width=2.0,
        opacity=0.8,
    ):
        super().__init__(meta)
        self.relation = relation
        self.team = team
        self.color = color
        self.line_width = line_width
        self.opacity = opacity
        self._collections: dict[str, LineCollection] = {}

    @classmethod
    def from_spec(cls, spec: LayerSpec, bundle: PrecomputedBundle) -> "EdgeSetOverlay":
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
            edges = bundle.edges_at(t, self.relation, tid)
            xy = to_display_points(bundle.frames[t, :, :2], bundle, home_at_bottom=True)
            segments = [
                (xy[a], xy[b])
                for a, b in edges
                if np.isfinite(xy[a]).all() and np.isfinite(xy[b]).all()
            ]
            self._collections[tid].set_segments(segments)
