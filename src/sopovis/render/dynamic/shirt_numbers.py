"""Shirt number labels on player positions."""
from __future__ import annotations

import numpy as np

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.presets import LayerSpec
from sopovis.render.common import meta_from_spec, team_ids
from sopovis.render.elements import DynamicElement, ElementMeta


class ShirtNumberLabel(DynamicElement):
    def __init__(self, meta: ElementMeta, team="both", font_size=7.0, color=None):
        super().__init__(meta)
        self.team = team
        self.font_size = font_size
        self.color = color
        self._texts: dict[int, object] = {}

    @classmethod
    def from_spec(cls, spec: LayerSpec, bundle: PrecomputedBundle) -> "ShirtNumberLabel":
        return cls(meta_from_spec(spec), **spec.style)

    def _prepare(self, ax, bundle: PrecomputedBundle) -> None:
        for tid in team_ids(bundle, self.team):
            number_color = self.color or bundle.teams[tid].shirt_number_color
            for c in bundle.team_columns(tid):
                player = bundle.player_registry[bundle.player_ids[c]]
                txt = ax.text(
                    -100, -100, str(player.shirt_number),
                    ha="center", va="center",
                    fontsize=self.font_size, color=number_color,
                    clip_on=True,
                )
                self._register(txt)
                self._texts[c] = txt

    def _draw(self, ax, bundle: PrecomputedBundle, t: int) -> None:
        if not self._texts:
            self._prepare(ax, bundle)
        xy = bundle.frames[t, :, :2]
        for c, txt in self._texts.items():
            x, y = xy[c]
            if np.isfinite(x) and np.isfinite(y):
                txt.set_position((x, y))
            else:
                txt.set_position((-100, -100))
