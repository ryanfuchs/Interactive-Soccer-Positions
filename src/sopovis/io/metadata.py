"""MetadataLoader — parse DFL 02_01 matchinformation XML.

Small files (~12 KB) → full DOM parse. floodlight's teamsheet reader drops
team colors and match-level info we need, so this parses the file directly.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from sopovis.model.meta import MatchInformation, MatchMeta, PlayerMeta, TeamMeta


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


class MetadataLoader:
    def load(self, path: str | Path) -> MatchInformation:
        root = ET.parse(path).getroot()
        info = root.find("MatchInformation")
        general = info.find("General")
        environment = info.find("Environment")
        other = info.find("OtherGameInformation")

        meta = MatchMeta(
            match_id=general.get("MatchId"),
            competition_id=general.get("CompetitionId"),
            competition_name=general.get("CompetitionName", ""),
            season=general.get("Season", ""),
            match_day=int(general.get("MatchDay", 0)),
            home_team_id=general.get("HomeTeamId"),
            guest_team_id=general.get("GuestTeamId"),
            home_team_name=general.get("HomeTeamName", ""),
            guest_team_name=general.get("GuestTeamName", ""),
            kickoff_time=_parse_time(general.get("KickoffTime")),
            result=general.get("Result", ""),
            pitch_x=float(environment.get("PitchX", 105.0)),
            pitch_y=float(environment.get("PitchY", 68.0)),
            stadium_name=environment.get("StadiumName", ""),
            total_time_first_half=int(other.get("TotalTimeFirstHalf", 0)) if other is not None else 0,
            total_time_second_half=int(other.get("TotalTimeSecondHalf", 0)) if other is not None else 0,
        )

        teams: dict[str, TeamMeta] = {}
        player_registry: dict[str, PlayerMeta] = {}
        team_by_role: dict[str, TeamMeta] = {}

        for team_el in info.find("Teams").findall("Team"):
            team_id = team_el.get("TeamId")
            role = team_el.get("Role", "")
            players: list[PlayerMeta] = []
            for p in team_el.find("Players").findall("Player"):
                player = PlayerMeta(
                    person_id=p.get("PersonId"),
                    shirt_number=int(p.get("ShirtNumber", 0)),
                    first_name=p.get("FirstName", ""),
                    last_name=p.get("LastName", ""),
                    short_name=p.get("Shortname", ""),
                    team_id=team_id,
                    role=role,
                    playing_position=p.get("PlayingPosition"),
                    starting=p.get("Starting") == "true",
                    team_leader=p.get("TeamLeader") == "true",
                )
                players.append(player)
                player_registry[player.person_id] = player

            team = TeamMeta(
                team_id=team_id,
                team_name=team_el.get("TeamName", ""),
                role=role,
                shirt_main_color=team_el.get("PlayerShirtMainColor", "#888888"),
                shirt_secondary_color=team_el.get("PlayerShirtSecondaryColor", "#444444"),
                shirt_number_color=team_el.get("PlayerShirtNumberColor", "#ffffff"),
                lineup=team_el.get("LineUp", ""),
                players=players,
            )
            teams[team_id] = team
            team_by_role[role] = team

        return MatchInformation(
            meta=meta,
            teams=teams,
            player_registry=player_registry,
            team_by_role=team_by_role,
        )
