"""TimelineStack + TimelineStackBuilder — config-driven timeline draw loop.

Mirrors the pitch-side ``SceneRenderer`` / ``SceneBuilder`` pair: the stack
owns the ordered element list and the draw loop; views only manage the Axes
and interactions.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.presets import LayerSpec
from sopovis.render.timeline.elements import TimelineElement
from sopovis.render.timeline.geometry import TimelineGeometry

if TYPE_CHECKING:
    from sopovis.render.timeline.registry import TimelineElementRegistry


class TimelineStack:
    def __init__(self, elements: list[TimelineElement]):
        self.set_elements(elements)

    def set_elements(self, elements: list[TimelineElement]) -> None:
        self.elements = sorted(elements, key=lambda e: e.meta.z_order)

    def build(self, ax, bundle: PrecomputedBundle, geom: TimelineGeometry) -> None:
        """Draw all enabled layers onto a cleared Axes (analog of SceneRenderer.draw)."""
        for el in self.elements:
            if el.meta.enabled:
                el.build(ax, bundle, geom)
            else:
                el.reset()

    def get(self, name: str) -> TimelineElement | None:
        for el in self.elements:
            if el.meta.name == name:
                return el
        return None

    def set_enabled(self, name: str, enabled: bool) -> None:
        for el in self.elements:
            if el.meta.name == name:
                el.meta.enabled = enabled

    @property
    def layer_names(self) -> list[str]:
        return [el.meta.name for el in self.elements]


class TimelineStackBuilder:
    def __init__(self, registry: "TimelineElementRegistry"):
        self.registry = registry

    def build(self, layers: list[LayerSpec], bundle: PrecomputedBundle) -> TimelineStack:
        elements = [
            self.registry.create(spec, bundle)
            for spec in sorted(layers, key=lambda s: s.z_order)
        ]
        return TimelineStack(elements)
