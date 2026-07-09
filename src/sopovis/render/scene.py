"""SceneRenderer + SceneBuilder — single config-driven draw loop."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.presets import LayerSpec
from sopovis.render.elements import Element, StaticElement

if TYPE_CHECKING:
    from sopovis.render.registry import ElementRegistry


class SceneRenderer:
    def __init__(self, elements: list[Element]):
        self.set_elements(elements)

    def set_elements(self, elements: list[Element]) -> None:
        self.elements = sorted(elements, key=lambda e: e.meta.z_order)

    def draw(self, ax, bundle: PrecomputedBundle, t: int) -> None:
        for el in self.elements:
            el.draw(ax, bundle, t)

    def invalidate_static(self) -> None:
        for el in self.elements:
            if isinstance(el, StaticElement):
                el.invalidate()

    def set_enabled(self, name: str, enabled: bool) -> None:
        for el in self.elements:
            if el.meta.name == name:
                el.meta.enabled = enabled

    def get(self, name: str) -> Element | None:
        for el in self.elements:
            if el.meta.name == name:
                return el
        return None

    @property
    def layer_names(self) -> list[str]:
        return [el.meta.name for el in self.elements]


class SceneBuilder:
    def __init__(self, registry: "ElementRegistry"):
        self.registry = registry

    def build(self, layers: list[LayerSpec], bundle: PrecomputedBundle) -> SceneRenderer:
        elements = [
            self.registry.create(spec, bundle)
            for spec in sorted(layers, key=lambda s: s.z_order)
        ]
        return SceneRenderer(elements)
