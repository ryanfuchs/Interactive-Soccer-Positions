"""TrackingDataLoader — DFL 04_03 positions via floodlight.

floodlight's `read_position_data_xml` uses iterparse internally and returns
per-segment, per-team XY objects (center-origin metres, x along the pitch
length). This loader:

- stacks home + away players into one (T, N, 5) array,
- concatenates game sections along the time axis,
- maps coordinates into the goal-aligned frame (Brandes 2023): x = signed
  lateral distance from the axis through the goal centers, y = longitudinal
  distance from the reference goal line (x ∈ [−width/2, width/2],
  y ∈ [0, length]),
- derives speed / acceleration / cumulative distance numerically
  (floodlight discards the S/A/D frame attributes).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from sopovis.model.meta import MatchInformation
from sopovis.model.sections import SECTION_ORDER
from sopovis.model.state import TrackingData


def _derive_kinematics(xy: np.ndarray, frame_rate: float) -> np.ndarray:
    """(T, N, 2) positions → (T, N, 3) speed, accel, cumulative distance."""
    step = np.diff(xy, axis=0, prepend=xy[:1])  # (T, N, 2)
    step_len = np.hypot(step[..., 0], step[..., 1])  # (T, N)
    speed = step_len * frame_rate
    accel = np.diff(speed, axis=0, prepend=speed[:1]) * frame_rate
    dist = np.nancumsum(step_len, axis=0)
    return np.stack([speed, accel, dist], axis=-1)


class TrackingDataLoader:
    def load(self, path: str | Path, meta_info: MatchInformation) -> TrackingData:
        from floodlight.io.dfl import read_position_data_xml

        # metadata path is required by floodlight for teamsheet links
        xy_objects, possession, ballstatus, teamsheets, _pitch = read_position_data_xml(
            str(path), str(self._mat_info_path)
        )

        home_sheet = teamsheets["Home"].teamsheet.sort_values("xID")
        away_sheet = teamsheets["Away"].teamsheet.sort_values("xID")
        player_ids = list(home_sheet["pID"]) + list(away_sheet["pID"])
        n_home = len(home_sheet)
        n_total = len(player_ids)

        # floodlight is center-origin with its x along the pitch length.
        # Goal-aligned frame: lateral x stays centered (provider y), and the
        # longitudinal coordinate y is measured from the reference goal line
        # (provider x shifted by half the pitch length).
        half_length = meta_info.meta.pitch_length / 2.0

        xy_parts: list[np.ndarray] = []
        ball_parts: list[np.ndarray] = []
        poss_parts: list[np.ndarray] = []
        section_ranges: dict[str, tuple[int, int]] = {}
        frame_rate = 25.0
        offset = 0

        for section in SECTION_ORDER:
            if section not in xy_objects:
                continue
            teams = xy_objects[section]
            home_xy = teams["Home"].xy  # (T, 2*n_home)
            away_xy = teams["Away"].xy
            ball_xy = teams["Ball"].xy  # (T, 2)
            frame_rate = float(teams["Home"].framerate or 25.0)
            t_seg = home_xy.shape[0]

            seg = np.full((t_seg, n_total, 2), np.nan, dtype=np.float64)
            seg[:, :n_home, 0] = home_xy[:, 1::2]
            seg[:, :n_home, 1] = home_xy[:, 0::2] + half_length
            seg[:, n_home:, 0] = away_xy[:, 1::2]
            seg[:, n_home:, 1] = away_xy[:, 0::2] + half_length
            xy_parts.append(seg)

            status = ballstatus[section].code.astype(np.float64)
            ball_seg = np.full((t_seg, 4), np.nan, dtype=np.float64)
            ball_seg[:, 0] = ball_xy[:, 1]
            ball_seg[:, 1] = ball_xy[:, 0] + half_length
            ball_seg[:, 2] = 0.0  # Z discarded by floodlight
            ball_seg[:, 3] = status[:t_seg]
            ball_parts.append(ball_seg)

            poss = possession[section].code.astype(np.float64)[:t_seg]
            poss_parts.append(np.nan_to_num(poss, nan=0.0))

            section_ranges[section] = (offset, offset + t_seg)
            offset += t_seg

        xy = np.concatenate(xy_parts, axis=0)  # (T, N, 2)

        kin_parts = [
            _derive_kinematics(xy[lo:hi], frame_rate)
            for lo, hi in (section_ranges[s] for s in SECTION_ORDER if s in section_ranges)
        ]
        kin = np.concatenate(kin_parts, axis=0)  # (T, N, 3)

        frames = np.concatenate([xy, kin], axis=-1)  # (T, N, 5)
        ball = np.concatenate(ball_parts, axis=0)
        ball_possession = np.concatenate(poss_parts, axis=0)

        return TrackingData(
            frames=frames,
            ball=ball,
            ball_possession=ball_possession,
            player_ids=player_ids,
            section_ranges=section_ranges,
            frame_rate=frame_rate,
        )

    def __init__(self, mat_info_path: str | Path):
        self._mat_info_path = Path(mat_info_path)
