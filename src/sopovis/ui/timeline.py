"""TimelineControlView — layered event timeline, sole writer of FrameCursor.

Owns scrubbing and playback (Play widget + slider + speed). Other views
request seeks via `on_scrub`; they never set the cursor themselves.

All visuals (possession background, lane furniture, shot / card / sub /
whistle markers, …) are ``TimelineElement`` layers drawn by a
``TimelineStack`` — the timeline analog of the pitch ``SceneRenderer``.
This view only manages the Axes, ticks, playhead, and interactions; layer
construction happens in ``AppController`` via ``TimelineStackBuilder``
(mirroring ``SceneBuilder`` for the pitch).

Hovering a marker shows a tooltip with the event details.
"""
from __future__ import annotations

from typing import Callable

from matplotlib.figure import Figure

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.render.timeline import (
    TIMELINE_BG,
    TimelineElement,
    TimelineStack,
    default_geometry,
)
from sopovis.ui.canvas import refresh_figure
from sopovis.ui.cursor import FrameCursor
from sopovis.ui.hover import TimeHoverLink
from sopovis.ui.span_zoom import SpanZoomInteraction
from sopovis.ui.time_window import ViewTimeRange

_HOVER_RADIUS_PX = 8.0
_TOOLTIP_OFFSET_PT = 10


class TimelineControlView:
    def __init__(
        self,
        cursor: FrameCursor,
        bundle: PrecomputedBundle,
        stack: TimelineStack,
        figure: Figure,
        view_range: ViewTimeRange | None = None,
        min_zoom_seconds: float = 5.0,
        on_span_zoom: Callable[[int, int], None] | None = None,
        on_span_reset: Callable[[], None] | None = None,
    ):
        self.cursor = cursor
        self.bundle = bundle
        self.stack = stack
        self.fig = figure
        self.ax = figure.add_subplot(111)
        self.view_range = view_range or ViewTimeRange(bundle)
        self.is_playing = False
        self.speed = 1.0
        self._geom = default_geometry()
        self._playhead = None
        self._time_label = None
        self._tooltip = None
        self._time_hover: TimeHoverLink | None = None
        self._hover_line = None
        self._build()
        min_frames = max(1, int(min_zoom_seconds * bundle.frame_rate))
        self._span_zoom = SpanZoomInteraction(
            self.ax,
            on_zoom=on_span_zoom or (lambda _a, _b: None),
            on_click=self.on_scrub,
            on_reset=on_span_reset or (lambda: None),
            y_limits=(self._geom.y_lo, self._geom.y_hi),
            min_span_frames=min_frames,
        )
        self._span_zoom.connect(self.fig)
        self.fig.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self.fig.canvas.mpl_connect("axes_leave_event", self._on_axes_leave)

    # ------------------------------------------------------------- controls

    def on_scrub(self, t: int) -> None:
        """Single entry point for all seeks (slider, clicks, other views)."""
        t0, t1 = self.time_window()
        t = max(t0, min(int(t), t1 - 1))
        self.cursor.set(t)
        self._update_playhead(t)

    def on_speed_change(self, speed: float) -> None:
        self.speed = speed

    def set_period(self, period: str | None) -> None:
        self._build()
        self.on_scrub(self.cursor.t)

    def bind_time_hover(self, time_hover: TimeHoverLink) -> None:
        self._time_hover = time_hover
        time_hover.subscribe(self._on_time_hover_change)

    def time_window(self) -> tuple[int, int]:
        return self.view_range.limits()

    def apply_view_range(self) -> None:
        t0, t1 = self.view_range.limits()
        self.ax.set_xlim(t0, t1)
        refresh_figure(self.fig)

    # ---------------------------------------------------------------- layers

    @property
    def elements(self) -> list[TimelineElement]:
        return self.stack.elements

    def get(self, name: str) -> TimelineElement | None:
        return self.stack.get(name)

    def set_stack(self, stack: TimelineStack) -> None:
        """Swap the layer stack (preset change) and rebuild."""
        self.stack = stack
        self._build()
        refresh_figure(self.fig)

    def set_layer_enabled(self, name: str, enabled: bool) -> None:
        self.stack.set_enabled(name, enabled)
        self._build()
        refresh_figure(self.fig)

    # ---------------------------------------------------------- interaction

    def _on_motion(self, event) -> None:
        if event.inaxes is not self.ax:
            if self._time_hover is not None:
                self._time_hover.set(None)
            self._hide_tooltip()
            return
        if self._time_hover is not None and event.xdata is not None:
            self._time_hover.set(int(round(event.xdata)))
        target = self._find_hover_target(event)
        if target is None:
            self._hide_tooltip()
            return
        x, y, lines = target
        self._show_tooltip(x, y, lines)

    def _on_axes_leave(self, event) -> None:
        if event.inaxes is self.ax:
            if self._time_hover is not None:
                self._time_hover.set(None)
            self._hide_tooltip()

    def _on_time_hover_change(self, frame: int | None) -> None:
        if self._hover_line is None:
            return
        if frame is None:
            self._hover_line.set_visible(False)
        else:
            self._hover_line.set_xdata([frame, frame])
            self._hover_line.set_visible(True)
        refresh_figure(self.fig)

    def _find_hover_target(self, event) -> tuple[float, float, list[str]] | None:
        best = None
        best_d2 = _HOVER_RADIUS_PX**2
        trans = self.ax.transData
        for el in reversed(self.elements):  # top-most layer wins
            if not el.meta.enabled:
                continue
            for x, y, lines in el.hover_targets():
                px, py = trans.transform((x, y))
                d2 = (px - event.x) ** 2 + (py - event.y) ** 2
                if d2 < best_d2:
                    best_d2 = d2
                    best = (x, y, lines)
        return best

    def _show_tooltip(self, x: float, y: float, lines: list[str]) -> None:
        if self._tooltip is None:
            return
        # Flip away from the strip edges so the box stays visible.
        t0, t1 = self.time_window()
        near_right = (x - t0) > 0.7 * max(t1 - t0, 1)
        near_top = y > (self._geom.y_lo + 0.6 * (self._geom.y_hi - self._geom.y_lo))
        dx = -_TOOLTIP_OFFSET_PT if near_right else _TOOLTIP_OFFSET_PT
        dy = -_TOOLTIP_OFFSET_PT if near_top else _TOOLTIP_OFFSET_PT
        self._tooltip.xy = (x, y)
        self._tooltip.set_position((dx, dy))
        self._tooltip.set_ha("right" if near_right else "left")
        self._tooltip.set_va("top" if near_top else "bottom")
        self._tooltip.set_text("\n".join(lines))
        self._tooltip.set_visible(True)
        refresh_figure(self.fig)

    def _hide_tooltip(self) -> None:
        if self._tooltip is not None and self._tooltip.get_visible():
            self._tooltip.set_visible(False)
            refresh_figure(self.fig)

    # ------------------------------------------------------------- drawing

    def _build(self) -> None:
        ax, bundle = self.ax, self.bundle
        ax.clear()
        self._playhead = None
        self._time_label = None
        self._tooltip = None
        self._hover_line = None
        t0, t1 = self.time_window()
        ax.set_xlim(t0, t1)
        ax.set_ylim(self._geom.y_lo, self._geom.y_hi)
        ax.set_yticks([])
        ax.set_facecolor(TIMELINE_BG)

        self.stack.build(ax, bundle, self._geom)

        ticks = []
        labels = []
        for name, (lo, hi) in bundle.section_ranges.items():
            if hi <= t0 or lo >= t1:
                continue
            offset = 45 * 60 if name == "secondHalf" else 0
            if name == "firstHalfExtra":
                offset = 90 * 60
            elif name == "secondHalfExtra":
                offset = 105 * 60
            span_lo = max(lo, t0)
            span_hi = min(hi, t1)
            for minute in range(0, int((hi - lo) / bundle.frame_rate / 60) + 1, 15):
                tick = lo + minute * 60 * bundle.frame_rate
                if span_lo <= tick <= span_hi:
                    ticks.append(tick)
                    labels.append(f"{minute + offset // 60}'")
        ax.set_xticks(ticks)
        ax.set_xticklabels(labels, fontsize=7)
        ax.tick_params(axis="x", pad=2)

        self._playhead = ax.axvline(self.cursor.t, color="#d00000", linewidth=1.4, zorder=100)
        hover_frame = self._time_hover.frame if self._time_hover is not None else None
        self._hover_line = ax.axvline(
            hover_frame if hover_frame is not None else self.cursor.t,
            color="#0077cc",
            linewidth=1.0,
            linestyle="--",
            alpha=0.9,
            zorder=110,
            visible=hover_frame is not None,
        )
        self._time_label = ax.text(
            0.5, 1.02, bundle.clock_label(self.cursor.t), transform=ax.transAxes,
            ha="center", va="bottom",
            fontsize=9, fontweight="bold", color="#d00000",
        )
        self._tooltip = ax.annotate(
            "",
            xy=(0, 0),
            xytext=(_TOOLTIP_OFFSET_PT, _TOOLTIP_OFFSET_PT),
            textcoords="offset points",
            ha="left",
            va="bottom",
            fontsize=7,
            color="#111111",
            bbox={
                "boxstyle": "round,pad=0.35",
                "facecolor": "#ffffe8",
                "edgecolor": "#888888",
                "linewidth": 0.8,
                "alpha": 0.95,
            },
            zorder=300,
            visible=False,
            clip_on=False,
            annotation_clip=False,
        )
        # Symmetric margins keep the strip centred — no y labels, team names
        # are drawn inside the axes.
        self.fig.subplots_adjust(left=0.015, right=0.985, top=0.88, bottom=0.28)

    def _update_playhead(self, t: int) -> None:
        self._playhead.set_xdata([t, t])
        self._time_label.set_text(self.bundle.clock_label(t))
        refresh_figure(self.fig)
