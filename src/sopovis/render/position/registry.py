"""PositionElementRegistry — plug-in point for position layers.

Adding a layer:
    1. implement a ``PositionElement`` subclass with ``from_spec()``
       under ``render/position/``
    2. registry.register("MyLayer", MyLayer.from_spec)
    3. add a YAML ``position:`` entry with the desired ``z_order``
"""
from __future__ import annotations

from typing import Callable

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.presets import LayerSpec
from sopovis.render.position.elements import PositionElement


class PositionElementRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, Callable[[LayerSpec, PrecomputedBundle], PositionElement]] = {}

    def register(self, type_name: str, factory: Callable) -> None:
        self._factories[type_name] = factory

    def create(self, spec: LayerSpec, bundle: PrecomputedBundle) -> PositionElement:
        if spec.type not in self._factories:
            raise KeyError(
                f"unknown position element type {spec.type!r}; "
                f"registered: {sorted(self._factories)}"
            )
        return self._factories[spec.type](spec, bundle)

    @property
    def types(self) -> list[str]:
        return sorted(self._factories)


def default_position_registry() -> PositionElementRegistry:
    from sopovis.render import position

    registry = PositionElementRegistry()
    for cls in (
        position.RoleHeatmap,
        position.SubstitutionMarkers,
        position.SectionBoundaries,
        position.RedzonePresence,
    ):
        registry.register(cls.__name__, cls.from_spec)
    return registry
