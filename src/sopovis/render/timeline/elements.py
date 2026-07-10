"""Timeline element interface — one visual layer on the event strip."""
from __future__ import annotations

from abc import ABC, abstractmethod

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.render.elements import ElementMeta
from sopovis.render.timeline.geometry import TimelineGeometry

HoverTarget = tuple[float, float, list[str]]  # (frame x, data y, tooltip lines)


class TimelineElement(ABC):
    """One visual layer of the timeline. Rebuilt whenever the strip redraws."""

    def __init__(self, meta: ElementMeta):
        self.meta = meta
        self._artists: list = []
        self._hover_targets: list[HoverTarget] = []

    @abstractmethod
    def build(self, ax, bundle: PrecomputedBundle, geom: TimelineGeometry) -> None: ...

    def hover_targets(self) -> list[HoverTarget]:
        return self._hover_targets

    def reset(self) -> None:
        """Drop artists and hover targets (called when the layer is not drawn)."""
        self._artists.clear()
        self._hover_targets.clear()

    def _register(self, *artists) -> None:
        for a in artists:
            a.set_zorder(self.meta.z_order)
            self._artists.append(a)
