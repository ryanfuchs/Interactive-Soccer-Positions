"""Defensive line height indicator."""
from __future__ import annotations

import numpy as np

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.presets import LayerSpec
from sopovis.render.common import meta_from_spec, team_ids
from sopovis.render.elements import DynamicElement, ElementMeta


class DefensiveLineOverlay(DynamicElement):
    """Horizontal line at each team's deepest outfield player (vertical pitch)."""

    def __init__(self, meta: ElementMeta, team="both", line_width=1.5, opacity=0.7):
        super().__init__(meta)
        self.team = team
        self.line_width = line_width
        self.opacity = opacity
        self._lines: dict[str, object] = {}

    @classmethod
    def from_spec(cls, spec: LayerSpec, bundle: PrecomputedBundle) -> "DefensiveLineOverlay":
        return cls(meta_from_spec(spec), **spec.style)

    def _draw(self, ax, bundle: PrecomputedBundle, t: int) -> None:
        section = bundle.section_of(t)
        for tid in team_ids(bundle, self.team):
            if tid not in self._lines:
                line = ax.axhline(
                    0, color=bundle.teams[tid].shirt_main_color,
                    linewidth=self.line_width, alpha=self.opacity, linestyle="-.",
                )
                self._register(line)
                self._lines[tid] = line
            cols = [
                c for c in bundle.team_columns(tid)
                if not bundle.player_registry[bundle.player_ids[c]].is_goalkeeper
            ]
            ys = bundle.frames[t, cols, 1]
            ys = ys[np.isfinite(ys)]
            if len(ys) == 0:
                continue
            attacking_pos_y = bundle.attack_directions.get((tid, section), True)
            height = ys.min() if attacking_pos_y else ys.max()
            # Display y = goal-aligned longitudinal coordinate (depth).
            self._lines[tid].set_ydata([height, height])
