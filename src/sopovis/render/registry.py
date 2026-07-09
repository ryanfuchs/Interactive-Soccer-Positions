"""ElementRegistry — plug-in point for new visual layers.

Adding a layer:
    1. implement a StaticElement/DynamicElement subclass with from_spec()
       under ``render/static/`` or ``render/dynamic/``
    2. registry.register("MyOverlay", MyOverlay.from_spec)
    3. add a YAML `layers` entry with the desired z_order
"""
from __future__ import annotations

from typing import Callable

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.presets import LayerSpec
from sopovis.render.elements import Element


class ElementRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, Callable[[LayerSpec, PrecomputedBundle], Element]] = {}

    def register(self, type_name: str, factory: Callable) -> None:
        self._factories[type_name] = factory

    def create(self, spec: LayerSpec, bundle: PrecomputedBundle) -> Element:
        if spec.type not in self._factories:
            raise KeyError(
                f"unknown element type {spec.type!r}; registered: {sorted(self._factories)}"
            )
        return self._factories[spec.type](spec, bundle)

    @property
    def types(self) -> list[str]:
        return sorted(self._factories)


def default_registry() -> ElementRegistry:
    from sopovis.render import dynamic, static

    registry = ElementRegistry()
    for cls in (
        static.PitchMarkings,
        static.HalfSpaceLines,
        dynamic.ShapeGraphOverlay,
        dynamic.TeamColorGlyph,
        dynamic.ShirtNumberLabel,
        dynamic.BallGlyph,
        dynamic.DefensiveLineOverlay,
        dynamic.VelocityArrow,
    ):
        registry.register(cls.__name__, cls.from_spec)
    return registry
