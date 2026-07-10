"""Player position glyphs."""
from __future__ import annotations

import numpy as np

from sopovis.analytics.roles import ROLE_COLORS_X, ROLE_COLORS_Y, UNSET
from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.presets import LayerSpec
from sopovis.render.common import meta_from_spec, team_ids
from sopovis.render.elements import DynamicElement, ElementMeta
from sopovis.render.orientation import to_display_points
from sopovis.render.sizes import PLAYER_MARKER_PT


class TeamColorGlyph(DynamicElement):
    """Player dots. color_mode: team | role_depth | role_lateral | dominant."""

    def __init__(
        self,
        meta: ElementMeta,
        team="both",
        size=PLAYER_MARKER_PT,
        color_mode="team",
        show_goalkeepers=True,
        edge_color="#222222",
    ):
        super().__init__(meta)
        self.team = team
        self.size = size
        self.color_mode = color_mode
        self.show_goalkeepers = show_goalkeepers
        self.edge_color = edge_color
        self._scatter = None
        self._cols: np.ndarray | None = None
        self._team_colors: np.ndarray | None = None

    @classmethod
    def from_spec(cls, spec: LayerSpec, bundle: PrecomputedBundle) -> "TeamColorGlyph":
        return cls(meta_from_spec(spec), **spec.style)

    def _prepare(self, ax, bundle: PrecomputedBundle) -> None:
        cols = []
        colors = []
        for tid in team_ids(bundle, self.team):
            shirt = bundle.teams[tid].shirt_main_color
            for c in bundle.team_columns(tid):
                player = bundle.player_registry[bundle.player_ids[c]]
                if not self.show_goalkeepers and player.is_goalkeeper:
                    continue
                cols.append(c)
                colors.append(shirt)
        self._cols = np.asarray(cols, dtype=np.int32)
        self._team_colors = np.asarray(colors, dtype=object)
        self._scatter = ax.scatter(
            [], [], s=self.size**2, edgecolors=self.edge_color, linewidths=0.7
        )
        self._register(self._scatter)

    def _colors_for(self, bundle: PrecomputedBundle, t: int) -> np.ndarray:
        if self.color_mode == "team":
            return self._team_colors
        roles = bundle.roles_at(t)[self._cols]
        out = np.empty(len(self._cols), dtype=object)
        for i, (xr, yr) in enumerate(roles):
            if xr == UNSET:
                out[i] = self._team_colors[i]
            elif self.color_mode == "role_depth":
                out[i] = ROLE_COLORS_X[xr + 2]
            elif self.color_mode == "role_lateral":
                out[i] = ROLE_COLORS_Y[yr + 2]
            else:
                if abs(xr) == 2:
                    out[i] = ROLE_COLORS_X[xr + 2]
                elif abs(yr) == 2:
                    out[i] = ROLE_COLORS_Y[yr + 2]
                else:
                    out[i] = "#A9A9A9"
        return out

    def _draw(self, ax, bundle: PrecomputedBundle, t: int) -> None:
        if self._scatter is None:
            self._prepare(ax, bundle)
        xy = to_display_points(bundle.frames[t, self._cols, :2], bundle, home_at_bottom=True)
        visible = np.isfinite(xy).all(axis=1)
        offsets = np.where(visible[:, None], xy, -100.0)
        self._scatter.set_offsets(offsets)
        self._scatter.set_facecolor(list(self._colors_for(bundle, t)))
