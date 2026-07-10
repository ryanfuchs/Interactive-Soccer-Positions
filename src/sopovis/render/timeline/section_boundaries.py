"""Vertical lines at period starts."""
from __future__ import annotations

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.presets import LayerSpec
from sopovis.render.common import meta_from_spec
from sopovis.render.elements import ElementMeta
from sopovis.render.timeline.elements import TimelineElement
from sopovis.render.timeline.geometry import TimelineGeometry


class SectionBoundaries(TimelineElement):
    """Vertical lines at period starts (2nd half, extra time, …)."""

    def __init__(self, meta: ElementMeta, color="#999999"):
        super().__init__(meta)
        self.color = color

    @classmethod
    def from_spec(cls, spec: LayerSpec, bundle: PrecomputedBundle) -> "SectionBoundaries":
        return cls(meta_from_spec(spec), **spec.style)

    def build(self, ax, bundle: PrecomputedBundle, geom: TimelineGeometry) -> None:
        self.reset()
        for _name, (lo, _hi) in bundle.section_ranges.items():
            if lo == 0:
                continue
            self._register(ax.axvline(lo, color=self.color, linewidth=1.0))
