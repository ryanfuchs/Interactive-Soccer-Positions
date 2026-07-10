"""Element interface — static/dynamic taxonomy.

Elements draw onto a matplotlib Axes. `meta.z_order` is forwarded to artist
zorder so stacking is controlled by config, not draw-call order. Elements
keep references to their artists, which makes enable/disable toggles cheap
(visibility flip) and lets dynamic elements update artist data in place
instead of rebuilding — required for smooth scrubbing in interactive figures.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from sopovis.bundle.bundle import PrecomputedBundle


@dataclass
class ElementMeta:
    name: str  # unique id, e.g. "shape_graph"
    z_order: int  # lower = drawn first (background)
    display_name: str | None = None  # UI label; falls back to title-cased name
    category: str | None = None  # optional UI grouping
    enabled: bool = True

    def ui_label(self) -> str:
        if self.display_name:
            return self.display_name
        return self.name.replace("_", " ").title()


class Element(ABC):
    meta: ElementMeta

    def __init__(self, meta: ElementMeta):
        self.meta = meta
        self._artists: list = []

    @abstractmethod
    def draw(self, ax, bundle: PrecomputedBundle, t: int) -> None: ...

    def _set_visible(self, visible: bool) -> None:
        for artist in self._artists:
            artist.set_visible(visible)

    def _register(self, *artists) -> None:
        for a in artists:
            a.set_zorder(self.meta.z_order)
            self._artists.append(a)


class StaticElement(Element, ABC):
    """Built once on first draw; ignores t. invalidate() forces rebuild."""

    def __init__(self, meta: ElementMeta):
        super().__init__(meta)
        self._built = False

    @abstractmethod
    def _build(self, ax, bundle: PrecomputedBundle) -> None: ...

    def draw(self, ax, bundle: PrecomputedBundle, t: int) -> None:
        if not self.meta.enabled:
            self._set_visible(False)
            return
        if not self._built:
            self._build(ax, bundle)
            self._built = True
        self._set_visible(True)

    def invalidate(self) -> None:
        for artist in self._artists:
            try:
                artist.remove()
            except (ValueError, NotImplementedError):
                pass
        self._artists.clear()
        self._built = False


class DynamicElement(Element, ABC):
    """Updates artist data from bundle[t] on every call."""

    @abstractmethod
    def _draw(self, ax, bundle: PrecomputedBundle, t: int) -> None: ...

    def draw(self, ax, bundle: PrecomputedBundle, t: int) -> None:
        if not self.meta.enabled:
            self._set_visible(False)
            return
        self._draw(ax, bundle, t)
        self._set_visible(True)
