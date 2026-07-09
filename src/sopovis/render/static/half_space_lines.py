"""Half-space zone boundary lines."""
from __future__ import annotations

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.presets import LayerSpec
from sopovis.render.common import meta_from_spec
from sopovis.render.elements import ElementMeta, StaticElement


class HalfSpaceLines(StaticElement):
    """Dashed lateral zone boundaries (half-spaces) along the pitch length."""

    def __init__(self, meta: ElementMeta, color="#ffffff", opacity=0.25):
        super().__init__(meta)
        self.color = color
        self.opacity = opacity

    @classmethod
    def from_spec(cls, spec: LayerSpec, bundle: PrecomputedBundle) -> "HalfSpaceLines":
        return cls(meta_from_spec(spec), **spec.style)

    def _build(self, ax, bundle: PrecomputedBundle) -> None:
        width = bundle.meta.pitch_y
        for frac in (0.211, 0.368, 0.632, 0.789):
            line = ax.axhline(
                width * frac,
                color=self.color,
                alpha=self.opacity,
                linestyle="--",
                linewidth=0.8,
            )
            self._register(line)
