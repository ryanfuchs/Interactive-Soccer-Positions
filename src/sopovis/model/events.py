"""Event model — parsed from DFL 03_02 events_raw files."""
from __future__ import annotations

from dataclasses import dataclass, field


#: Event types shown as markers on the timeline.
TIMELINE_EVENT_TYPES = frozenset(
    {
        "KickOff",
        "SuccessfulShot",
        "ShotAtGoal",
        "Substitution",
        "Caution",
        "SendingOff",
        "FinalWhistle",
        "VideoAssistantAction",
        "FreeKick",
        "CornerKick",
        "Penalty",
        "Offside",
        "Foul",
        "OwnGoal",
    }
)


@dataclass(frozen=True)
class EventMoment:
    frame_idx: int
    event_type: str  # e.g. "KickOff", "SuccessfulShot", "Play_Pass"
    player_id: str | None
    team_id: str | None
    x: float | None
    y: float | None
    section: str  # see model.sections.SECTION_ORDER
    raw: dict = field(default_factory=dict, compare=False)

    @property
    def base_type(self) -> str:
        """First component of a compound floodlight eID, e.g. 'KickOff_Play_Pass' → 'KickOff'."""
        return self.event_type.split("_")[0]

    @property
    def is_goal(self) -> bool:
        """Goals appear as 'ShotAtGoal_SuccessfulShot' / 'Penalty_ShotAtGoal_SuccessfulShot'."""
        return "SuccessfulShot" in self.event_type

    @property
    def is_shot(self) -> bool:
        return "ShotAtGoal" in self.event_type

    @property
    def is_shot_on_target(self) -> bool:
        """On-target attempt that did not result in a goal."""
        return self.is_shot and not self.is_goal and any(
            tag in self.event_type
            for tag in ("SavedShot", "BlockedShot", "ShotWoodWork")
        )

    @property
    def is_shot_off_target(self) -> bool:
        return self.is_shot and not self.is_goal and "ShotWide" in self.event_type
