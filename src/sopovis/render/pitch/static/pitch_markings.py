"""Pitch grass and line markings (vertical orientation)."""
from __future__ import annotations

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.presets import LayerSpec
from sopovis.render.common import meta_from_spec
from sopovis.render.elements import ElementMeta, StaticElement


class PitchMarkings(StaticElement):
    """Grass + line markings via mplsoccer VerticalPitch (length bottom→top)."""

    def __init__(
        self,
        meta: ElementMeta,
        grass_color="#2e7d46",
        line_color="#ffffff",
        goal_color: str | None = None,
        goal_depth: float = 2.44,
        goal_width: float = 7.32,
    ):
        super().__init__(meta)
        self.grass_color = grass_color
        self.line_color = line_color
        # Keep goals visible on white outer backgrounds while preserving line color on-pitch.
        self.goal_color = goal_color
        self.goal_depth = goal_depth
        self.goal_width = goal_width

    @classmethod
    def from_spec(cls, spec: LayerSpec, bundle: PrecomputedBundle) -> "PitchMarkings":
        return cls(meta_from_spec(spec), **spec.style)

    def _build(self, ax, bundle: PrecomputedBundle) -> None:
        from matplotlib.patches import Rectangle
        from mplsoccer import VerticalPitch

        before = set(ax.get_children())
        pitch = VerticalPitch(
            pitch_type="custom",
            pitch_length=bundle.meta.pitch_x,
            pitch_width=bundle.meta.pitch_y,
            pitch_color=self.grass_color,
            line_color=self.line_color,
            linewidth=1.2,
            goal_type="box",
        )
        pitch.draw(ax=ax)
        goal_color = self.goal_color or (
            "#222222"
            if self.line_color.lower() in {"#fff", "#ffffff", "white"}
            else self.line_color
        )
        x0 = (bundle.meta.pitch_y - self.goal_width) / 2.0
        bottom_goal = Rectangle(
            (x0, -self.goal_depth),
            self.goal_width,
            self.goal_depth,
            fill=False,
            edgecolor=goal_color,
            linewidth=1.2,
            clip_on=False,
        )
        top_goal = Rectangle(
            (x0, bundle.meta.pitch_x),
            self.goal_width,
            self.goal_depth,
            fill=False,
            edgecolor=goal_color,
            linewidth=1.2,
            clip_on=False,
        )
        ax.add_patch(bottom_goal)
        ax.add_patch(top_goal)
        self._register(*(set(ax.get_children()) - before))
