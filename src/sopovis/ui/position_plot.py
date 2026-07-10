"""PositionPlotView — time × player-row heatmap of tactical roles.

Each player band has two stacked halves: upper = depth role color (F…B),
lower = lateral role color (L…R), with a thin blank gap between players.
Aggregation picks the role with the largest role_counts delta over each
time bin. Bins can be blanked when the ball is out of play or when
possession does not match the active filter.

When both teams are shown they stack to match the vertical pitch
(``home_at_bottom``): the top block is the team at the top of the pitch.
Lateral colours are mirrored on one side and row order is reversed so the
two blocks face each other (attackers toward the middle).

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
from sopovis.ui.span_zoom import SpanZoomInteraction
from sopovis.ui.time_window import ViewTimeRange
from sopovis.ui.tooltips import PlayerTooltip, PlayerTooltipConfig, row_mates, substitution_frames

_TEAM_GAP_ROWS = 1  # blank image rows between team blocks
_PLAYER_BAND = 2  # depth + lateral colour strips
_PLAYER_GAP = 1  # blank image rows between players
_BIN_VISIBLE_FRAC = 0.5  # min fraction of frames in bin that must pass filters

# possession filter values (match ball_possession codes; None = no filter)
POSSESSION_ALL = "all"
POSSESSION_HOME = "home"  # code 1
POSSESSION_AWAY = "away"  # code 2
POSSESSION_CONTESTED = "contested"  # code 0 (unknown / contested)


class PositionPlotView:
    def __init__(
        self,
        cursor: FrameCursor,
        bundle: PrecomputedBundle,
        figure: Figure,
        resolution: int = 150,  # bin width in analytics frames (≈30 s at stride 5)
        team_focus: str = "both",  # "home" | "away" | "both"
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
        self._tooltip_config = tooltip_config or PlayerTooltipConfig()
        self._tooltip: PlayerTooltip | None = None
        self._playhead = None
        self._row_bands: list[dict] = []
        self._highlight: Rectangle | None = None
        self._sub_lines: dict[int, object] = {}  # tracking frame → axvline
        self._local_hover = False  # True while pointer is over this axes
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

    def on_cursor_change(self, t: int) -> None:
        if self._playhead is not None:
            self._playhead.set_xdata([t, t])
        if self._local_hover and self._hover is not None and self._hover.person_id:
            self._update_tooltip(self._hover.person_id)
        refresh_figure(self.fig)

    def _on_motion(self, event) -> None:
        if self._hover is None:
            return
        if event.inaxes is not self.ax or event.ydata is None:
            if self._local_hover:
                self._local_hover = False
                self._hover.set(None)
            return
        self._local_hover = True
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
            self._local_hover = False
            self._hover.set(None)

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
            if col in band["cols"]:
                t0, t1 = self.time_window()
                x = min(max(self.cursor.t, t0), t1 - 1)
                y = 0.5 * (band["y0"] + band["y1"])
                related = [self.bundle.player_ids[c] for c in band["cols"]]
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

    # Back-compat alias used by older call sites / tests
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

    def apply_view_range(self) -> None:
        t0, t1 = self.view_range.limits()
        self.ax.set_xlim(t0, t1)
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
        """Inclusive start / exclusive end frame for the visible window."""
        return self.view_range.limits()

    # ------------------------------------------------------------- rendering

    def _frame_mask(self) -> np.ndarray:
        """Boolean mask over tracking frames that pass ball/possession filters."""
        n = self.bundle.total_frames
        mask = np.ones(n, dtype=bool)
        if self.ball_in_play:
            status = self.bundle.ball[:, 3]
            mask &= np.isfinite(status) & (status == 1)
        if self.possession_filter == POSSESSION_HOME:
            mask &= self.bundle.ball_possession == 1
        elif self.possession_filter == POSSESSION_AWAY:
            mask &= self.bundle.ball_possession == 2
        elif self.possession_filter == POSSESSION_CONTESTED:
            mask &= self.bundle.ball_possession == 0
        return mask

    def _bin_visible(self, edges: np.ndarray, frame_mask: np.ndarray) -> np.ndarray:
        """Per-bin visibility from the fraction of tracking frames that pass filters."""
        indices = self.bundle.analytics_frame_indices
        n_bins = len(edges) - 1
        visible = np.ones(n_bins, dtype=bool)
        if not (self.ball_in_play or self.possession_filter != POSSESSION_ALL):
            return visible
        for b in range(n_bins):
            ta0, ta1 = int(edges[b]), int(edges[b + 1])
            t0 = int(indices[ta0])
            t1 = int(indices[min(ta1, len(indices) - 1)])
            if t1 <= t0:
                t1 = min(t0 + 1, self.bundle.total_frames)
            segment = frame_mask[t0:t1]
            if len(segment) == 0 or float(segment.mean()) < _BIN_VISIBLE_FRAC:
                visible[b] = False
        return visible

    def _band_colors(
        self,
        team_id: str,
        edges: np.ndarray,
        bin_visible: np.ndarray,
        *,
        mirror_lateral: bool,
        reverse_rows: bool,
    ) -> tuple[np.ndarray, list[str], list[list[int]]]:
        """RGB image block, row labels, and column lists per band."""
        counts = self.bundle.role_counts
        band_cols: list[list[int]] = []
        labels: list[str] = []
        row_map: dict[int, list[int]] = {}
        for pid, row in self.bundle.player_row_order.items():
            if self.bundle.team_map.get(pid) == team_id:
                row_map.setdefault(row, []).append(self.bundle.player_index[pid])
        row_keys = sorted(row_map)
        if reverse_rows:
            row_keys = list(reversed(row_keys))
        for row in row_keys:
            cols = row_map[row]
            band_cols.append(cols)
            shirts = [
                str(self.bundle.player_registry[self.bundle.player_ids[c]].shirt_number)
                for c in cols
            ]
            labels.append("/".join(shirts))

        n_rows, n_bins = len(band_cols), len(edges) - 1
        row_stride = _PLAYER_BAND + _PLAYER_GAP
        img_h = max(0, n_rows * row_stride - (_PLAYER_GAP if n_rows else 0))
        img = np.ones((img_h, n_bins, 3))
        y_colors = list(reversed(ROLE_COLORS_Y)) if mirror_lateral else ROLE_COLORS_Y
        for r, cols in enumerate(band_cols):
            sel = np.ix_(edges[1:], cols)
            sel_prev = np.ix_(edges[:-1], cols)
            deltas = counts[sel].astype(np.int64) - counts[sel_prev].astype(np.int64)
            total = deltas.sum(axis=(1, 2))
            flat = deltas.sum(axis=1)
            best = flat.argmax(axis=1)
            base = r * row_stride
            for b in range(n_bins):
                if not bin_visible[b] or total[b] == 0:
                    continue
                x_role, y_role = best[b] // 5 - 2, best[b] % 5 - 2
                img[base, b] = to_rgb(ROLE_COLORS_X[x_role + 2])
                img[base + 1, b] = to_rgb(y_colors[y_role + 2])
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
        t0, t1 = self.time_window()
        for band in self._row_bands:
            if col in band["cols"]:
                self._highlight.set_xy((t0, band["y0"]))
                self._highlight.set_width(t1 - t0)
                self._highlight.set_height(band["y1"] - band["y0"])
                self._highlight.set_visible(True)
                return
        self._highlight.set_visible(False)

    def _apply_sub_highlight(self, person_id: str | None) -> None:
        """Bold substitution vlines for the hovered player and their row-mates."""
        active: set[int] = set()
        if person_id is not None:
            for pid in row_mates(self.bundle, person_id):
                active.update(substitution_frames(self.bundle, pid).values())
        for frame, line in self._sub_lines.items():
            if frame in active:
                line.set_color("#111111")
                line.set_linewidth(2.2)
                line.set_alpha(1.0)
                line.set_zorder(7)
            else:
                line.set_color("#555555")
                line.set_linewidth(0.6)
                line.set_alpha(0.6)
                line.set_zorder(2)

    def _redraw_full(self) -> None:
        bundle = self.bundle
        ax = self.ax
        ax.clear()
        self._playhead = None
        self._highlight = None
        self._tooltip = None
        self._row_bands = []
        self._sub_lines = {}

        ta_total = bundle.total_analytics_frames
        n_bins = max(1, ta_total // self.resolution)
        edges = np.linspace(0, ta_total - 1, n_bins + 1).astype(int)
        t0, t1 = self.time_window()
        bin_visible = self._bin_visible(edges, self._frame_mask())

        home, away = bundle.meta.home_team_id, bundle.meta.guest_team_id
        # Top block = team at top of vertical pitch; bottom block faces it.
        blocks: list[tuple[str, bool, bool]] = []
        if self.team_focus == "both":
            if self.home_at_bottom:
                blocks = [
                    (away, True, False),
                    (home, False, True),
                ]
            else:
                blocks = [
                    (home, True, False),
                    (away, False, True),
                ]
        elif self.team_focus == "home":
            blocks = [(home, not self.home_at_bottom, not self.home_at_bottom)]
        else:
            blocks = [(away, self.home_at_bottom, self.home_at_bottom)]

        team_gap = np.ones((_TEAM_GAP_ROWS * (_PLAYER_BAND + _PLAYER_GAP), n_bins, 3))
        parts: list[np.ndarray] = []
        yticks: list[float] = []
        ylabels: list[str] = []
        offset = 0.0
        row_stride = _PLAYER_BAND + _PLAYER_GAP
        for i, (tid, reverse_rows, mirror_lateral) in enumerate(blocks):
            img, labels, band_cols = self._band_colors(
                tid, edges, bin_visible,
                mirror_lateral=mirror_lateral, reverse_rows=reverse_rows,
            )
            if i > 0:
                parts.append(team_gap)
                offset += team_gap.shape[0]
            parts.append(img)
            for r, (label, cols) in enumerate(zip(labels, band_cols)):
                y0 = offset + r * row_stride
                y1 = y0 + _PLAYER_BAND
                self._row_bands.append({"y0": y0, "y1": y1, "cols": cols})
                yticks.append(y0 + _PLAYER_BAND / 2.0)
                ylabels.append(label)
            offset += img.shape[0]

        stacked = np.concatenate(parts, axis=0) if parts else np.ones((1, n_bins, 3))
        ax.imshow(
            stacked,
            aspect="auto",
            interpolation="nearest",
            extent=(0, bundle.total_frames, stacked.shape[0], 0),
        )
        ax.set_xlim(t0, t1)
        ax.set_yticks(yticks)
        ax.set_yticklabels(ylabels, fontsize=6)
        ax.set_xticks([])

        sub_frames: set[int] = set()
        for ta in bundle.substitution_frames[1:-1]:
            sub_frames.add(int(bundle.analytics_frame_indices[ta]))
        for ev in bundle.events:
            if "Substitution" in ev.event_type:
                sub_frames.add(int(ev.frame_idx))
        for t in sorted(sub_frames):
            if t0 <= t < t1:
                line = ax.axvline(t, color="#555555", linewidth=0.6, alpha=0.6, zorder=2)
                self._sub_lines[t] = line

        for _name, (lo, _hi) in bundle.section_ranges.items():
            if t0 < lo < t1:
                ax.axvline(lo, color="#000000", linewidth=1.0)

        self._playhead = ax.axvline(self.cursor.t, color="#d00000", linewidth=1.2, zorder=8)
        self._highlight = Rectangle(
            (t0, 0),
            t1 - t0,
            _PLAYER_BAND,
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
            f"Tactical positions (bin ≈ {self.resolution_seconds:.0f}s)", fontsize=8
        )
        self.fig.tight_layout()
        if self._hover is not None:
            self._apply_row_highlight(self._hover.person_id)
            self._apply_sub_highlight(self._hover.person_id)
            if self._local_hover and self._hover.person_id:
                self._update_tooltip(self._hover.person_id)
        refresh_figure(self.fig)


def _active_column(bundle: PrecomputedBundle, cols: list[int], t: int) -> int | None:
    """Column of the player on pitch in this band at frame t."""
    for c in cols:
        xy = bundle.frames[t, c, :2]
        if np.isfinite(xy).all():
            return c
    return cols[0] if cols else None
