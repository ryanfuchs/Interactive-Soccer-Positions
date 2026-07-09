"""PitchAnimationView — spatial snapshot at the current frame.

Read-only subscriber of FrameCursor. All drawing is delegated to the
config-driven SceneRenderer; this view only manages the Axes, the
clock title, and scene swaps on preset change.

Hovering a player highlights their tactical row in the position plot.
"""
from __future__ import annotations

import numpy as np
from matplotlib.figure import Figure

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.render.scene import SceneRenderer
from sopovis.ui.canvas import refresh_figure
from sopovis.ui.cursor import FrameCursor
from sopovis.ui.hover import HoverLink

_PICK_RADIUS_M = 4.0


class PitchAnimationView:
    def __init__(
        self,
        cursor: FrameCursor,
        bundle: PrecomputedBundle,
        scene: SceneRenderer,
        figure: Figure,
    ):
        self.cursor = cursor
        self.bundle = bundle
        self.scene = scene
        self.fig = figure
        self.ax = figure.add_subplot(111)
        self._hover: HoverLink | None = None
        self._highlight = None
        self.draw(cursor.t)
        self.fig.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self.fig.canvas.mpl_connect("axes_leave_event", self._on_axes_leave)

    def bind_hover(self, hover: HoverLink) -> None:
        self._hover = hover
        hover.subscribe(self._on_hover_change)

    def on_cursor_change(self, t: int) -> None:
        self.draw(t)

    def draw(self, t: int) -> None:
        self.scene.draw(self.ax, self.bundle, t)
        self.ax.set_title(
            f"{self.bundle.meta.home_team_name} {self.bundle.meta.result} "
            f"{self.bundle.meta.guest_team_name}   {self.bundle.clock_label(t)}",
            fontsize=9,
        )
        self._update_highlight(t)
        refresh_figure(self.fig, force=True)

    def set_scene(self, scene: SceneRenderer) -> None:
        """Swap the layer stack (preset change) and redraw at the current frame."""
        self.ax.clear()
        self.scene = scene
        self.scene.invalidate_static()
        self._highlight = None
        self.draw(self.cursor.t)

    def toggle_layer(self, name: str, enabled: bool) -> None:
        self.scene.set_enabled(name, enabled)
        self.draw(self.cursor.t)

    def _on_motion(self, event) -> None:
        if self._hover is None:
            return
        if event.inaxes is not self.ax or event.xdata is None or event.ydata is None:
            self._hover.set(None)
            return
        self._hover.set(self._pick_player(float(event.xdata), float(event.ydata), self.cursor.t))

    def _on_axes_leave(self, event) -> None:
        if self._hover is not None and event.inaxes is self.ax:
            self._hover.set(None)

    def _on_hover_change(self, _person_id: str | None) -> None:
        self._update_highlight(self.cursor.t)
        refresh_figure(self.fig, force=True)

    def _pick_player(self, x: float, y: float, t: int) -> str | None:
        best_col: int | None = None
        best_d2 = _PICK_RADIUS_M**2
        for c, pid in enumerate(self.bundle.player_ids):
            px, py = self.bundle.frames[t, c, :2]
            if not np.isfinite(px):
                continue
            d2 = (px - x) ** 2 + (py - y) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best_col = c
        if best_col is None:
            return None
        return self.bundle.player_ids[best_col]

    def _update_highlight(self, t: int) -> None:
        person_id = self._hover.person_id if self._hover is not None else None
        if person_id is None:
            if self._highlight is not None:
                self._highlight.set_visible(False)
            return

        if self._highlight is None:
            self._highlight = self.ax.scatter(
                [],
                [],
                s=260,
                facecolors="none",
                edgecolors="#FF8F00",
                linewidths=2.4,
                zorder=90,
            )

        col = self.bundle.player_index.get(person_id)
        if col is None:
            self._highlight.set_visible(False)
            return
        x, y = self.bundle.frames[t, col, :2]
        if not np.isfinite(x):
            self._highlight.set_visible(False)
            return
        self._highlight.set_offsets([[x, y]])
        self._highlight.set_visible(True)
