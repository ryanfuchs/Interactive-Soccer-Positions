"""Shape graph construction via Delaunay reduction.

Delaunay triangulation followed by iterative removal of edges whose combined
apex angle exceeds 135° (π·3/4).
"""
from __future__ import annotations

from math import acos, hypot, pi

import heapq
import networkx as nx
import numpy as np
from scipy.spatial import Delaunay, QhullError


def frame_to_shape_graph(frame: dict) -> nx.Graph:
    """Construct the shape graph for a tracking frame.

    Parameters
    ----------
    frame :
        Mapping of player labels → ``(x, y)`` coordinates. Duplicate
        coordinates are nudged slightly so Delaunay succeeds.

    Returns
    -------
    networkx.Graph
        Undirected shape graph on the same labels.
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

    def tweak_duplicates(frame_in, offset=float(0.000001)):
        unique_coords = set(frame_in.values())
        if offset < float(0.000001):
            offset = float(0.000001)
        while len(unique_coords) != len(frame_in):
            appendix = set()
            for coord in unique_coords:
                m = 0
                for point in frame_in:
                    if frame_in[point] == coord:
                        frame_in[point] = (coord[0] + m * offset, coord[1])
                        if frame_in[point] not in unique_coords:
                            appendix.add(frame_in[point])
                        m += 1
            unique_coords = unique_coords.union(appendix)
        return frame_in

    def prio_lr(e):
        tri_nodes = set(S.neighbors(e[0])) & set(S.neighbors(e[1]))
        prio_l, prio_r = 1, 1
        for r in tri_nodes:
            rp, rq = vector((r, e[0])), vector((r, e[1]))
            if (rp[0] * rq[1] - rp[1] * rq[0]) < 0:
                if cos_vec(rp, rq) < prio_r:
                    prio_r = cos_vec(rp, rq)
            else:
                if cos_vec(rp, rq) < prio_l:
                    prio_l = cos_vec(rp, rq)
        return prio_l, prio_r

    def vector(e):
        if e not in vector_cache_dict:
            p, q = e
            vector_cache_dict[e] = (
                frame[q][0] - frame[p][0],
                frame[q][1] - frame[p][1],
            )
            vector_cache_dict[(q, p)] = (
                -vector_cache_dict[e][0],
                -vector_cache_dict[e][1],
            )
        return vector_cache_dict[e]

    def iter_edges(p_start, p_end, v_start):
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

    def update_external_face(e, ext):
        new_edges = set()
        if (e[1], e[0]) in ext:
            new_edges = iter_edges(e[1], e[0], vector((e[1], e[0])))
            ext.remove((e[1], e[0]))
        elif e in ext:
            new_edges = iter_edges(e[0], e[1], vector(e))
            ext.remove(e)
        for new_edge in new_edges:
            ext.add(new_edge)
        return ext

    def is_external_face(face, ext):
        return next(iter(face)) in ext

    def cos_max(e, points):
        P_pq = right_points(e, points)
        alpha = -1
        for r in P_pq:
            if r in e:
                continue
            rp, rq = vector((r, e[0])), vector((r, e[1]))
            prq = cos_vec(rp, rq)
            if prq > alpha:
                alpha = prq
        return alpha

    def right_points(e, points):
        pq = vector(e)
        right = set()
        for r in points:
            if r not in e:
                pr = vector((e[0], r))
                if (pr[1] * pq[0] - pr[0] * pq[1]) < 0:
                    right.add(r)
        return right

    def alpha_pq(e):
        if e in alpha_cache_dict:
            return alpha_cache_dict[e]
        P_pq = right_points(e, frame)
        alpha = 1
        for r in P_pq:
            rp, rq = vector((r, e[0])), vector((r, e[1]))
            prq = cos_vec(rp, rq)
            if prq < alpha:
                alpha = prq
        return alpha

    S = nx.Graph()
    Q = {}
    prio_heap = []
    alpha_cache_dict = {}
    vector_cache_dict = {}

    frame = tweak_duplicates(dict(frame))

    if len(frame) < 3:
        S.add_nodes_from(frame.keys())
        if len(frame) == 2:
            a, b = list(frame.keys())
            S.add_edge(a, b)
        return S

    coords = list(frame.values())
    labels = list(frame.keys())
    indices = {i: labels[i] for i in range(len(labels))}

    try:
        tri = Delaunay(coords)
    except QhullError:
        S.add_nodes_from(labels)
        return S

    for simplex in tri.simplices:
        for i in range(3):
            for j in range(i + 1, 3):
                S.add_edge(indices[simplex[i]], indices[simplex[j]])

    threshold = pi * 3 / 4
    pivot = min(frame, key=lambda p: (frame[p][1], frame[p][0]))
    E = iter_edges(pivot, pivot, (0, -1))

    for e in list(S.edges):
        alpha_cache_dict[(e[1], e[0])], alpha_cache_dict[e] = prio_lr(e)
        prio = acos(alpha_cache_dict[(e[1], e[0])]) + acos(alpha_cache_dict[e])
        if prio > threshold:
            Q[e] = prio
            heapq.heappush(prio_heap, (-prio, e))

    while Q:
        max_Q, e = heapq.heappop(prio_heap)
        max_Q = -max_Q
        if e in Q and Q[e] == max_Q:
            p, q = e[0], e[1]
            S.remove_edge(p, q)
            del Q[e]

            F = iter_edges(p, p, vector(e))
            E = update_external_face(e, E)
            external_face = is_external_face(F, E)

            for e_f in F:
                prio = 0
                if not external_face:
                    F_pts = {edge[0]: frame[edge[0]] for edge in F}
                    prio_new = cos_max(e_f, F_pts)
                    alpha_cache_dict[e_f] = prio_new
                    prio += acos(prio_new)

                prio += acos(alpha_pq((e_f[1], e_f[0])))
                e_f = (e_f[1], e_f[0]) if (e_f[1], e_f[0]) in Q else e_f
                Q[e_f] = prio
                if prio <= threshold:
                    del Q[e_f]
                else:
                    heapq.heappush(prio_heap, (-prio, e_f))

    return S


def points_to_shape_edges(points: np.ndarray) -> nx.Graph:
    """Shape graph for an ``(K, 2)`` point array; nodes are ``0..K-1``."""
    frame = {i: (float(points[i, 0]), float(points[i, 1])) for i in range(len(points))}
    return frame_to_shape_graph(frame)
