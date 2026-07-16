"""PositionPlotView — time × player-row heatmap of tactical roles.

Drawing is delegated to a ``PositionStack`` (see ``sopovis.render.position``).
This view owns the Axes, cursor playhead, row highlight, tooltips, and span-zoom.

Read-only subscriber of FrameCursor; clicks request a seek via the timeline.
Hovering a row highlights the active player on the pitch (via HoverLink).
"""
from __future__ import annotations

from typing import Callable

import numpy as np
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.render.position import (
    PositionContext,
    PositionStack,
    POSSESSION_ALL,
    PLAYER_BAND,
    RowBand,
)
from sopovis.ui.canvas import refresh_figure
from sopovis.ui.cursor import FrameCursor
from sopovis.ui.hover import HoverLink, TimeHoverLink
from sopovis.ui.span_zoom import SpanZoomInteraction
from sopovis.ui.time_window import ViewTimeRange
from sopovis.ui.tooltips import PlayerTooltip, PlayerTooltipConfig, row_mates, substitution_frames

# Re-export possession constants for callers (desktop, tests).
__all__ = ["POSSESSION_ALL", "PositionPlotView"]


class PositionPlotView:
    def __init__(
        self,
        cursor: FrameCursor,
        bundle: PrecomputedBundle,
        stack: PositionStack,
        figure: Figure,
        resolution: int = 150,
        team_focus: str = "both",
        home_at_bottom: bool = True,
        view_range: ViewTimeRange | None = None,
        ball_in_play: bool = False,
        possession_filter: str = POSSESSION_ALL,
        tooltip_config: PlayerTooltipConfig | None = None,
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
        self.resolution = max(1, resolution)
        self.team_focus = team_focus
        self.home_at_bottom = home_at_bottom
        self.ball_in_play = ball_in_play
        self.possession_filter = possession_filter
        self.request_seek: Callable[[int], None] = lambda t: None
        self._hover: HoverLink | None = None
        self._time_hover: TimeHoverLink | None = None
        self._hover_line = None
        self._tooltip_config = tooltip_config or PlayerTooltipConfig()
        self._tooltip: PlayerTooltip | None = None
        self._playhead = None
        self._row_bands: list[RowBand] = []
        self._highlight: Rectangle | None = None
        self._sub_lines: dict[int, object] = {}
        self._local_hover = False
        self._redraw_full()
        min_frames = max(1, int(min_zoom_seconds * bundle.frame_rate))
        self._span_zoom = SpanZoomInteraction(
            self.ax,
            on_zoom=on_span_zoom or (lambda _a, _b: None),
            on_click=self.request_seek,
            on_reset=on_span_reset or (lambda: None),
            y_limits=(0.0, 1.0),
            min_span_frames=min_frames,
        )
        self._span_zoom.connect(self.fig)
        self.fig.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self.fig.canvas.mpl_connect("axes_leave_event", self._on_axes_leave)

    # ----------------------------------------------------------- interaction

    def bind_hover(self, hover: HoverLink) -> None:
        self._hover = hover
        hover.subscribe(self._on_hover_change)

    def bind_time_hover(self, time_hover: TimeHoverLink) -> None:
        self._time_hover = time_hover
        time_hover.subscribe(self._on_time_hover_change)

    def on_cursor_change(self, t: int) -> None:
        if self._playhead is not None:
            self._playhead.set_xdata([t, t])
        if self._local_hover and self._hover is not None and self._hover.person_id:
            self._update_tooltip(self._hover.person_id)
        refresh_figure(self.fig)

    def _on_motion(self, event) -> None:
        if event.inaxes is not self.ax or event.xdata is None:
            if self._time_hover is not None:
                self._time_hover.set(None)
            if self._hover is not None and self._local_hover:
                self._local_hover = False
                self._hover.set(None)
            return
        if self._time_hover is not None:
            self._time_hover.set(int(round(event.xdata)))
        if self._hover is None:
            return
        if event.ydata is None:
            if self._local_hover:
                self._local_hover = False
                self._hover.set(None)
            return
        self._local_hover = True
        band = self._band_at_y(float(event.ydata))
        if band is None:
            self._hover.set(None)
            return
        col = _active_column(self.bundle, band.cols, self.cursor.t)
        if col is None:
            self._hover.set(None)
            return
        self._hover.set(self.bundle.player_ids[col])

    def _on_axes_leave(self, event) -> None:
        if event.inaxes is self.ax:
            if self._time_hover is not None:
                self._time_hover.set(None)
            if self._hover is not None:
                self._local_hover = False
                self._hover.set(None)

    def _on_time_hover_change(self, frame: int | None) -> None:
        if self._hover_line is None:
            return
        if frame is None:
            self._hover_line.set_visible(False)
        else:
            self._hover_line.set_xdata([frame, frame])
            self._hover_line.set_visible(True)
        refresh_figure(self.fig)

    def _on_hover_change(self, person_id: str | None) -> None:
        self._apply_row_highlight(person_id)
        self._apply_sub_highlight(person_id)
        if person_id is None or not self._local_hover:
            if self._tooltip is not None:
                self._tooltip.hide()
        else:
            self._update_tooltip(person_id)
        refresh_figure(self.fig)

    def _update_tooltip(self, person_id: str) -> None:
        if self._tooltip is None:
            return
        col = self.bundle.player_index.get(person_id)
        if col is None:
            self._tooltip.hide()
            return
        for band in self._row_bands:
            if col in band.cols:
                t0, t1 = self.time_window()
                x = min(max(self.cursor.t, t0), t1 - 1)
                y = 0.5 * (band.y0 + band.y1)
                related = [self.bundle.player_ids[c] for c in band.cols]
                self._tooltip.show_at(
                    self.bundle,
                    person_id,
                    self.cursor.t,
                    x,
                    y,
                    related_ids=related,
                )
                return
        self._tooltip.hide()

    def set_resolution(self, resolution: int) -> None:
        self.resolution = max(1, int(resolution))
        self._redraw_full()

    def set_smoothing(self, smoothing: int) -> None:
        self.set_resolution(smoothing)

    @property
    def smoothing(self) -> int:
        return self.resolution

    def set_team_focus(self, team_focus: str) -> None:
        self.team_focus = team_focus
        self._redraw_full()

    def set_home_at_bottom(self, home_at_bottom: bool) -> None:
        if self.home_at_bottom == home_at_bottom:
            return
        self.home_at_bottom = home_at_bottom
        self._redraw_full()

    def set_period(self, period: str | None) -> None:
        self._redraw_full()

    def set_stack(self, stack: PositionStack) -> None:
        self.stack = stack
        self._redraw_full()

    def set_layer_enabled(self, name: str, enabled: bool) -> None:
        self.stack.set_enabled(name, enabled)
        self._redraw_full()

    def apply_view_range(self) -> None:
        t0, t1 = self.view_range.limits()
        self.ax.set_xlim(t0, t1)
        self._draw_minute_axis(t0, t1)
        if self._playhead is not None:
            self._playhead.set_xdata([self.cursor.t, self.cursor.t])
        refresh_figure(self.fig)

    def set_ball_in_play(self, enabled: bool) -> None:
        self.ball_in_play = bool(enabled)
        self._redraw_full()

    def set_possession_filter(self, possession_filter: str) -> None:
        self.possession_filter = possession_filter
        self._redraw_full()

    @property
    def resolution_seconds(self) -> float:
        return self.resolution * self.bundle.analytics_stride / self.bundle.frame_rate

    def time_window(self) -> tuple[int, int]:
        return self.view_range.limits()

    # ------------------------------------------------------------- rendering

    def _position_context(self) -> PositionContext:
        return PositionContext.prepare(
            self.bundle,
            resolution=self.resolution,
            team_focus=self.team_focus,
            home_at_bottom=self.home_at_bottom,
            ball_in_play=self.ball_in_play,
            possession_filter=self.possession_filter,
            time_window=self.time_window(),
        )

    def _band_at_y(self, y: float) -> RowBand | None:
        for band in self._row_bands:
            if band.y0 <= y <= band.y1:
                return band
        return None

    def _apply_row_highlight(self, person_id: str | None) -> None:
        if self._highlight is None:
            return
        if person_id is None:
            self._highlight.set_visible(False)
            return
        col = self.bundle.player_index.get(person_id)
        if col is None:
            self._highlight.set_visible(False)
            return
        t0, t1 = self.time_window()
        for band in self._row_bands:
            if col in band.cols:
                self._highlight.set_xy((t0, band.y0))
                self._highlight.set_width(t1 - t0)
                self._highlight.set_height(band.y1 - band.y0)
                self._highlight.set_visible(True)
                return
        self._highlight.set_visible(False)

    def _apply_sub_highlight(self, person_id: str | None) -> None:
        active: set[int] = set()
        if person_id is not None:
            for pid in row_mates(self.bundle, person_id):
                active.update(substitution_frames(self.bundle, pid).values())
        for frame, line in self._sub_lines.items():
            if frame in active:
                line.set_color("#111111")
                line.set_linewidth(2.2)
                line.set_alpha(1.0)
                line.set_zorder(31)
            else:
                line.set_color("#555555")
                line.set_linewidth(0.6)
                line.set_alpha(0.6)
                line.set_zorder(30)

    def _redraw_full(self) -> None:
        ax = self.ax
        ax.clear()
        self._playhead = None
        self._hover_line = None
        self._highlight = None
        self._tooltip = None
        self._row_bands = []
        self._sub_lines = {}

        ctx = self._position_context()
        self.stack.build(ax, self.bundle, ctx)
        self._row_bands = list(ctx.row_bands)
        self._sub_lines = dict(ctx.sub_lines)

        ax.set_yticks(ctx.yticks)
        ax.set_yticklabels(ctx.ylabels, fontsize=6)
        self._draw_minute_axis(ctx.t0, ctx.t1)

        self._playhead = ax.axvline(self.cursor.t, color="#d00000", linewidth=1.2, zorder=40)
        hover_frame = self._time_hover.frame if self._time_hover is not None else None
        self._hover_line = ax.axvline(
            hover_frame if hover_frame is not None else self.cursor.t,
            color="#0077cc",
            linewidth=1.0,
            linestyle="--",
            alpha=0.9,
            zorder=50,
            visible=hover_frame is not None,
        )
        self._highlight = Rectangle(
            (ctx.t0, 0),
            ctx.t1 - ctx.t0,
            PLAYER_BAND,
            facecolor="#FFD54F",
            edgecolor="#FF8F00",
            linewidth=1.4,
            alpha=0.38,
            zorder=6,
            visible=False,
        )
        ax.add_patch(self._highlight)
        self._tooltip = PlayerTooltip(ax, self._tooltip_config)
        ax.set_title(
            f"Tactical positions (bin ≈ {ctx.resolution_seconds(self.bundle):.0f}s)",
            fontsize=8,
            pad=16,
        )
        self.fig.tight_layout()
        if self._hover is not None:
            self._apply_row_highlight(self._hover.person_id)
            self._apply_sub_highlight(self._hover.person_id)
            if self._local_hover and self._hover.person_id:
                self._update_tooltip(self._hover.person_id)
        refresh_figure(self.fig)

    def _draw_minute_axis(self, t0: int, t1: int) -> None:
        """Match-minute ticks along the top edge (a play-clock timeline)."""
        ticks, labels = self._minute_ticks(t0, t1)
        ax = self.ax
        ax.set_xticks(ticks)
        ax.set_xticklabels(labels, fontsize=6)
        ax.xaxis.set_ticks_position("top")
        ax.xaxis.set_label_position("top")
        ax.tick_params(
            axis="x",
            top=True,
            bottom=False,
            labeltop=True,
            labelbottom=False,
            length=3,
            pad=2,
        )

    def _minute_ticks(self, t0: int, t1: int) -> tuple[list[float], list[str]]:
        fr = self.bundle.frame_rate
        window_minutes = max(1.0, (t1 - t0) / fr / 60.0)
        step = next(
            (s for s in (1, 2, 5, 10, 15, 30) if window_minutes / s <= 10),
            45,
        )
        ticks: list[float] = []
        labels: list[str] = []
        for name, (lo, hi) in self.bundle.section_ranges.items():
            if hi <= t0 or lo >= t1:
                continue
            offset = _SECTION_MINUTE_OFFSET.get(name, 0)
            span_lo = max(lo, t0)
            span_hi = min(hi, t1)
            section_minutes = int((hi - lo) / fr / 60) + 1
            for minute in range(0, section_minutes + 1, step):
                tick = lo + minute * 60 * fr
                if span_lo <= tick <= span_hi:
                    ticks.append(tick)
                    labels.append(f"{minute + offset}'")
        return ticks, labels


_SECTION_MINUTE_OFFSET = {
    "firstHalf": 0,
    "secondHalf": 45,
    "firstHalfExtra": 90,
    "secondHalfExtra": 105,
}


def _active_column(bundle: PrecomputedBundle, cols: list[int], t: int) -> int | None:
    for c in cols:
        xy = bundle.frames[t, c, :2]
        if np.isfinite(xy).all():
            return c
    return cols[0] if cols else None
