"""EventLoader — DFL 03_02 events via floodlight.

floodlight returns per-segment, per-team Events dataframes with a `gameclock`
(seconds from segment start). Frame alignment: frame_idx = section_start +
round(gameclock * frame_rate), clamped to the section range.

Event locations are mapped into the same goal-aligned frame as tracking
(x lateral and signed, y longitudinal from the reference goal line).
"""
from __future__ import annotations

import math
from pathlib import Path

from sopovis.model.events import EventMoment


class EventLoader:
    def load(
        self,
        path: str | Path,
        mat_info_path: str | Path,
        section_ranges: dict[str, tuple[int, int]],
        frame_rate: float = 25.0,
        pitch_length: float = 105.0,
    ) -> list[EventMoment]:
        from floodlight.io.dfl import read_event_data_xml

        events_objects, _teamsheets, _pitch = read_event_data_xml(
            str(path), str(mat_info_path)
        )

        moments: list[EventMoment] = []
        for section, teams in events_objects.items():
            if section not in section_ranges:
                continue
            lo, hi = section_ranges[section]
            for _team, ev in teams.items():
                df = ev.events
                for row in df.itertuples(index=False):
                    gameclock = getattr(row, "gameclock", None)
                    if gameclock is None or (isinstance(gameclock, float) and math.isnan(gameclock)):
                        continue
                    frame_idx = lo + int(round(float(gameclock) * frame_rate))
                    frame_idx = max(lo, min(frame_idx, hi - 1))
                    # provider frame: at_x along length (center-origin),
                    # at_y lateral → goal-aligned: x = at_y, y = at_x + L/2
                    at_x = _float_or_none(getattr(row, "at_x", None))
                    at_y = _float_or_none(getattr(row, "at_y", None))
                    qualifier = getattr(row, "qualifier", None)
                    moments.append(
                        EventMoment(
                            frame_idx=frame_idx,
                            event_type=str(row.eID),
                            player_id=_none_if_nan(getattr(row, "pID", None)),
                            team_id=_none_if_nan(getattr(row, "tID", None)),
                            x=at_y,
                            y=(at_x + pitch_length / 2.0) if at_x is not None else None,
                            section=section,
                            raw=dict(qualifier) if isinstance(qualifier, dict) else {},
                        )
                    )

        moments.sort(key=lambda m: m.frame_idx)
        return moments


def _none_if_nan(value):
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _float_or_none(value) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f
