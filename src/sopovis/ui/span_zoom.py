"""Drag-to-zoom interaction for time-based matplotlib axes."""
from __future__ import annotations

from matplotlib.patches import Rectangle

from sopovis.ui.canvas import refresh_figure


class SpanZoomInteraction:
    """Left-drag selects a time span; click without drag seeks; double-click resets.

    Parameters
    ----------
    on_zoom:
        ``(t_start, t_end)`` with *t_end* exclusive (tracking frames).
    on_click:
        Single click / short drag — typically seek to frame *t*.
    on_reset:
        Double-click — typically clear zoom.
    y_limits:
        Vertical extent of the selection rectangle in data coordinates.
    min_span_frames:
        Minimum drag width to count as zoom rather than a click.
    """

    def __init__(
        self,
        ax,
        on_zoom,
        on_click,
        on_reset,
        y_limits: tuple[float, float],
        min_span_frames: int = 1,
    ):
        self.ax = ax
        self.on_zoom = on_zoom
        self.on_click = on_click
        self.on_reset = on_reset
        self.y_lo, self.y_hi = y_limits
        self.min_span_frames = max(1, int(min_span_frames))
        self._press_x: float | None = None
        self._last_x: float | None = None
        self._rect: Rectangle | None = None
        self._dragging = False

    def connect(self, figure) -> None:
        figure.canvas.mpl_connect("button_press_event", self._on_press)
        figure.canvas.mpl_connect("motion_notify_event", self._on_motion)
        figure.canvas.mpl_connect("button_release_event", self._on_release)

    def _clear_rect(self) -> None:
        if self._rect is not None:
            self._rect.remove()
            self._rect = None

    def _on_press(self, event) -> None:
        if event.inaxes is not self.ax or event.button != 1:
            return
        if getattr(event, "dblclick", False):
            self._clear_rect()
            self.on_reset()
            return
        if event.xdata is None:
            return
        self._press_x = float(event.xdata)
        self._last_x = self._press_x
        self._dragging = True
        self._clear_rect()

    def _x_from_event(self, event) -> float | None:
        if event.xdata is not None:
            return float(event.xdata)
        if event.x is None:
            return self._last_x
        bbox = self.ax.bbox
        if bbox.width <= 0:
            return self._last_x
        frac = (event.x - bbox.x0) / bbox.width
        xmin, xmax = self.ax.get_xlim()
        return xmin + frac * (xmax - xmin)

    def _draw_selection(self, x1: float) -> None:
        if self._press_x is None:
            return
        x0, x1 = self._press_x, x1
        lo, hi = min(x0, x1), max(x0, x1)
        y_lo, y_hi = sorted(self.ax.get_ylim())
        self._clear_rect()
        self._rect = Rectangle(
            (lo, y_lo),
            hi - lo,
            y_hi - y_lo,
            facecolor="#4A90D9",
            edgecolor="#215CAF",
            alpha=0.22,
            linewidth=0.8,
            zorder=50,
        )
        self.ax.add_patch(self._rect)
        refresh_figure(self.ax.figure)

    def _on_motion(self, event) -> None:
        if not self._dragging or self._press_x is None:
            return
        x1 = self._x_from_event(event)
        if x1 is None:
            return
        self._last_x = x1
        self._draw_selection(x1)

    def _on_release(self, event) -> None:
        if not self._dragging or self._press_x is None:
            return
        self._dragging = False
        self._clear_rect()
        x1 = self._x_from_event(event)
        x0 = self._press_x
        self._press_x = None
        self._last_x = None
        if x1 is None:
            return
        if abs(x1 - x0) >= self.min_span_frames:
            lo, hi = sorted((int(x0), int(x1)))
            if hi > lo:
                self.on_zoom(lo, hi)
                return
        self.on_click(int(x1))
