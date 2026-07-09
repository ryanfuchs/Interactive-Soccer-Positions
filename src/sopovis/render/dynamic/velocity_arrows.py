"""Player velocity arrows."""
from __future__ import annotations

import numpy as np

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.presets import LayerSpec
from sopovis.render.common import meta_from_spec, team_ids
from sopovis.render.elements import DynamicElement, ElementMeta


class VelocityArrow(DynamicElement):
    """Velocity vectors from frame-to-frame displacement, scaled by speed."""

    def __init__(self, meta: ElementMeta, team="both", scale=1.0, color="#ffff88", opacity=0.9):
        super().__init__(meta)
        self.team = team
        self.scale = scale
        self.color = color
        self.opacity = opacity
        self._quiver = None
        self._cols: np.ndarray | None = None

    @classmethod
    def from_spec(cls, spec: LayerSpec, bundle: PrecomputedBundle) -> "VelocityArrow":
        return cls(meta_from_spec(spec), **spec.style)

    def _draw(self, ax, bundle: PrecomputedBundle, t: int) -> None:
        if self._cols is None:
            cols = []
            for tid in team_ids(bundle, self.team):
                cols.extend(bundle.team_columns(tid))
            self._cols = np.asarray(cols, dtype=np.int32)
        t_prev = max(t - 1, 0)
        xy = bundle.frames[t, self._cols, :2]
        d = (xy - bundle.frames[t_prev, self._cols, :2]) * bundle.frame_rate * self.scale
        ok = np.isfinite(xy).all(axis=1) & np.isfinite(d).all(axis=1)
        xy = np.where(ok[:, None], xy, -100.0)
        d = np.where(ok[:, None], d, 0.0)
        if self._quiver is not None:
            self._quiver.remove()
            self._artists.remove(self._quiver)
        self._quiver = ax.quiver(
            xy[:, 0], xy[:, 1], d[:, 0], d[:, 1],
            angles="xy", scale_units="xy", scale=1.0,
            color=self.color, alpha=self.opacity, width=0.004,
        )
        self._register(self._quiver)
