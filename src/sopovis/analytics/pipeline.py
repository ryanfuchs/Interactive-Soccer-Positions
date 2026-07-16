"""Per-frame analytics and temporal aggregation — pure computation.

Per team per frame: positions → shape-graph edges / tactical roles.
Whole-match orchestration (frame iteration, dependencies, caching) lives in
``sopovis.analytics.producers``.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from sopovis.analytics.roles import UNSET, compute_roles, role_count_index
from sopovis.analytics.shape_graph import points_to_shape_edges
from sopovis.model.state import MatchState

# --------------------------------------------------------------- per frame


def frame_shape_edges(points: np.ndarray, columns: list[int]) -> np.ndarray:
    """``(E, 2)`` shape-graph edges as MatchState column pairs for one team-frame.

    Degenerate frames (< 2 points, NaNs, Qhull failures) yield no edges.
    """
    k = len(points)
    if k < 2 or not np.isfinite(points).all():
        return np.empty((0, 2), dtype=np.int32)
    try:
        graph = points_to_shape_edges(points)
    except (ZeroDivisionError, ValueError, FloatingPointError):
        return np.empty((0, 2), dtype=np.int32)

    col_arr = np.asarray(columns, dtype=np.int32)
    edge_list = [
        (int(col_arr[u]), int(col_arr[v])) for u, v in graph.edges if u < k and v < k
    ]
    return (
        np.asarray(edge_list, dtype=np.int32)
        if edge_list
        else np.empty((0, 2), dtype=np.int32)
    )


def frame_roles(points: np.ndarray, attacking_positive_x: bool) -> np.ndarray:
    """``(K, 2)`` tactical roles per point; all-UNSET when inference fails."""
    k = len(points)
    if k < 2 or not np.isfinite(points).all():
        return np.full((k, 2), UNSET, dtype=np.int8)
    try:
        return compute_roles(points, attacking_positive_x)
    except (ZeroDivisionError, ValueError, FloatingPointError):
        return np.full((k, 2), UNSET, dtype=np.int8)


# ---------------------------------------------------------------------------


def infer_attack_directions(state: MatchState) -> dict[tuple[str, str], bool]:
    """(team_id, section) → attacking toward +x, inferred from GK mean position."""
    directions: dict[tuple[str, str], bool] = {}
    gk_cols: dict[str, list[int]] = {}
    for team_id in (state.meta.home_team_id, state.meta.guest_team_id):
        gk_cols[team_id] = [
            state.player_index[pid]
            for pid, p in state.player_registry.items()
            if p.team_id == team_id and p.is_goalkeeper and pid in state.player_index
        ]

    for section, (lo, hi) in state.section_ranges.items():
        window = state.frames[lo : min(lo + 2500, hi), :, 0]  # first ~100 s
        for team_id, cols in gk_cols.items():
            gk_x = window[:, cols]
            mean_x = np.nanmean(gk_x) if np.isfinite(gk_x).any() else None
            if mean_x is None:  # fallback: whole-team mean
                team_cols = state.team_columns(team_id)
                mean_x = np.nanmean(window[:, team_cols])
            directions[(team_id, section)] = bool(mean_x < state.meta.pitch_x / 2)
    return directions


def outfield_columns(state: MatchState, team_id: str) -> list[int]:
    return [
        c
        for c in state.team_columns(team_id)
        if not state.player_registry[state.player_ids[c]].is_goalkeeper
    ]


# ------------------------------------------------------ temporal aggregation


@dataclass
class RoleResult:
    tactical_roles: np.ndarray  # (Ta, N, 2) int8, UNSET where absent
    role_counts: np.ndarray  # (Ta, N, 25) int32 cumulative histogram
    substitution_frames: list[int]  # analytics-frame indices of lineup changes
    player_row_order: dict[str, int]  # person_id → stable heatmap row (per team)


def aggregate_roles(
    state: MatchState, roles: np.ndarray, presence: np.ndarray
) -> RoleResult:
    """Cumulative role histogram, substitution detection and row ordering."""
    ta_total = roles.shape[0]
    counts = np.zeros((ta_total, roles.shape[1], 25), dtype=np.int32)

    # cumulative role histogram over all frames
    for ta in range(ta_total):
        if ta > 0:
            counts[ta] = counts[ta - 1]
        present_cols = np.nonzero(presence[ta])[0]
        for c in present_cols:
            idx = role_count_index(int(roles[ta, c, 0]), int(roles[ta, c, 1]))
            counts[ta, c, idx] += 1

    # substitution detection — presence set change between analytics frames
    sub_frames = [0]
    for ta in range(1, ta_total):
        if not np.array_equal(presence[ta], presence[ta - 1]):
            sub_frames.append(ta)
    sub_frames.append(ta_total - 1)
    sub_frames = sorted(set(sub_frames))

    team_ids = [state.meta.home_team_id, state.meta.guest_team_id]
    row_order = _compute_player_ordering(
        state, team_ids, roles, counts, presence, sub_frames
    )

    return RoleResult(
        tactical_roles=roles,
        role_counts=counts,
        substitution_frames=sub_frames,
        player_row_order=row_order,
    )


def _compute_player_ordering(
    state: MatchState,
    team_ids: list[str],
    roles: np.ndarray,
    counts: np.ndarray,
    presence: np.ndarray,
    sub_frames: list[int],
) -> dict[str, int]:
    """Assign stable heatmap rows across substitutions.

    Starters are ordered **zeilenweise** (row-major) on the 5×5 role matrix:
    depth row F→B outer, lateral L→R within each depth — i.e. flat index
    ``(x_role+2)*5 + (y_role+2)``. Ties break by shirt number.

    At each substitution the incoming player inherits the row of the most
    role-similar outgoing player (greedy min assignment).
    """
    from sopovis.analytics.roles import most_frequent_role_index, role_similarity

    ta_total = roles.shape[0]
    row_order: dict[str, int] = {}

    for tid in team_ids:
        cols = np.asarray(
            [
                state.player_index[pid]
                for pid in state.player_ids
                if state.team_map.get(pid) == tid
            ],
            dtype=np.int32,
        )

        first_sub = sub_frames[1] if len(sub_frames) > 1 else ta_total - 1

        starters = [c for c in cols if presence[0, c]]
        pairs = []
        for c in starters:
            idx = most_frequent_role_index(counts[0, c], counts[first_sub, c])
            shirt = state.player_registry[state.player_ids[c]].shirt_number
            # (matrix flat index, shirt) — zeilenweise then jersey
            pairs.append((c, idx if idx is not None else 12, shirt))
        pairs.sort(key=lambda p: (p[1], p[2]))
        for row, (c, _idx, _shirt) in enumerate(pairs):
            row_order[state.player_ids[c]] = row

        for si in range(1, len(sub_frames) - 1):
            frame_prev = sub_frames[si - 1] + 1
            frame = sub_frames[si]
            frame_next = min(sub_frames[si + 1], ta_total - 1)
            before, after = frame - 1, min(frame + 1, ta_total - 1)

            out_cols = [
                c for c in cols if presence[before, c] and not presence[after, c]
            ]
            in_cols = [
                c
                for c in cols
                if presence[after, c]
                and not presence[before, c]
                and state.player_ids[c] not in row_order
            ]
            if not out_cols or not in_cols:
                continue

            score = np.zeros((len(out_cols), len(in_cols)), dtype=np.int64)
            for j, oc in enumerate(out_cols):
                role_prev = most_frequent_role_index(
                    counts[min(frame_prev, before), oc], counts[before, oc]
                )
                for k, ic in enumerate(in_cols):
                    role_next = most_frequent_role_index(
                        counts[after, ic], counts[frame_next, ic]
                    )
                    if role_prev is None or role_next is None:
                        score[j, k] = 100
                    else:
                        score[j, k] = role_similarity(role_prev, role_next)

            out_rows = [row_order.get(state.player_ids[oc], 0) for oc in out_cols]
            remaining_out = list(range(len(out_cols)))
            remaining_in = list(range(len(in_cols)))
            while remaining_out and remaining_in:
                best = min(
                    ((j, k) for j in remaining_out for k in remaining_in),
                    key=lambda jk: score[jk[0], jk[1]],
                )
                j, k = best
                row_order[state.player_ids[in_cols[k]]] = out_rows[j]
                remaining_out.remove(j)
                remaining_in.remove(k)

    return row_order


def _progress(iterator, total):
    import sys
    import time

    t0 = time.perf_counter()
    width = 24
    step = max(1, total // 50)

    def _draw(done: int) -> None:
        frac = done / total if total else 1.0
        filled = int(width * frac)
        bar = "█" * filled + "░" * (width - filled)
        elapsed = time.perf_counter() - t0
        eta = (elapsed / frac - elapsed) if frac > 0 else 0.0
        sys.stdout.write(
            f"\r      [{bar}] {100 * frac:5.1f}%  "
            f"{done:,}/{total:,}  "
            f"{elapsed:5.0f}s elapsed  ~{eta:4.0f}s left"
        )
        sys.stdout.flush()

    for i, item in enumerate(iterator):
        yield item
        done = i + 1
        if done % step == 0 or done == total:
            _draw(done)
    sys.stdout.write("\n")
    sys.stdout.flush()
