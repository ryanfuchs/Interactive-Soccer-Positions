"""Generic marker layer for card / sub / whistle event kinds."""
from __future__ import annotations

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.presets import LayerSpec
from sopovis.render.common import meta_from_spec
from sopovis.render.elements import ElementMeta
from sopovis.render.sizes import TIMELINE_SCATTER_S
from sopovis.render.timeline.elements import TimelineElement
from sopovis.render.timeline.events import format_event, iter_events
from sopovis.render.timeline.geometry import EVENT_STYLES, TimelineGeometry


class EventMarkers(TimelineElement):
    """Generic marker layer for card / sub / whistle event kinds."""

    def __init__(self, meta: ElementMeta, kinds=("card", "sub", "whistle"), team="both"):
        super().__init__(meta)
        self.kinds = tuple(kinds)
        self.team = team

    @classmethod
    def from_spec(cls, spec: LayerSpec, bundle: PrecomputedBundle) -> "EventMarkers":
        return cls(meta_from_spec(spec), **spec.style)

    def build(self, ax, bundle: PrecomputedBundle, geom: TimelineGeometry) -> None:
        self.reset()
        entries = iter_events(bundle, set(self.kinds), self.team)
        by_kind: dict[str, list[tuple[int, float]]] = {}
        for ev, kind, y in entries:
            by_kind.setdefault(kind, []).append((ev.frame_idx, y))
            self._hover_targets.append((float(ev.frame_idx), y, format_event(bundle, ev, kind)))

        for kind, points in by_kind.items():
            marker, color, _offset = EVENT_STYLES[kind]
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            sc = ax.scatter(xs, ys, marker=marker, c=color, s=TIMELINE_SCATTER_S)
            self._register(sc)
