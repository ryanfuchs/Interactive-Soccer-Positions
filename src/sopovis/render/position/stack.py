"""PositionStack + PositionStackBuilder — config-driven position-plot draw loop."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.presets import LayerSpec
from sopovis.render.position.context import PositionContext
from sopovis.render.position.elements import PositionElement

if TYPE_CHECKING:
    from sopovis.render.position.registry import PositionElementRegistry


class PositionStack:
    def __init__(self, elements: list[PositionElement]):
        self.set_elements(elements)

    def set_elements(self, elements: list[PositionElement]) -> None:
        self.elements = sorted(elements, key=lambda e: e.meta.z_order)

    def build(self, ax, bundle: PrecomputedBundle, ctx: PositionContext) -> None:
        for el in self.elements:
            if el.meta.enabled:
                el.build(ax, bundle, ctx)
            else:
                el.reset()

    def get(self, name: str) -> PositionElement | None:
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


class PositionStackBuilder:
    def __init__(self, registry: "PositionElementRegistry"):
        self.registry = registry

    def build(self, layers: list[LayerSpec], bundle: PrecomputedBundle) -> PositionStack:
        elements = [
            self.registry.create(spec, bundle)
            for spec in sorted(layers, key=lambda s: s.z_order)
        ]
        return PositionStack(elements)
