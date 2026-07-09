"""Metadata model — parsed from DFL 02_01 matchinformation files."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class PlayerMeta:
    person_id: str
    shirt_number: int
    first_name: str
    last_name: str
    short_name: str
    team_id: str
    role: str  # "home" | "guest"
    playing_position: str | None
    starting: bool
    team_leader: bool

    @property
    def is_goalkeeper(self) -> bool:
        return self.playing_position == "TW"


@dataclass(frozen=True)
class TeamMeta:
    team_id: str
    team_name: str
    role: str  # "home" | "guest"
    shirt_main_color: str
    shirt_secondary_color: str
    shirt_number_color: str
    lineup: str
    players: list[PlayerMeta] = field(default_factory=list)

    @property
    def starting_xi(self) -> list[PlayerMeta]:
        return [p for p in self.players if p.starting]


@dataclass(frozen=True)
class MatchMeta:
    match_id: str
    competition_id: str
    competition_name: str
    season: str
    match_day: int
    home_team_id: str
    guest_team_id: str
    home_team_name: str
    guest_team_name: str
    kickoff_time: datetime | None
    result: str
    pitch_x: float
    pitch_y: float
    stadium_name: str
    total_time_first_half: int  # milliseconds
    total_time_second_half: int


@dataclass(frozen=True)
class MatchInformation:
    meta: MatchMeta
    teams: dict[str, TeamMeta]  # team_id → TeamMeta
    player_registry: dict[str, PlayerMeta]  # person_id → PlayerMeta
    team_by_role: dict[str, TeamMeta]  # "home" / "guest" → TeamMeta
