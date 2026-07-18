"""MatchState — single time-indexed store.

Coordinate convention: goal-aligned pitch metres (Brandes 2023) — the
longitudinal axis runs through the two goal centers. x is the signed lateral
distance from that axis, x ∈ [−pitch_width/2, pitch_width/2]; y is the
longitudinal distance from the reference goal line, y ∈ [0, pitch_length].
The reference goal is one fixed physical end of the pitch for the whole
match; which team defends it per section is given by the inferred attack
directions. All downstream components (analytics, rendering) use this frame.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from sopovis.model.events import EventMoment
from sopovis.model.meta import MatchMeta, PlayerMeta, TeamMeta

# Channel indices of MatchState.frames last axis
PX, PY, PSPEED, PACCEL, PDIST = 0, 1, 2, 3, 4
# Channel indices of MatchState.ball last axis
BX, BY, BZ, BSTATUS = 0, 1, 2, 3


@dataclass
class MatchState:
    frames: np.ndarray  # (T, N, 5) — x, y, speed, accel, dist; NaN when absent
    ball: np.ndarray  # (T, 4) — x, y, z, status (1 = in play)
    ball_possession: np.ndarray  # (T,) — 1 home, 2 away, 0 contested/unknown
    player_ids: list[str]  # length N, column index → person_id
    player_registry: dict[str, PlayerMeta]
    team_map: dict[str, str]  # person_id → team_id
    events: list[EventMoment]
    event_index: dict[int, list[EventMoment]]  # frame_idx → events
    section_ranges: dict[str, tuple[int, int]]  # section id → (start, end) exclusive; see model.sections
    frame_rate: float
    total_frames: int
    meta: MatchMeta
    teams: dict[str, TeamMeta]  # team_id → TeamMeta (colors, lineup, names)
    player_index: dict[str, int] = field(init=False)  # person_id → column

    def __post_init__(self) -> None:
        self.player_index = {pid: i for i, pid in enumerate(self.player_ids)}

    @classmethod
    def from_parts(
        cls,
        meta_info,
        events: list[EventMoment],
        track: "TrackingData",
    ) -> "MatchState":
        event_index: dict[int, list[EventMoment]] = {}
        for ev in events:
            event_index.setdefault(ev.frame_idx, []).append(ev)
        return cls(
            frames=track.frames,
            ball=track.ball,
            ball_possession=track.ball_possession,
            player_ids=track.player_ids,
            player_registry=meta_info.player_registry,
            team_map={
                pid: p.team_id for pid, p in meta_info.player_registry.items()
            },
            events=sorted(events, key=lambda e: e.frame_idx),
            event_index=event_index,
            section_ranges=track.section_ranges,
            frame_rate=track.frame_rate,
            total_frames=track.frames.shape[0],
            meta=meta_info.meta,
            teams=meta_info.teams,
        )

    def section_of(self, t: int) -> str:
        for name, (lo, hi) in self.section_ranges.items():
            if lo <= t < hi:
                return name
        return "firstHalf"

    def team_columns(self, team_id: str) -> list[int]:
        return [
            i for i, pid in enumerate(self.player_ids) if self.team_map.get(pid) == team_id
        ]


@dataclass
class TrackingData:
    """Intermediate output of TrackingDataLoader, consumed by MatchState.from_parts."""

    frames: np.ndarray  # (T, N, 5)
    ball: np.ndarray  # (T, 4)
    ball_possession: np.ndarray  # (T,)
    player_ids: list[str]
    section_ranges: dict[str, tuple[int, int]]
    frame_rate: float
