"""Substitution vertical markers."""
from __future__ import annotations

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.presets import LayerSpec
from sopovis.render.common import meta_from_spec
from sopovis.render.elements import ElementMeta
from sopovis.render.position.context import PositionContext
from sopovis.render.position.elements import PositionElement


class SubstitutionMarkers(PositionElement):
    """Faint vlines at substitution frames (bolded on row hover by the view)."""

    def __init__(
        self,
        meta: ElementMeta,
        color: str = "#555555",
        linewidth: float = 0.6,
        alpha: float = 0.6,
    ):
        super().__init__(meta)
        self.color = color
        self.linewidth = linewidth
        self.alpha = alpha

    @classmethod
    def from_spec(cls, spec: LayerSpec, bundle: PrecomputedBundle) -> "SubstitutionMarkers":
        return cls(meta_from_spec(spec), **spec.style)

    def build(self, ax, bundle: PrecomputedBundle, ctx: PositionContext) -> None:
        self.reset()
        ctx.sub_lines.clear()
        sub_frames: set[int] = set()
        for ta in bundle.substitution_frames[1:-1]:
            sub_frames.add(int(bundle.analytics_frame_indices[ta]))
        for ev in bundle.events:
            if "Substitution" in ev.event_type:
                sub_frames.add(int(ev.frame_idx))
        for t in sorted(sub_frames):
            if ctx.t0 <= t < ctx.t1:
                line = ax.axvline(
                    t,
                    color=self.color,
                    linewidth=self.linewidth,
                    alpha=self.alpha,
                    zorder=self.meta.z_order,
                )
                self._register(line)
                ctx.sub_lines[t] = line
