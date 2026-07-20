"""Lane divider line and team name labels."""
from __future__ import annotations

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.presets import LayerSpec
from sopovis.render.common import meta_from_spec
from sopovis.render.elements import ElementMeta
from sopovis.render.timeline.common import team_label_color
from sopovis.render.timeline.elements import TimelineElement
from sopovis.render.timeline.geometry import DIVIDER_Y, LANE_CENTRE, TimelineGeometry


class LaneFurniture(TimelineElement):
    """Lane divider line and team name labels."""

    def __init__(self, meta: ElementMeta):
        super().__init__(meta)

    @classmethod
    def from_spec(cls, spec: LayerSpec, bundle: PrecomputedBundle) -> "LaneFurniture":
        return cls(meta_from_spec(spec))

    def build(self, ax, bundle: PrecomputedBundle, geom: TimelineGeometry) -> None:
        self.reset()
        divider = ax.axhline(DIVIDER_Y, color="#cccccc", linewidth=0.9)
        self._register(divider)
        # Team names sit outside the strip (home above, away below) so they
        # never cover possession lines or event markers.
        top_lane = max(LANE_CENTRE, key=LANE_CENTRE.get)
        for lane, team_id in (
            ("home", bundle.meta.home_team_id),
            ("away", bundle.meta.guest_team_id),
        ):
            team = bundle.teams[team_id]
            above = lane == top_lane
            # Below the strip the minute tick labels come first; drop the
            # away name beneath them.
            label = ax.text(
                0.0,
                1.02 if above else -0.16,
                team.team_name,
                transform=ax.transAxes,
                ha="left",
                va="bottom" if above else "top",
                fontsize=7,
                fontweight="bold",
                color=team_label_color(team.shirt_main_color, team.shirt_secondary_color),
                clip_on=False,
            )
            self._register(label)
