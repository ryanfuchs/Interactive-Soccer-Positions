"""TimelineElementRegistry — plug-in point for new timeline layers.

Adding a layer:
    1. implement a ``TimelineElement`` subclass with ``from_spec()``
       under ``render/timeline/``
    2. registry.register("MyTimelineLayer", MyTimelineLayer.from_spec)
    3. add a YAML ``timeline:`` entry with the desired ``z_order``
"""
from __future__ import annotations

from typing import Callable

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.presets import LayerSpec
from sopovis.render.timeline.elements import TimelineElement


class TimelineElementRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, Callable[[LayerSpec, PrecomputedBundle], TimelineElement]] = {}

    def register(self, type_name: str, factory: Callable) -> None:
        self._factories[type_name] = factory

    def create(self, spec: LayerSpec, bundle: PrecomputedBundle) -> TimelineElement:
        if spec.type not in self._factories:
            raise KeyError(
                f"unknown timeline element type {spec.type!r}; "
                f"registered: {sorted(self._factories)}"
            )
        return self._factories[spec.type](spec, bundle)

    @property
    def types(self) -> list[str]:
        return sorted(self._factories)


def default_timeline_registry() -> TimelineElementRegistry:
    from sopovis.render import timeline

    registry = TimelineElementRegistry()
    for cls in (
        timeline.PossessionChart,
        timeline.LaneFurniture,
        timeline.SectionBoundaries,
        timeline.ShotMarkers,
        timeline.EventMarkers,
    ):
        registry.register(cls.__name__, cls.from_spec)
    return registry
