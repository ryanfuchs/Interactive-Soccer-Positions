"""TimelineControlView — event-annotated timeline, sole writer of FrameCursor.

Owns scrubbing and playback (Play widget + slider + speed). Other views
request seeks via `on_scrub`; they never set the cursor themselves.

Two horizontal lanes — home (upper) and away (lower) — share the same time
axis. Shot icons:
  goal          — filled black dot
  on target     — hollow circle + inner dot
  off target    — hollow circle
"""
from __future__ import annotations

import numpy as np
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.ui.canvas import refresh_figure
from sopovis.ui.cursor import FrameCursor

# marker style per non-shot class: (marker, color, y-offset from lane centre, label)
_EVENT_STYLES = {
    "card": ("s", "#f1c40f", -0.32, "Card"),
    "sub": ("^", "#8d99ae", 0.32, "Substitution"),
    "whistle": ("|", "#222222", 0.0, "Kickoff / Final whistle"),
}

_SHOT_OFFSET = {
    "goal": 0.48,
    "shot_on_goal": 0.0,
    "shot_off": -0.48,
}

# lane centre y in data coordinates (home upper, away lower)
_LANE_CENTRE = {"home": 2.85, "away": 0.85}
_DIVIDER_Y = 1.85
_TIMELINE_BG = "#f7f7f7"
_Y_PAD = 0.18


def _content_ylim() -> tuple[float, float]:
    """Symmetric vertical limits around the two event lanes."""
    centres = _LANE_CENTRE.values()
    event_pad = max(abs(offset) for _, _, offset, _ in _EVENT_STYLES.values())
    shot_pad = max(abs(offset) for offset in _SHOT_OFFSET.values())
    pad = max(event_pad, shot_pad) + _Y_PAD
    lo = min(centres) - pad
    hi = max(centres) + pad
    return lo, hi


def _luminance(hex_color: str) -> float:
    value = hex_color.lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    r, g, b = (int(value[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _team_label_color(main: str, secondary: str, background: str = _TIMELINE_BG) -> str:
    """Pick a team colour that stays readable on the timeline background."""
    bg = _luminance(background)
    for color in (main, secondary, "#333333"):
        if color and abs(_luminance(color) - bg) >= 55:
            return color
    return "#333333"


def _classify(event) -> str | None:
    if event.is_goal:
        return "goal"
    if event.is_shot_on_target:
        return "shot_on_goal"
    if event.is_shot_off_target:
        return "shot_off"
    if event.is_shot:
        return "shot_on_goal"
    base = event.base_type
    if base in ("Caution", "SendingOff"):
        return "card"
    if base in ("Substitution", "OutSubstitution"):
        return "sub"
    if base in ("KickOff", "FinalWhistle"):
        return "whistle"
    return None


def _team_lane(bundle: PrecomputedBundle, team_id: str | None) -> str | None:
    if team_id == bundle.meta.home_team_id:
        return "home"
    if team_id == bundle.meta.guest_team_id:
        return "away"
    return None


def _event_y(bundle: PrecomputedBundle, team_id: str | None, kind: str) -> float | None:
    lane = _team_lane(bundle, team_id)
    if lane is None:
        if kind == "whistle":
            return _DIVIDER_Y
        return None
    centre = _LANE_CENTRE[lane]
    if kind in _SHOT_OFFSET:
        return centre + _SHOT_OFFSET[kind]
    if kind in _EVENT_STYLES:
        return centre + _EVENT_STYLES[kind][2]
    return centre


def _draw_shot_markers(ax, xs: np.ndarray, ys: np.ndarray, kind: str) -> None:
    if len(xs) == 0:
        return
    if kind == "goal":
        ax.plot(
            xs, ys, linestyle="none", marker="o", markersize=5.5,
            markerfacecolor="black", markeredgecolor="black", markeredgewidth=0,
            zorder=6,
        )
        return
    if kind == "shot_off":
        ax.plot(
            xs, ys, linestyle="none", marker="o", markersize=7.0,
            markerfacecolor="white", markeredgecolor="black", markeredgewidth=1.2,
            zorder=6,
        )
        return
    # on target: ring + centred inner dot (plot markersize is diameter in points)
    ax.plot(
        xs, ys, linestyle="none", marker="o", markersize=7.0,
        markerfacecolor="white", markeredgecolor="black", markeredgewidth=1.2,
        zorder=6,
    )
    ax.plot(
        xs, ys, linestyle="none", marker="o", markersize=2.4,
        markerfacecolor="black", markeredgecolor="black", markeredgewidth=0,
        zorder=7,
    )


def _legend_handles(groups: dict[str, list[int]]) -> list[Line2D]:
    handles: list[Line2D] = []
    if groups.get("goal"):
        handles.append(
            Line2D(
                [], [], linestyle="none", marker="o", markersize=6,
                markerfacecolor="black", markeredgecolor="black", label="Goal",
            )
        )
    if groups.get("shot_on_goal"):
        handles.append(
            Line2D(
                [], [], linestyle="none", marker="o", markersize=7,
                markerfacecolor="white", markeredgecolor="black", markeredgewidth=1.2,
                label="Shot on target",
            )
        )
    if groups.get("shot_off"):
        handles.append(
            Line2D(
                [], [], linestyle="none", marker="o", markersize=7,
                markerfacecolor="white", markeredgecolor="black", markeredgewidth=1.2,
                label="Shot",
            )
        )
    return handles


class TimelineControlView:
    def __init__(self, cursor: FrameCursor, bundle: PrecomputedBundle, figure: Figure):
        self.cursor = cursor
        self.bundle = bundle
        self.fig = figure
        self.ax = figure.add_subplot(111)
        self.is_playing = False
        self.speed = 1.0
        self._playhead = None
        self._time_label = None
        self._build()
        self.fig.canvas.mpl_connect("button_press_event", self._on_click)

    # ------------------------------------------------------------- controls

    def on_scrub(self, t: int) -> None:
        """Single entry point for all seeks (slider, clicks, other views)."""
        t = max(0, min(int(t), self.bundle.total_frames - 1))
        self.cursor.set(t)
        self._update_playhead(t)

    def on_speed_change(self, speed: float) -> None:
        self.speed = speed

    def _on_click(self, event) -> None:
        if event.inaxes is self.ax and event.xdata is not None:
            self.on_scrub(int(event.xdata))

    # ------------------------------------------------------------- drawing

    def _build(self) -> None:
        ax, bundle = self.ax, self.bundle
        y_lo, y_hi = _content_ylim()
        ax.set_xlim(0, bundle.total_frames)
        ax.set_ylim(y_lo, y_hi)
        ax.set_yticks([])
        ax.set_facecolor(_TIMELINE_BG)

        for name, (lo, hi) in bundle.section_ranges.items():
            if name == "secondHalf":
                ax.axvline(lo, color="#999999", linewidth=1.0, zorder=1)

        ax.axhline(_DIVIDER_Y, color="#cccccc", linewidth=0.9, zorder=1)

        home_team = bundle.teams[bundle.meta.home_team_id]
        away_team = bundle.teams[bundle.meta.guest_team_id]
        ax.text(
            0.01, _LANE_CENTRE["home"], home_team.team_name,
            transform=ax.get_yaxis_transform(), ha="left", va="center",
            fontsize=7, fontweight="bold",
            color=_team_label_color(home_team.shirt_main_color, home_team.shirt_secondary_color),
            clip_on=False,
        )
        ax.text(
            0.01, _LANE_CENTRE["away"], away_team.team_name,
            transform=ax.get_yaxis_transform(), ha="left", va="center",
            fontsize=7, fontweight="bold",
            color=_team_label_color(away_team.shirt_main_color, away_team.shirt_secondary_color),
            clip_on=False,
        )

        ticks = []
        labels = []
        for name, (lo, hi) in bundle.section_ranges.items():
            offset = 45 * 60 if name == "secondHalf" else 0
            for minute in range(0, int((hi - lo) / bundle.frame_rate / 60) + 1, 15):
                ticks.append(lo + minute * 60 * bundle.frame_rate)
                labels.append(f"{minute + offset // 60}'")
        ax.set_xticks(ticks)
        ax.set_xticklabels(labels, fontsize=7)
        ax.tick_params(axis="x", pad=2)

        # bucket: kind → list of (frame, y)
        buckets: dict[str, list[tuple[int, float]]] = {}
        groups: dict[str, list[int]] = {}
        for ev in bundle.events:
            kind = _classify(ev)
            if kind is None:
                continue
            y = _event_y(bundle, ev.team_id, kind)
            if y is None:
                continue
            buckets.setdefault(kind, []).append((ev.frame_idx, y))
            groups.setdefault(kind, []).append(ev.frame_idx)

        for kind in ("goal", "shot_on_goal", "shot_off"):
            points = buckets.get(kind, [])
            if not points:
                continue
            xs, ys = zip(*points)
            _draw_shot_markers(ax, np.asarray(xs), np.asarray(ys), kind)

        for kind, points in buckets.items():
            if kind in _SHOT_OFFSET:
                continue
            marker, color, _offset, _label = _EVENT_STYLES[kind]
            xs, ys = zip(*points)
            ax.scatter(
                xs, ys, marker=marker, c=color, s=22, zorder=5,
            )

        legend_items = _legend_handles(groups)
        for kind, (_, color, _offset, label) in _EVENT_STYLES.items():
            if kind in groups:
                marker = _EVENT_STYLES[kind][0]
                legend_items.append(
                    Line2D(
                        [], [], linestyle="none", marker=marker, markersize=6,
                        markerfacecolor=color, markeredgecolor=color, label=label,
                    )
                )
        if legend_items:
            self.fig.legend(
                handles=legend_items,
                loc="upper center",
                bbox_to_anchor=(0.5, 0.995),
                ncol=len(legend_items),
                fontsize=6.5,
                frameon=False,
                handlelength=1.2,
                handletextpad=0.35,
                columnspacing=1.4,
                borderaxespad=0.0,
            )

        self._playhead = ax.axvline(0, color="#d00000", linewidth=1.4, zorder=10)
        self._time_label = ax.text(
            0.5, 1.02, "00:00", transform=ax.transAxes,
            ha="center", va="bottom",
            fontsize=9, fontweight="bold", color="#d00000",
        )
        self.fig.subplots_adjust(left=0.09, right=0.995, top=0.78, bottom=0.30)

    def _update_playhead(self, t: int) -> None:
        self._playhead.set_xdata([t, t])
        self._time_label.set_text(self.bundle.clock_label(t))
        refresh_figure(self.fig)
