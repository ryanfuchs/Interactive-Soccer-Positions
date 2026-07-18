"""Tactical role model via position-plot splitting on a 5×5 grid.

Roles are discrete coordinates on a 5×5 grid:
  x_role ∈ [-2, 2]  depth   — −2 = Forward … +2 = Back
  y_role ∈ [-2, 2]  lateral — −2 = Left    … +2 = Right
UNSET (−3) marks players that received no role (absent from the frame).

Assignment uses recursive barycenter splits of the shape graph
(``frame_to_position_plot``). Pitch coordinates are goal-aligned: x is the
signed lateral offset and y runs goal line to goal line. For a team attacking
toward +y, the most advanced players (max y) are Forwards and lower x is
Left; ``attacking_positive_y=False`` mirrors both.
"""
from __future__ import annotations

from math import cos, hypot, pi

import networkx as nx
import numpy as np

from sopovis.analytics.shape_graph import frame_to_shape_graph

UNSET = -3

ROLE_NAMES = [
    ["LF", "LCF", "CF", "RCF", "RF"],
    ["LF", "LAM", "CAM", "RAM", "RF"],
    ["LM", "LCM", "CM", "RCM", "RM"],
    ["LB", "LDM", "CDM", "RDM", "RB"],
    ["LB", "LCB", "CB", "RCB", "RB"],
]

# depth palette: F (red) → B (blue); lateral palette: L → R
ROLE_COLORS_X = ["#B7352D", "#D48681", "#E2E2E2", "#7A9DCF", "#215CAF"]
ROLE_COLORS_Y = ["#8E6713", "#D2C2A1", "#E2E2E2", "#C0C7A1", "#627313"]


def role_label(x_role: int, y_role: int) -> str:
    if x_role == UNSET or y_role == UNSET:
        return ""
    return ROLE_NAMES[x_role + 2][y_role + 2]


def role_count_index(x_role: int, y_role: int) -> int:
    """Flat 0..24 histogram index for a grid cell."""
    return (x_role + 2) * 5 + (y_role + 2)


def most_frequent_role_index(start_count: np.ndarray, end_count: np.ndarray) -> int | None:
    """Grid cell with the largest count delta over a time window."""
    diff = end_count.astype(np.int64) - start_count.astype(np.int64)
    if diff.max() <= 0:
        return None
    return int(diff.argmax())


def most_frequent_role(start_count: np.ndarray, end_count: np.ndarray) -> tuple[int, int]:
    idx = most_frequent_role_index(start_count, end_count)
    if idx is None:
        return (0, 0)
    return (idx // 5 - 2, idx % 5 - 2)


def role_similarity(index_a: int, index_b: int) -> int:
    """Squared grid distance between two flat role indices."""
    x1, y1 = index_a // 5, index_a % 5
    x2, y2 = index_b // 5, index_b % 5
    return (x1 - x2) ** 2 + (y1 - y2) ** 2


def frame_to_position_plot(frame: dict) -> dict:
    """Create position-plot coordinates from the shape graph.

    Parameters
    ----------
    frame :
        Mapping of player labels → ``(x, y)`` coordinates.

    Returns
    -------
    dict
        Mapping of labels → ``(h_role, v_role)`` with each component in
        approximately ``[-2, 2]`` (horizontal then vertical splits).
    """

    def cos_vec(v1, v2):
        denom = hypot(*v1) * hypot(*v2)
        if denom == 0:
            return 1  # coincident points → treat as aligned
        result = (v1[0] * v2[0] + v1[1] * v2[1]) / denom
        if result > 1:
            return 1
        if result < -1:
            return -1
        return result

    def left_cos(v1, v2):
        cross_product = v2[1] * v1[0] - v2[0] * v1[1]
        if cross_product <= 0:
            return -2 - cos_vec(v1, v2)
        return cos_vec(v1, v2)

    def vector(e):
        p, q = e
        return (frame[q][0] - frame[p][0], frame[q][1] - frame[p][1])

    def iter_edges(p_start, p_end, v_start, S):
        face_edges, v, p = set(), v_start, p_start
        while True:
            min_cos, p_next, neighbors = -3, None, list(S.neighbors(p))
            if not neighbors:
                break
            if len(neighbors) == 1:
                p_next = neighbors[0]
                face_edges.add((p, p_next))
                v = vector((p_next, p))
                p, p_next = p_next, None
                continue
            for r in neighbors:
                vr = vector((p, r))
                if vr == v or vr == (0.0, 0.0):
                    continue
                cos_left = left_cos(v, vr)
                if cos_left >= min_cos:
                    min_cos, p_next = cos_left, r
            if p_next is None:
                break
            edge = (p, p_next)
            if edge in face_edges:
                break
            face_edges.add(edge)
            if p_start != p_end and p_next == p_end:
                break
            v, p = vector((p_next, p)), p_next
        return face_edges

    def find_faces(S, frame_local):
        if len(S.edges) <= 1:
            return []
        faces = []
        top_point = max(frame_local.items(), key=lambda item: item[1][1])[0]
        E = iter_edges(top_point, top_point, (0, 1), S)
        for e in S.edges:
            F = iter_edges(e[0], e[0], vector(e), S)
            if F not in faces and F != E:
                faces.append(F)
        return faces

    def find_barycenters_new(S, frame_local, o_vec):
        faces = find_faces(S, frame_local)
        barycenters = []
        if not faces:
            for e in S.edges:
                if abs(cos_vec(vector(e), o_vec)) < cos(1 / 8 * pi):
                    barycenters.append(
                        (
                            (frame_local[e[0]][0] + frame_local[e[1]][0]) / 2,
                            (frame_local[e[0]][1] + frame_local[e[1]][1]) / 2,
                        )
                    )
        else:
            for F in faces:
                x_cm, y_cm = 0, 0
                for e in F:
                    x_cm += frame_local[e[0]][0]
                    y_cm += frame_local[e[0]][1]
                x_cm, y_cm = x_cm / len(F), y_cm / len(F)
                barycenters.append((x_cm, y_cm))
        return barycenters

    def collinear(frame_local):
        if len(frame_local) <= 2:
            return True
        keys = list(frame_local.keys())
        v1 = vector((keys[0], keys[1]))
        for p in keys[2:]:
            vp = vector((keys[0], p))
            if abs(cos_vec(v1, vp)) != 1:
                return False
        return True

    def split_positions(frame_local, orientation, pos_dict, reps=2):
        if orientation == "v":
            i = 1
            norm_vec = (1, 0)
        elif orientation == "h":
            i = 0
            norm_vec = (0, 1)
        else:
            return

        for c in range(reps, 0, -1):
            frame_current = {pt: frame_local[pt] for pt in frame_local if pos_dict[pt][i] == 0}
            if not frame_current:
                continue

            if collinear(frame_current):
                S_current = nx.Graph()
                for p1 in frame_current:
                    for p2 in frame_current:
                        if p1 != p2:
                            S_current.add_edge(p1, p2)
            else:
                S_current = frame_to_shape_graph(frame_current)

            B = find_barycenters_new(S_current, frame_current, norm_vec)
            if B:
                b_min, b_max = min(b[i] for b in B), max(b[i] for b in B)
                p_min = min(frame_current[p][i] for p in frame_current)
                p_max = max(frame_current[p][i] for p in frame_current)
                third1, third2 = p_min + (p_max - p_min) / 3, p_max - (p_max - p_min) / 3
                b_tot = sum(frame_current[p][i] for p in frame_current) / len(frame_current)

                if b_min == b_max and len(S_current.nodes) >= 4 and b_tot != b_min:
                    over = [p for p in S_current.nodes if frame_current[p][i] > b_min]
                    under = [p for p in S_current.nodes if frame_current[p][i] < b_min]
                    if len(over) == 1:
                        pos_dict[over[0]][i] += c
                    elif len(under) == 1:
                        pos_dict[under[0]][i] -= c
                    else:
                        for p in frame_current:
                            if frame_current[p][i] < b_min:
                                pos_dict[p][i] -= c
                            if frame_current[p][i] > b_max:
                                pos_dict[p][i] += c
                elif b_min > third1 and b_max < third2:
                    for p in frame_current:
                        if frame_current[p][i] < third1:
                            pos_dict[p][i] -= c
                        if frame_current[p][i] > third2:
                            pos_dict[p][i] += c
                else:
                    for p in frame_current:
                        if frame_current[p][i] < b_min:
                            pos_dict[p][i] -= c
                        if frame_current[p][i] > b_max:
                            pos_dict[p][i] += c

    pos_dict = {p: [0, 0] for p in frame.keys()}
    split_positions(frame, "h", pos_dict)
    split_positions(frame, "v", pos_dict)
    return {p: tuple(pos_dict[p]) for p in pos_dict}


def compute_roles(
    points: np.ndarray,
    attacking_positive_y: bool,
) -> np.ndarray:
    """Assign ``(x_role, y_role)`` per point via position-plot splits.

    Parameters
    ----------
    points :
        ``(K, 2)`` outfield positions in goal-aligned pitch metres
        (lateral x, longitudinal y).
    attacking_positive_y :
        Whether the team attacks toward +y; controls which end is Forward
        and which side is Left.

    Returns
    -------
    np.ndarray
        ``(K, 2)`` int8 roles. ``frame_to_position_plot`` returns
        ``(h, v)`` = (lateral split, longitudinal split); depth comes from
        the longitudinal split and lateral from the lateral split, with
        signs fixed by the attack direction.
    """
    k = len(points)
    if k == 0:
        return np.empty((0, 2), dtype=np.int8)

    frame = {i: (float(points[i, 0]), float(points[i, 1])) for i in range(k)}
    pos = frame_to_position_plot(frame)

    roles = np.zeros((k, 2), dtype=np.int8)
    for i in range(k):
        h, v = pos[i]
        lat_role = int(np.clip(h, -2, 2))
        lon_role = int(np.clip(v, -2, 2))
        # Grid: −2 = Forward on depth, −2 = Left laterally.
        # Attacking +y: max y is Forward (negate lon); Left is −x (keep lat).
        # Attacking −y: min y is Forward (keep lon); Left is +x (negate lat).
        if attacking_positive_y:
            roles[i, 0] = -lon_role
            roles[i, 1] = lat_role
        else:
            roles[i, 0] = lon_role
            roles[i, 1] = -lat_role
    return roles
