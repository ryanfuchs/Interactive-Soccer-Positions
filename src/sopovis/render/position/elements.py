"""PositionElement interface — one visual layer on the position plot."""
from __future__ import annotations

from abc import ABC, abstractmethod

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.render.elements import ElementMeta
from sopovis.render.position.context import PositionContext


class PositionElement(ABC):
    """One visual layer of the position view. Rebuilt on full redraw."""

    def __init__(self, meta: ElementMeta):
        self.meta = meta
        self._artists: list = []

    @abstractmethod
    def build(self, ax, bundle: PrecomputedBundle, ctx: PositionContext) -> None: ...

    def reset(self) -> None:
        self._artists.clear()

    def _register(self, *artists) -> None:
        for a in artists:
            a.set_zorder(self.meta.z_order)
            self._artists.append(a)
