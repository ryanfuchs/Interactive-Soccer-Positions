"""Pitch grass and line markings."""
from __future__ import annotations

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.presets import LayerSpec
from sopovis.render.common import meta_from_spec
from sopovis.render.elements import ElementMeta, StaticElement


class PitchMarkings(StaticElement):
    """Grass + line markings via mplsoccer custom pitch."""

    def __init__(self, meta: ElementMeta, grass_color="#2e7d46", line_color="#ffffff"):
        super().__init__(meta)
        self.grass_color = grass_color
        self.line_color = line_color

    @classmethod
    def from_spec(cls, spec: LayerSpec, bundle: PrecomputedBundle) -> "PitchMarkings":
        return cls(meta_from_spec(spec), **spec.style)

    def _build(self, ax, bundle: PrecomputedBundle) -> None:
        from mplsoccer import Pitch

        before = set(ax.get_children())
        pitch = Pitch(
            pitch_type="custom",
            pitch_length=bundle.meta.pitch_x,
            pitch_width=bundle.meta.pitch_y,
            pitch_color=self.grass_color,
            line_color=self.line_color,
            linewidth=1.2,
        )
        pitch.draw(ax=ax)
        self._register(*(set(ax.get_children()) - before))
