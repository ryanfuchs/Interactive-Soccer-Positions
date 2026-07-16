"""Period boundary vertical lines."""
from __future__ import annotations

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.presets import LayerSpec
from sopovis.render.common import meta_from_spec
from sopovis.render.elements import ElementMeta
from sopovis.render.position.context import PositionContext
from sopovis.render.position.elements import PositionElement


class SectionBoundaries(PositionElement):
    """Vertical lines at period starts (2nd half, extra time, …)."""

    def __init__(self, meta: ElementMeta, color: str = "#000000", linewidth: float = 1.0):
        super().__init__(meta)
        self.color = color
        self.linewidth = linewidth

    @classmethod
    def from_spec(cls, spec: LayerSpec, bundle: PrecomputedBundle) -> "SectionBoundaries":
        return cls(meta_from_spec(spec), **spec.style)

    def build(self, ax, bundle: PrecomputedBundle, ctx: PositionContext) -> None:
        self.reset()
        for _name, (lo, _hi) in bundle.section_ranges.items():
            if ctx.t0 < lo < ctx.t1:
                self._register(
                    ax.axvline(
                        lo,
                        color=self.color,
                        linewidth=self.linewidth,
                        zorder=self.meta.z_order,
                    )
                )
