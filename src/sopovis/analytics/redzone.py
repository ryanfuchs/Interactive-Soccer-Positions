"""Red zone detection (Tanner 2026) — the central space between the defensive
line and the first midfield line of one team.

Implements the improved player selection (shape-graph line growth with an
angle-from-horizontal cutoff, wingback extension) and the refined red zone
construction (closed degree-3 NURBS with centrality weights and midfield-gap
extension points), adapted to SoPoVis conventions:

- coordinates are goal-aligned pitch metres (x lateral, y longitudinal),
- "up the pitch" for a team means toward its own goal (defending direction),
- tactical roles come from the existing ``roles`` product (5x5 grid),
- the per-frame result is stored compactly as NURBS control points and
  weights; the boundary polygon is re-sampled where needed.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import atan2, pi

import numpy as np

from sopovis.analytics.shape_graph import frame_to_shape_graph
from sopovis.analytics.roles import UNSET

DEGREE = 3  # minimum degree for C2 continuity (paper, section 4.2)

# weights of the refined construction (paper, algorithm 5/6)
CENTER_WEIGHT = 2.0
DEFAULT_WEIGHT = 1.0
SIDE_WEIGHT = 0.3

LINE_ANGLE_CUTOFF = pi / 7  # ~25.7 deg (paper, section 4.1.1)
WINGBACK_ANGLE_CUTOFF = pi / 4  # 45 deg (paper, algorithm 3)
MERGE_RADIUS_M = 2.5  # co-located players merged (paper, section 4.1)


@dataclass
class RedzoneResult:
    """Per-team red zone over the analytics-frame grid.

    ``control_points[tid][ta]`` is a (K, 2) float32 array of NURBS control
    points in pitch coordinates (None when the zone is undefined) and
    ``weights[tid][ta]`` the matching (K,) weight vector. ``areas[tid]`` is
    the (Ta,) polygon area in square metres (0 where undefined) and
    ``inside_opponent`` a (Ta, N) bool array marking players standing inside
    the red zone of the *opposing* team.
    """

    control_points: dict[str, list[np.ndarray | None]]
    weights: dict[str, list[np.ndarray | None]]
    areas: dict[str, np.ndarray]
    inside_opponent: np.ndarray


# ------------------------------------------------------------------- NURBS


def evaluate_closed_nurbs(
    ctrl: np.ndarray, weights: np.ndarray, samples: int = 200
) -> np.ndarray:
    """Sample a closed rational B-spline of degree 3 as an (S, 2) polyline.

    The control polygon is wrapped (first ``DEGREE`` points repeated) over a
    uniform unclamped knot vector, which closes the curve with C2 continuity
    (paper, section 2.5). Vectorised de Boor over all samples.
    """
    p = DEGREE
    P = np.vstack([ctrl, ctrl[:p]]).astype(float)
    w = np.concatenate([weights, weights[:p]]).astype(float)
    n = len(P)
    # homogeneous coordinates (wx, wy, w)
    pw = np.column_stack([P * w[:, None], w])
    knots = np.arange(n + p + 1, dtype=float)
    u = np.linspace(p, n, samples, endpoint=False)
    k = np.clip(np.searchsorted(knots, u, side="right") - 1, p, n - 1)

    d = pw[(k[:, None] - p + np.arange(p + 1))]  # (S, p+1, 3)
    for r in range(1, p + 1):
        for j in range(p, r - 1, -1):
            i = k - p + j
            denom = knots[i + p - r + 1] - knots[i]
            alpha = ((u - knots[i]) / denom)[:, None]
            d[:, j] = (1.0 - alpha) * d[:, j - 1] + alpha * d[:, j]
    return d[:, p, :2] / d[:, p, 2:3]


def polygon_area(polygon: np.ndarray) -> float:
    """Shoelace area of an (S, 2) closed polyline."""
    x, y = polygon[:, 0], polygon[:, 1]
    return float(0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(np.roll(x, -1), y)))


# --------------------------------------------------------- player selection


def _merge_close(points: np.ndarray, radius: float) -> list[int]:
    """Greedy representative selection: drop players within ``radius`` of a
    kept player (paper merges co-located players for angular stability)."""
    keep: list[int] = []
    for i in range(len(points)):
        if all(np.hypot(*(points[i] - points[j])) > radius for j in keep):
            keep.append(i)
    return keep


def _angle_from_horizontal(du: float, dv: float) -> float:
    return atan2(abs(dv), abs(du))


def _get_line(
    graph, u: dict, v: dict, depth_role: dict, cutoff: float
) -> set:
    """Line selection (paper, algorithm 2) on a shape graph.

    ``u``/``v`` map nodes to lateral / depth-up coordinates (larger v =
    deeper, toward the own goal); ``depth_role`` is the vertical split from
    the role model (larger = deeper).
    """
    nodes = list(graph.nodes)
    if not nodes:
        return set()
    top = max(depth_role[c] for c in nodes)
    sel = {c for c in nodes if depth_role[c] == top}

    def angle(a, b):
        return _angle_from_horizontal(u[b] - u[a], v[b] - v[a])

    queue = [w for c in sel for w in graph.neighbors(c) if w not in sel]
    while queue:
        cand = queue.pop(0)
        if cand in sel:
            continue
        nbrs_in = [w for w in graph.neighbors(cand) if w in sel]
        if nbrs_in and all(angle(cand, w) < cutoff for w in nbrs_in):
            sel.add(cand)
            queue.extend(w for w in graph.neighbors(cand) if w not in sel)

    # refinement — strictly subtractive, terminates (paper, section 4.1.1)
    changed = True
    while changed:
        changed = False
        for c in list(sel):
            for w in graph.neighbors(c):
                above = v[w] > v[c]
                if w in sel and above and angle(c, w) >= cutoff:
                    sel.discard(c)
                    changed = True
                    break
                if w not in sel and above:
                    sel.discard(c)
                    changed = True
                    break
    return sel


def _wingback_extension(graph, sel: set, u: dict, v: dict) -> set:
    """Backline extension for advanced fullbacks (paper, algorithm 3)."""
    if not sel:
        return sel
    for side in (-1, 1):
        edge_player = min(sel, key=lambda c: side * -u[c])
        cands = [
            r
            for r in graph.neighbors(edge_player)
            if r not in sel and side * (u[r] - u[edge_player]) > 0
        ]
        if not cands:
            continue
        best = min(
            cands,
            key=lambda r: _angle_from_horizontal(
                u[r] - u[edge_player], v[r] - v[edge_player]
            ),
        )
        angle = _angle_from_horizontal(
            u[best] - u[edge_player], v[best] - v[edge_player]
        )
        outside_below = all(
            v[w] < v[best] for w in graph.neighbors(best) if w not in sel
        )
        if angle < WINGBACK_ANGLE_CUTOFF and outside_below:
            sel.add(best)
    return sel


# --------------------------------------------------------- zone construction


def compute_redzone_frame(
    xy: np.ndarray,
    columns: list[int],
    roles: np.ndarray,
    attacking_positive_y: bool,
) -> tuple[np.ndarray, np.ndarray] | None:
    """Control points + weights of one team's red zone for one frame.

    ``xy`` are the (K, 2) present outfield positions, ``columns`` their
    MatchState columns and ``roles`` the (N, 2) role grid of the analytics
    frame. Returns None when the zone is undefined (failed role inference,
    empty lines, too few control points).
    """
    role_by_col = {c: roles[c] for c in columns}
    if any(r[0] == UNSET for r in role_by_col.values()):
        return None

    keep = _merge_close(xy, MERGE_RADIUS_M)
    cols = [columns[i] for i in keep]
    pts = xy[keep]

    up_sign = -1.0 if attacking_positive_y else 1.0
    u = {c: float(pts[i, 0]) for i, c in enumerate(cols)}
    v = {c: up_sign * float(pts[i, 1]) for i, c in enumerate(cols)}
    y_of = {c: float(pts[i, 1]) for i, c in enumerate(cols)}
    depth_role = {c: int(role_by_col[c][0]) for c in cols}  # +2 = Back
    lat_role = {c: int(role_by_col[c][1]) for c in cols}

    # shape graph without the forward split (paper, algorithm 1 line 3)
    non_forward = [c for c in cols if depth_role[c] > -2]
    if len(non_forward) < 2:
        return None
    g1 = frame_to_shape_graph({c: (u[c], v[c]) for c in non_forward})
    backline = _get_line(g1, u, v, depth_role, LINE_ANGLE_CUTOFF)
    backline = _wingback_extension(g1, backline, u, v)
    if not backline:
        return None

    remaining = [c for c in non_forward if c not in backline]
    if not remaining:
        return None
    g2 = frame_to_shape_graph({c: (u[c], v[c]) for c in remaining})
    midfield = _get_line(g2, u, v, depth_role, LINE_ANGLE_CUTOFF)
    if not midfield:
        return None

    back_sorted = sorted(backline, key=lambda c: u[c])  # left to right
    mid_sorted = sorted(midfield, key=lambda c: -u[c])  # right to left

    def weight_of(c) -> float:
        if abs(lat_role[c]) == 2:
            same = sum(
                1 for d in list(backline) + list(midfield) if lat_role[d] == lat_role[c]
            )
            return SIDE_WEIGHT / max(1, same)
        if lat_role[c] == 0:
            return CENTER_WEIGHT
        return DEFAULT_WEIGHT

    # midfield-gap extensions (paper, algorithm 6): if one pitch side has no
    # midfielder, add control points at the midfield height above that side's
    # centre-adjacent defenders so the zone cannot collapse there.
    lat_dir = _lat_direction(lat_role, u)

    def pitch_side(c) -> int:
        return int(np.sign(lat_role[c]) * lat_dir)

    def side_extension(side: int) -> list[tuple[float, float]]:
        if any(pitch_side(c) == side for c in midfield):
            return []
        anchor = max(midfield, key=lambda c: side * u[c])
        ext_cols = [
            c for c in backline if pitch_side(c) == side and abs(lat_role[c]) == 1
        ]
        return [(u[c], y_of[anchor]) for c in ext_cols]

    right_ext = side_extension(+1)
    left_ext = side_extension(-1)

    ctrl: list[tuple[float, float]] = []
    weights: list[float] = []
    for c in back_sorted:
        ctrl.append((u[c], y_of[c]))
        weights.append(weight_of(c))
    for p in sorted(right_ext, key=lambda q: -q[0]):
        ctrl.append(p)
        weights.append(DEFAULT_WEIGHT)
    for c in mid_sorted:
        ctrl.append((u[c], y_of[c]))
        weights.append(weight_of(c))
    for p in sorted(left_ext, key=lambda q: q[0]):
        ctrl.append(p)
        weights.append(DEFAULT_WEIGHT)

    if len(ctrl) < DEGREE + 1:
        return None
    return (
        np.asarray(ctrl, dtype=np.float32),
        np.asarray(weights, dtype=np.float32),
    )


def _lat_direction(lat_role: dict, u: dict) -> float:
    """Sign linking the lateral role axis to the pitch x axis (orientation)."""
    left = [u[c] for c in lat_role if lat_role[c] < 0]
    right = [u[c] for c in lat_role if lat_role[c] > 0]
    if not left or not right:
        return 1.0
    return 1.0 if float(np.mean(right)) >= float(np.mean(left)) else -1.0
