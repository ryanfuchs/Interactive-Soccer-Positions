"""Goal / on-target / off-target shot icons."""
from __future__ import annotations

import numpy as np

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.presets import LayerSpec
from sopovis.render.common import meta_from_spec
from sopovis.render.elements import ElementMeta
from sopovis.render.sizes import TIMELINE_INNER_DOT_PT, TIMELINE_MARKER_PT
from sopovis.render.timeline.elements import TimelineElement
from sopovis.render.timeline.events import format_event, iter_events
from sopovis.render.timeline.geometry import TimelineGeometry


class ShotMarkers(TimelineElement):
    """Goal / on-target / off-target shot icons in the shooting team's lane."""

    def __init__(self, meta: ElementMeta, team="both"):
        super().__init__(meta)
        self.team = team

    @classmethod
    def from_spec(cls, spec: LayerSpec, bundle: PrecomputedBundle) -> "ShotMarkers":
        return cls(meta_from_spec(spec), **spec.style)

    def build(self, ax, bundle: PrecomputedBundle, geom: TimelineGeometry) -> None:
        self.reset()
        entries = iter_events(bundle, {"goal", "shot_on_goal", "shot_off"}, self.team)
        by_kind: dict[str, list[tuple[int, float]]] = {}
        for ev, kind, y in entries:
            by_kind.setdefault(kind, []).append((ev.frame_idx, y))
            self._hover_targets.append((float(ev.frame_idx), y, format_event(bundle, ev, kind)))

        for kind, points in by_kind.items():
            xs, ys = np.asarray([p[0] for p in points]), np.asarray([p[1] for p in points])
            if kind == "goal":
                (a,) = ax.plot(
                    xs,
                    ys,
                    linestyle="none",
                    marker="o",
                    markersize=TIMELINE_MARKER_PT,
                    markerfacecolor="black",
                    markeredgecolor="black",
                    markeredgewidth=0,
                )
                self._register(a)
            elif kind == "shot_off":
                (a,) = ax.plot(
                    xs,
                    ys,
                    linestyle="none",
                    marker="o",
                    markersize=TIMELINE_MARKER_PT,
                    markerfacecolor="white",
                    markeredgecolor="black",
                    markeredgewidth=1.2,
                )
                self._register(a)
            else:  # on target: ring + inner dot
                (ring,) = ax.plot(
                    xs,
                    ys,
                    linestyle="none",
                    marker="o",
                    markersize=TIMELINE_MARKER_PT,
                    markerfacecolor="white",
                    markeredgecolor="black",
                    markeredgewidth=1.2,
                )
                (dot,) = ax.plot(
                    xs,
                    ys,
                    linestyle="none",
                    marker="o",
                    markersize=TIMELINE_INNER_DOT_PT,
                    markerfacecolor="black",
                    markeredgecolor="black",
                    markeredgewidth=0,
                )
                self._register(ring, dot)
