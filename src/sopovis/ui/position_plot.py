"""PositionPlotView — time × player-row heatmap of tactical roles.

Each player band has two stacked halves: upper = depth role color (F…B),
lower = lateral role color (L…R). Aggregation picks the role with the
largest role_counts delta over each time bin.

Read-only subscriber of FrameCursor; clicks request a seek via the timeline.
Hovering a row highlights the active player on the pitch (via HoverLink).
"""
from __future__ import annotations

from typing import Callable

import numpy as np
from matplotlib.colors import to_rgb
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

from sopovis.analytics.roles import ROLE_COLORS_X, ROLE_COLORS_Y
from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.ui.canvas import refresh_figure
from sopovis.ui.cursor import FrameCursor
from sopovis.ui.hover import HoverLink

_BLANK = (1.0, 1.0, 1.0)
_GAP_ROWS = 1  # blank bands between team blocks in "both" mode


class PositionPlotView:
    def __init__(
        self,
        cursor: FrameCursor,
        bundle: PrecomputedBundle,
        figure: Figure,
        smoothing: int = 150,  # bin width in analytics frames (≈30 s at stride 5)
        team_focus: str = "both",  # "home" | "away" | "both"
    ):
        self.cursor = cursor
        self.bundle = bundle
        self.fig = figure
        self.ax = figure.add_subplot(111)
        self.smoothing = max(1, smoothing)
        self.team_focus = team_focus
        self.request_seek: Callable[[int], None] = lambda t: None
        self._hover: HoverLink | None = None
        self._playhead = None
        self._row_bands: list[dict] = []
        self._highlight: Rectangle | None = None
        self._redraw_full()
        self.fig.canvas.mpl_connect("button_press_event", self._on_click)
        self.fig.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self.fig.canvas.mpl_connect("axes_leave_event", self._on_axes_leave)

    # ----------------------------------------------------------- interaction

    def bind_hover(self, hover: HoverLink) -> None:
        self._hover = hover
        hover.subscribe(self._on_hover_change)

    def on_cursor_change(self, t: int) -> None:
        if self._playhead is not None:
            self._playhead.set_xdata([t, t])
            refresh_figure(self.fig)

    def _on_click(self, event) -> None:
        if event.inaxes is self.ax and event.xdata is not None:
            self.request_seek(int(event.xdata))

    def _on_motion(self, event) -> None:
        if self._hover is None:
            return
        if event.inaxes is not self.ax or event.ydata is None:
            self._hover.set(None)
            return
        band = self._band_at_y(float(event.ydata))
        if band is None:
            self._hover.set(None)
            return
        col = _active_column(self.bundle, band["cols"], self.cursor.t)
        if col is None:
            self._hover.set(None)
            return
        self._hover.set(self.bundle.player_ids[col])

    def _on_axes_leave(self, event) -> None:
        if self._hover is not None and event.inaxes is self.ax:
            self._hover.set(None)

    def _on_hover_change(self, person_id: str | None) -> None:
        self._apply_row_highlight(person_id)
        refresh_figure(self.fig)

    def set_smoothing(self, smoothing: int) -> None:
        self.smoothing = max(1, int(smoothing))
        self._redraw_full()

    def set_team_focus(self, team_focus: str) -> None:
        self.team_focus = team_focus
        self._redraw_full()

    @property
    def smoothing_seconds(self) -> float:
        return self.smoothing * self.bundle.analytics_stride / self.bundle.frame_rate

    # ------------------------------------------------------------- rendering

    def _band_colors(
        self, team_id: str, edges: np.ndarray
    ) -> tuple[np.ndarray, list[str], list[list[int]]]:
        """RGB image block, row labels, and column lists per band."""
        counts = self.bundle.role_counts
        band_cols: list[list[int]] = []
        labels: list[str] = []
        row_map: dict[int, list[int]] = {}
        for pid, row in self.bundle.player_row_order.items():
            if self.bundle.team_map.get(pid) == team_id:
                row_map.setdefault(row, []).append(self.bundle.player_index[pid])
        for row in sorted(row_map):
            cols = row_map[row]
            band_cols.append(cols)
            shirts = [
                str(self.bundle.player_registry[self.bundle.player_ids[c]].shirt_number)
                for c in cols
            ]
            labels.append("/".join(shirts))

        n_rows, n_bins = len(band_cols), len(edges) - 1
        img = np.ones((n_rows * 2, n_bins, 3))
        for r, cols in enumerate(band_cols):
            sel = np.ix_(edges[1:], cols)
            sel_prev = np.ix_(edges[:-1], cols)
            deltas = counts[sel].astype(np.int64) - counts[sel_prev].astype(np.int64)
            total = deltas.sum(axis=(1, 2))
            flat = deltas.sum(axis=1)
            best = flat.argmax(axis=1)
            for b in range(n_bins):
                if total[b] == 0:
                    continue
                x_role, y_role = best[b] // 5 - 2, best[b] % 5 - 2
                img[r * 2, b] = to_rgb(ROLE_COLORS_X[x_role + 2])
                img[r * 2 + 1, b] = to_rgb(ROLE_COLORS_Y[y_role + 2])
        return img, labels, band_cols

    def _band_at_y(self, y: float) -> dict | None:
        for band in self._row_bands:
            if band["y0"] <= y <= band["y1"]:
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
        for band in self._row_bands:
            if col in band["cols"]:
                self._highlight.set_xy((0, band["y0"]))
                self._highlight.set_width(self.bundle.total_frames)
                self._highlight.set_height(band["y1"] - band["y0"])
                self._highlight.set_visible(True)
                return
        self._highlight.set_visible(False)

    def _redraw_full(self) -> None:
        bundle = self.bundle
        ax = self.ax
        ax.clear()
        self._playhead = None
        self._highlight = None
        self._row_bands = []

        ta_total = bundle.total_analytics_frames
        n_bins = max(1, ta_total // self.smoothing)
        edges = np.linspace(0, ta_total - 1, n_bins + 1).astype(int)

        home, away = bundle.meta.home_team_id, bundle.meta.guest_team_id
        blocks: list[tuple[str, np.ndarray, list[str], list[list[int]]]] = []
        if self.team_focus in ("away", "both"):
            img, labels, band_cols = self._band_colors(away, edges)
            blocks.append((bundle.meta.guest_team_name, img, labels, band_cols))
        if self.team_focus in ("home", "both"):
            img, labels, band_cols = self._band_colors(home, edges)
            blocks.append((bundle.meta.home_team_name, img, labels, band_cols))

        gap = np.ones((_GAP_ROWS * 2, len(edges) - 1, 3))
        parts: list[np.ndarray] = []
        yticks: list[float] = []
        ylabels: list[str] = []
        offset = 0.0
        for i, (_team_name, img, labels, band_cols) in enumerate(blocks):
            if i > 0:
                parts.append(gap)
                offset += gap.shape[0]
            parts.append(img)
            for r, (label, cols) in enumerate(zip(labels, band_cols)):
                y0 = offset + r * 2
                y1 = y0 + 2
                self._row_bands.append({"y0": y0, "y1": y1, "cols": cols})
                yticks.append(y0 + 1.0)
                ylabels.append(label)
            offset += img.shape[0]

        stacked = np.concatenate(parts, axis=0)
        ax.imshow(
            stacked,
            aspect="auto",
            interpolation="nearest",
            extent=(0, bundle.total_frames, stacked.shape[0], 0),
        )
        ax.set_yticks(yticks)
        ax.set_yticklabels(ylabels, fontsize=6)
        ax.set_xticks([])

        for ta in bundle.substitution_frames[1:-1]:
            t = int(bundle.analytics_frame_indices[ta])
            ax.axvline(t, color="#555555", linewidth=0.6, alpha=0.6)

        lo2 = bundle.section_ranges.get("secondHalf", (None,))[0]
        if lo2 is not None:
            ax.axvline(lo2, color="#000000", linewidth=1.0)

        self._playhead = ax.axvline(self.cursor.t, color="#d00000", linewidth=1.2, zorder=8)
        self._highlight = Rectangle(
            (0, 0),
            bundle.total_frames,
            2,
            facecolor="#FFD54F",
            edgecolor="#FF8F00",
            linewidth=1.4,
            alpha=0.38,
            zorder=6,
            visible=False,
        )
        ax.add_patch(self._highlight)
        ax.set_title(
            f"Tactical positions (bin ≈ {self.smoothing_seconds:.0f}s)", fontsize=8
        )
        self.fig.tight_layout()
        if self._hover is not None:
            self._apply_row_highlight(self._hover.person_id)
        refresh_figure(self.fig)


def _active_column(bundle: PrecomputedBundle, cols: list[int], t: int) -> int | None:
    """Column of the player on pitch in this band at frame t."""
    for c in cols:
        xy = bundle.frames[t, c, :2]
        if np.isfinite(xy).all():
            return c
    return cols[0] if cols else None
