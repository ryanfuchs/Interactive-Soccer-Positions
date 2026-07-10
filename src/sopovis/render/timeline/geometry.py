"""Vertical band layout for the timeline strip."""
from __future__ import annotations

from dataclasses import dataclass

from sopovis.bundle.bundle import PrecomputedBundle

LANE_CENTRE = {"home": 2.85, "away": 0.85}
DIVIDER_Y = 1.85
LANE_HALF = 0.66  # half height of one team lane band
TIMELINE_BG = "#f7f7f7"

# marker style per non-shot class: (marker, color, y-offset from lane centre)
EVENT_STYLES = {
    "card": ("s", "#f1c40f", -0.32),
    "sub": ("^", "#8d99ae", 0.32),
    "whistle": ("|", "#222222", 0.0),
}

SHOT_OFFSET = {
    "goal": 0.48,
    "shot_on_goal": 0.0,
    "shot_off": -0.48,
}


@dataclass(frozen=True)
class TimelineGeometry:
    """Vertical band layout of the timeline strip."""

    y_lo: float
    y_hi: float

    def band(self, name: str) -> tuple[float, float]:
        if name == "full":
            return self.y_lo, self.y_hi
        centre = LANE_CENTRE[name]
        return centre - LANE_HALF, centre + LANE_HALF


def default_geometry() -> TimelineGeometry:
    pad = LANE_HALF
    return TimelineGeometry(
        y_lo=min(LANE_CENTRE.values()) - pad,
        y_hi=max(LANE_CENTRE.values()) + pad,
    )


def team_lane(bundle: PrecomputedBundle, team_id: str | None) -> str | None:
    if team_id == bundle.meta.home_team_id:
        return "home"
    if team_id == bundle.meta.guest_team_id:
        return "away"
    return None


def event_y(bundle: PrecomputedBundle, team_id: str | None, kind: str) -> float | None:
    lane = team_lane(bundle, team_id)
    if lane is None:
        return DIVIDER_Y if kind == "whistle" else None
    centre = LANE_CENTRE[lane]
    if kind in SHOT_OFFSET:
        return centre + SHOT_OFFSET[kind]
    if kind in EVENT_STYLES:
        return centre + EVENT_STYLES[kind][2]
    return centre
