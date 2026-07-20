"""PitchAnimationView — spatial snapshot at the current frame.

Read-only subscriber of FrameCursor. All drawing is delegated to the
config-driven SceneRenderer; this view only manages the Axes, the
clock title, scene swaps, vertical-pitch orientation, and player tooltips.
"""
from __future__ import annotations

import numpy as np
from matplotlib.figure import Figure

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.render.orientation import to_display_xy, to_tracking_xy
from sopovis.render.scene import SceneRenderer
from sopovis.render.sizes import PLAYER_HIGHLIGHT_S
from sopovis.ui.canvas import refresh_figure
from sopovis.ui.cursor import FrameCursor
from sopovis.ui.hover import HoverLink
from sopovis.ui.tooltips import PlayerTooltip, PlayerTooltipConfig

_PICK_RADIUS_M = 4.0


class PitchAnimationView:
    def __init__(
        self,
        cursor: FrameCursor,
        bundle: PrecomputedBundle,
        scene: SceneRenderer,
        figure: Figure,
        home_at_bottom: bool = True,
        tooltip_config: PlayerTooltipConfig | None = None,
    ):
        self.cursor = cursor
        self.bundle = bundle
        self.scene = scene
        self.fig = figure
        self.ax = figure.add_subplot(111)
        self.home_at_bottom = home_at_bottom
        self._tooltip_config = tooltip_config or PlayerTooltipConfig()
        self._hover: HoverLink | None = None
        self._highlight = None
        self._tooltip: PlayerTooltip | None = None
        self._local_hover = False
        self.draw(cursor.t)
        self.fig.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self.fig.canvas.mpl_connect("axes_leave_event", self._on_axes_leave)

    def bind_hover(self, hover: HoverLink) -> None:
        self._hover = hover
        hover.subscribe(self._on_hover_change)

    def on_cursor_change(self, t: int) -> None:
        self.draw(t)

    def set_home_at_bottom(self, home_at_bottom: bool) -> None:
        if self.home_at_bottom == home_at_bottom:
            return
        self.home_at_bottom = home_at_bottom
        self.draw(self.cursor.t)

    def draw(self, t: int) -> None:
        self.scene.draw(self.ax, self.bundle, t)
        self._apply_orientation()
        # No clock here — the timeline is the single time indicator.
        self.ax.set_title(
            f"{self.bundle.meta.home_team_name} {self.bundle.meta.result} "
            f"{self.bundle.meta.guest_team_name}",
            fontsize=9,
            pad=8,
        )
        self._update_highlight(t)
        if self._local_hover and self._hover is not None and self._hover.person_id:
            self._update_tooltip(self._hover.person_id, t)
        elif self._tooltip is not None and not self._local_hover:
            self._tooltip.hide()
        refresh_figure(self.fig, force=True)

    def set_scene(self, scene: SceneRenderer) -> None:
        """Swap the layer stack (preset change) and redraw at the current frame."""
        self.ax.clear()
        self.scene = scene
        self.scene.invalidate_static()
        self._highlight = None
        self._tooltip = None
        self.draw(self.cursor.t)

    def toggle_layer(self, name: str, enabled: bool) -> None:
        self.scene.set_enabled(name, enabled)
        self.draw(self.cursor.t)

    def _apply_orientation(self) -> None:
        """Keep VerticalPitch data coords; flip ends via axis limits when needed."""
        length, width = self.bundle.meta.pitch_length, self.bundle.meta.pitch_width
        # Goal boxes protrude ~2.4 m beyond each goal line (clip_on=False);
        # pad the y-range so they stay inside the axes, clear of the title.
        pad = 3.5
        if self.home_at_bottom:
            self.ax.set_xlim(0, width)
            self.ax.set_ylim(-pad, length + pad)
        else:
            self.ax.set_xlim(width, 0)
            self.ax.set_ylim(length + pad, -pad)

    def _on_motion(self, event) -> None:
        if self._hover is None:
            return
        if event.inaxes is not self.ax or event.xdata is None or event.ydata is None:
            if self._local_hover:
                self._local_hover = False
                self._hover.set(None)
            return
        self._local_hover = True
        # Artists stay in unflipped display coords; only axis limits invert.
        tx, ty = to_tracking_xy(
            float(event.xdata), float(event.ydata), self.bundle, home_at_bottom=True
        )
        self._hover.set(self._pick_player(tx, ty, self.cursor.t))

    def _on_axes_leave(self, event) -> None:
        if self._hover is not None and event.inaxes is self.ax:
            self._local_hover = False
            self._hover.set(None)

    def _on_hover_change(self, person_id: str | None) -> None:
        self._update_highlight(self.cursor.t)
        if person_id is None or not self._local_hover:
            if self._tooltip is not None:
                self._tooltip.hide()
        else:
            self._update_tooltip(person_id, self.cursor.t)
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

    def _update_tooltip(self, person_id: str, t: int) -> None:
        from sopovis.ui.tooltips import row_mates

        if self._tooltip is None:
            self._tooltip = PlayerTooltip(self.ax, self._tooltip_config)
        col = self.bundle.player_index.get(person_id)
        if col is None:
            self._tooltip.hide()
            return
        x, y = self.bundle.frames[t, col, :2]
        if not np.isfinite(x):
            self._tooltip.hide()
            return
        dx, dy = to_display_xy(x, y, self.bundle, home_at_bottom=True)
        self._tooltip.show_at(
            self.bundle,
            person_id,
            t,
            dx,
            dy,
            related_ids=row_mates(self.bundle, person_id),
        )

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
                s=PLAYER_HIGHLIGHT_S,
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
        dx, dy = to_display_xy(x, y, self.bundle, home_at_bottom=True)
        self._highlight.set_offsets([[dx, dy]])
        self._highlight.set_visible(True)
