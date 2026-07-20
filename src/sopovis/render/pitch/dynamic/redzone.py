"""Red zone pitch overlay — filled NURBS boundary per team."""
from __future__ import annotations

import numpy as np
from matplotlib.patches import Polygon

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.presets import LayerSpec
from sopovis.render.common import meta_from_spec, team_ids
from sopovis.render.elements import DynamicElement, ElementMeta
from sopovis.render.orientation import to_display_points

_OFFSCREEN = np.array([[-100.0, -100.0], [-99.0, -100.0], [-100.0, -99.0]])


def _visible_team_color(team, fallback: str) -> str:
    """Shirt color unless it is too light to see on the pitch (e.g. white
    home shirts); then the secondary color, then ``fallback``."""
    from matplotlib.colors import to_rgb

    for color in (team.shirt_main_color, team.shirt_secondary_color):
        if not color:
            continue
        r, g, b = to_rgb(color)
        if 0.2126 * r + 0.7152 * g + 0.0722 * b < 0.72:
            return color
    return fallback


class RedzoneOverlay(DynamicElement):
    """Filled red zone (Tanner 2026) of one or both teams at the cursor frame.

    Reads the ``redzone`` product (NURBS control points + weights per
    analytics frame) and samples the closed boundary on draw. ``team``
    selects whose zone is shown; each zone is the space that team defends.
    ``team: defending`` follows the paper's definition and shows only the
    zone of the team currently out of possession.
    """

    def __init__(
        self,
        meta: ElementMeta,
        team="both",
        color="#d62728",
        use_team_colors=True,
        opacity=0.25,
        edge_width=1.5,
        samples=200,
    ):
        super().__init__(meta)
        self.team = team
        self.color = color
        self.use_team_colors = use_team_colors
        self.opacity = opacity
        self.edge_width = edge_width
        self.samples = int(samples)
        self._patches: dict[str, Polygon] = {}

    @classmethod
    def from_spec(cls, spec: LayerSpec, bundle: PrecomputedBundle) -> "RedzoneOverlay":
        return cls(meta_from_spec(spec), **spec.style)

    def _draw(self, ax, bundle: PrecomputedBundle, t: int) -> None:
        from sopovis.analytics.redzone import evaluate_closed_nurbs

        result = bundle.product("redzone")
        ta = bundle.to_analytics_frame(t)
        if self.team == "defending":
            possession = int(bundle.ball_possession[t])
            shown = {
                1: [bundle.meta.guest_team_id],
                2: [bundle.meta.home_team_id],
            }.get(possession, [])
        else:
            shown = team_ids(bundle, self.team)
        for tid, patch in self._patches.items():
            if tid not in shown:
                patch.set_xy(_OFFSCREEN)
        for tid in shown:
            if tid not in self._patches:
                face = (
                    _visible_team_color(bundle.teams[tid], self.color)
                    if self.use_team_colors
                    else self.color
                )
                patch = Polygon(
                    _OFFSCREEN,
                    closed=True,
                    facecolor=face,
                    edgecolor=face,
                    alpha=self.opacity,
                    linewidth=self.edge_width,
                )
                ax.add_patch(patch)
                self._register(patch)
                self._patches[tid] = patch

            ctrl = result.control_points[tid][ta]
            if ctrl is None:
                self._patches[tid].set_xy(_OFFSCREEN)
                continue
            boundary = evaluate_closed_nurbs(
                ctrl, result.weights[tid][ta], self.samples
            )
            self._patches[tid].set_xy(
                to_display_points(boundary, bundle, home_at_bottom=True)
            )
