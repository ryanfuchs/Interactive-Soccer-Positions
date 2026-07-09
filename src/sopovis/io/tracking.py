"""TrackingDataLoader — DFL 04_03 positions via floodlight.

floodlight's `read_position_data_xml` uses iterparse internally and returns
per-segment, per-team XY objects (center-origin metres). This loader:

- stacks home + away players into one (T, N, 5) array,
- concatenates game sections along the time axis,
- shifts coordinates to corner-origin (0..pitch_x, 0..pitch_y),
- derives speed / acceleration / cumulative distance numerically
  (floodlight discards the S/A/D frame attributes).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from sopovis.model.meta import MatchInformation
from sopovis.model.state import TrackingData

_SECTION_ORDER = ["firstHalf", "secondHalf"]


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

        half_x = meta_info.meta.pitch_x / 2.0
        half_y = meta_info.meta.pitch_y / 2.0

        xy_parts: list[np.ndarray] = []
        ball_parts: list[np.ndarray] = []
        poss_parts: list[np.ndarray] = []
        section_ranges: dict[str, tuple[int, int]] = {}
        frame_rate = 25.0
        offset = 0

        for section in _SECTION_ORDER:
            if section not in xy_objects:
                continue
            teams = xy_objects[section]
            home_xy = teams["Home"].xy  # (T, 2*n_home)
            away_xy = teams["Away"].xy
            ball_xy = teams["Ball"].xy  # (T, 2)
            frame_rate = float(teams["Home"].framerate or 25.0)
            t_seg = home_xy.shape[0]

            seg = np.full((t_seg, n_total, 2), np.nan, dtype=np.float64)
            seg[:, :n_home, 0] = home_xy[:, 0::2] + half_x
            seg[:, :n_home, 1] = home_xy[:, 1::2] + half_y
            seg[:, n_home:, 0] = away_xy[:, 0::2] + half_x
            seg[:, n_home:, 1] = away_xy[:, 1::2] + half_y
            xy_parts.append(seg)

            status = ballstatus[section].code.astype(np.float64)
            ball_seg = np.full((t_seg, 4), np.nan, dtype=np.float64)
            ball_seg[:, 0] = ball_xy[:, 0] + half_x
            ball_seg[:, 1] = ball_xy[:, 1] + half_y
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
            for lo, hi in (section_ranges[s] for s in _SECTION_ORDER if s in section_ranges)
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
