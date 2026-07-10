"""Ball position glyph."""
from __future__ import annotations

import numpy as np

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.presets import LayerSpec
from sopovis.render.common import meta_from_spec
from sopovis.render.elements import DynamicElement, ElementMeta
from sopovis.render.orientation import to_display_xy
from sopovis.render.sizes import BALL_MARKER_PT


class BallGlyph(DynamicElement):
    def __init__(
        self,
        meta: ElementMeta,
        size=BALL_MARKER_PT,
        color="#ffffff",
        edge_color="#000000",
    ):
        super().__init__(meta)
        self.size = size
        self.color = color
        self.edge_color = edge_color
        self._scatter = None

    @classmethod
    def from_spec(cls, spec: LayerSpec, bundle: PrecomputedBundle) -> "BallGlyph":
        return cls(meta_from_spec(spec), **spec.style)

    def _draw(self, ax, bundle: PrecomputedBundle, t: int) -> None:
        if self._scatter is None:
            self._scatter = ax.scatter(
                [], [], s=self.size**2, c=self.color,
                edgecolors=self.edge_color, linewidths=1.0,
            )
            self._register(self._scatter)
        bx, by = bundle.ball[t, 0], bundle.ball[t, 1]
        if np.isfinite(bx) and np.isfinite(by):
            dx, dy = to_display_xy(bx, by, bundle, home_at_bottom=True)
            self._scatter.set_offsets([[dx, dy]])
        else:
            self._scatter.set_offsets([[-100, -100]])
