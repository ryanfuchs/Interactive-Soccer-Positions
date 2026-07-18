"""Shared fixtures — synthetic match for fast UI/render tests."""
import matplotlib

matplotlib.use("Agg")

import numpy as np
import pytest

from sopovis.model.events import EventMoment
from sopovis.model.meta import MatchInformation, MatchMeta, PlayerMeta, TeamMeta
from sopovis.model.state import MatchState, TrackingData


def _make_team(team_id: str, role: str, n_players: int = 14) -> TeamMeta:
    players = [
        PlayerMeta(
            person_id=f"{team_id}-P{i:02d}",
            shirt_number=i + 1,
            first_name=f"First{i}",
            last_name=f"Last{i}",
            short_name=f"F. Last{i}",
            team_id=team_id,
            role=role,
            playing_position="TW" if i == 0 else "MZ",
            starting=i < 11,
            team_leader=i == 1,
        )
        for i in range(n_players)
    ]
    return TeamMeta(
        team_id=team_id,
        team_name=f"Team {role}",
        role=role,
        shirt_main_color="#C43140" if role == "home" else "#215CAF",
        shirt_secondary_color="#222222",
        shirt_number_color="#ffffff",
        lineup="4-4-2",
        players=players,
    )


@pytest.fixture(scope="session")
def synthetic_state() -> MatchState:
    rng = np.random.default_rng(42)
    home = _make_team("CLU-HOME", "home")
    away = _make_team("CLU-AWAY", "guest")

    meta = MatchMeta(
        match_id="SYN-MAT-000001",
        competition_id="SYN-COM",
        competition_name="Synthetic League",
        season="2022/2023",
        match_day=1,
        home_team_id=home.team_id,
        guest_team_id=away.team_id,
        home_team_name=home.team_name,
        guest_team_name=away.team_name,
        kickoff_time=None,
        result="1:0",
        pitch_length=105.0,
        pitch_width=68.0,
        stadium_name="Test Arena",
        total_time_first_half=60_000,
        total_time_second_half=60_000,
    )
    info = MatchInformation(
        meta=meta,
        teams={home.team_id: home, away.team_id: away},
        player_registry={p.person_id: p for t in (home, away) for p in t.players},
        team_by_role={"home": home, "guest": away},
    )

    t_half = 1500  # 60 s per half at 25 fps
    t_total = 2 * t_half
    player_ids = [p.person_id for p in home.players] + [p.person_id for p in away.players]
    n = len(player_ids)

    frames = np.full((t_total, n, 5), np.nan)
    # starters follow a smooth random walk around formation anchors
    # (goal-aligned frame: x lateral and signed, y from the reference goal line)
    for team_idx, team in enumerate((home, away)):
        base_col = team_idx * len(home.players)
        anchor_y = 30.0 if team_idx == 0 else 75.0
        for i in range(11):
            col = base_col + i
            ay = 8.0 if i == 0 else anchor_y + rng.uniform(-18, 18)
            ax = rng.uniform(-26, 26)
            if team_idx == 1 and i == 0:
                ay = 97.0
            walk = rng.normal(0, 0.06, size=(t_total, 2)).cumsum(axis=0)
            frames[:, col, 0] = np.clip(ax + walk[:, 0], -33, 33)
            frames[:, col, 1] = np.clip(ay + walk[:, 1], 1, 104)
    frames[:, :, 2:] = 0.0

    ball = np.zeros((t_total, 4))
    ball[:, 0] = rng.normal(0, 10, t_total).cumsum() * 0.01
    ball[:, 1] = 52.5
    ball[:, 3] = 1.0

    track = TrackingData(
        frames=frames,
        ball=ball,
        ball_possession=np.ones(t_total),
        player_ids=player_ids,
        section_ranges={"firstHalf": (0, t_half), "secondHalf": (t_half, t_total)},
        frame_rate=25.0,
    )

    events = [
        EventMoment(0, "KickOff_Play_Pass", player_ids[5], home.team_id, 0.0, 52.5, "firstHalf"),
        EventMoment(700, "ShotAtGoal_SuccessfulShot", player_ids[9], home.team_id, -4.0, 95.0, "firstHalf"),
        EventMoment(900, "Caution", player_ids[20], away.team_id, -14.0, 50.0, "firstHalf"),
        EventMoment(t_half - 1, "FinalWhistle", None, None, None, None, "firstHalf"),
        EventMoment(t_total - 1, "FinalWhistle", None, None, None, None, "secondHalf"),
    ]

    return MatchState.from_parts(info, events, track)


@pytest.fixture(scope="session")
def synthetic_bundle(synthetic_state):
    from sopovis.bundle import BundleBuilder

    return BundleBuilder(analytics_stride=5).build(synthetic_state)
