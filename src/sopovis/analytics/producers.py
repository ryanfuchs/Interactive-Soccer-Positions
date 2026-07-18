"""Analytics producers — plug-in point for new derived data.

Mirror image of ``render.registry.ElementRegistry`` on the data side: a
producer turns a ``MatchState`` (plus previously computed products) into one
named *product* stored on the bundle. Adding an analytic:

    1. subclass Producer, set ``name``/``version``, implement compute()
    2. registry.register(MyProducer())
    3. read it anywhere via ``bundle.product("my_product")``

Products are cached on disk per producer (see ``bundle.cache``); bump
``version`` (or change ``params``) to invalidate a single product's cache
without touching the others.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterator

import numpy as np

from sopovis.analytics.pipeline import (
    RoleResult,
    _progress,
    aggregate_roles,
    frame_roles,
    frame_shape_edges,
    infer_attack_directions,
    outfield_columns,
)
from sopovis.analytics.roles import UNSET
from sopovis.model.state import MatchState


class Producer(ABC):
    """One named analytics product computed over the analytics-frame grid."""

    name: str
    version: int = 1
    #: Products that must be computed first; passed to compute() via ``deps``.
    requires: tuple[str, ...] = ()
    #: Tunables that affect the result — part of the cache key.
    params: dict[str, Any] = {}

    @abstractmethod
    def compute(
        self,
        state: MatchState,
        deps: dict[str, Any],
        stride: int,
        progress: bool = False,
    ) -> Any: ...

    def cache_token(self, stride: int) -> str:
        """Uniquely identifies this producer's output for a given config."""
        params = ",".join(f"{k}={v}" for k, v in sorted(self.params.items()))
        return f"{self.name}:v{self.version}:stride={stride}:{params}"


class ProducerRegistry:
    def __init__(self) -> None:
        self._producers: dict[str, Producer] = {}

    def register(self, producer: Producer) -> None:
        self._producers[producer.name] = producer

    def get(self, name: str) -> Producer:
        if name not in self._producers:
            raise KeyError(
                f"unknown product {name!r}; registered: {sorted(self._producers)}"
            )
        return self._producers[name]

    @property
    def names(self) -> list[str]:
        return sorted(self._producers)


# ------------------------------------------------------- iteration helper


def iter_team_frames(
    state: MatchState, stride: int, team_id: str
) -> Iterator[tuple[int, int, np.ndarray, list[int]]]:
    """Yield ``(ta, t, points, columns)`` per analytics frame for one team.

    ``points`` are the (K, 2) positions of the *present* outfield players and
    ``columns`` their MatchState columns.
    """
    cols = outfield_columns(state, team_id)
    for ta, t in enumerate(range(0, state.total_frames, stride)):
        xy = state.frames[t, cols, :2]
        present = np.isfinite(xy).all(axis=1)
        yield ta, t, xy[present], [c for c, p in zip(cols, present) if p]


# --------------------------------------------------------- built-in producers


class AttackDirectionsProducer(Producer):
    """(team_id, section) → attacking toward +y (away from the reference goal)."""

    name = "attack_directions"
    version = 2  # v2: goal-aligned coordinate frame

    def compute(self, state, deps, stride, progress=False):
        return infer_attack_directions(state)


class ShapeGraphProducer(Producer):
    """team_id → per-analytics-frame (E, 2) edge arrays (tactical adjacency)."""

    name = "shape_graph"
    version = 2  # v2: goal-aligned coordinate frame

    def compute(self, state, deps, stride, progress=False):
        edges: dict[str, list[np.ndarray]] = {}
        for tid in (state.meta.home_team_id, state.meta.guest_team_id):
            iterator = iter_team_frames(state, stride, tid)
            if progress:
                total = (state.total_frames + stride - 1) // stride
                iterator = _progress(iterator, total)
            edges[tid] = [
                frame_shape_edges(points, columns)
                for _ta, _t, points, columns in iterator
            ]
        return edges


class RolesProducer(Producer):
    """Tactical roles per analytics frame + temporal aggregation (RoleResult)."""

    name = "roles"
    version = 2  # v2: goal-aligned coordinate frame
    requires = ("attack_directions",)

    def compute(self, state, deps, stride, progress=False) -> RoleResult:
        directions = deps["attack_directions"]
        ta_total = (state.total_frames + stride - 1) // stride
        n = len(state.player_ids)

        roles = np.full((ta_total, n, 2), UNSET, dtype=np.int8)
        presence = np.zeros((ta_total, n), dtype=bool)

        for tid in (state.meta.home_team_id, state.meta.guest_team_id):
            iterator = iter_team_frames(state, stride, tid)
            if progress:
                iterator = _progress(iterator, ta_total)
            for ta, t, points, columns in iterator:
                if not columns:
                    continue
                section = state.section_of(t)
                cols = np.asarray(columns, dtype=np.int32)
                roles[ta, cols] = frame_roles(points, directions[(tid, section)])
                presence[ta, cols] = True

        return aggregate_roles(state, roles, presence)


class ProximityEdgesProducer(Producer):
    """team_id → per-analytics-frame (E, 2) edges between nearby teammates.

    Deliberately simple; exists to demonstrate that a new relation product
    plus one preset line yields a new overlay with zero render-code changes.
    """

    name = "proximity"
    version = 2  # v2: goal-aligned coordinate frame
    params = {"max_distance_m": 12.0}

    def compute(self, state, deps, stride, progress=False):
        from scipy.spatial.distance import pdist, squareform

        limit = float(self.params["max_distance_m"])
        edges: dict[str, list[np.ndarray]] = {}
        for tid in (state.meta.home_team_id, state.meta.guest_team_id):
            per_frame: list[np.ndarray] = []
            for _ta, _t, points, columns in iter_team_frames(state, stride, tid):
                if len(points) < 2:
                    per_frame.append(np.empty((0, 2), dtype=np.int32))
                    continue
                close = squareform(pdist(points)) < limit
                a, b = np.nonzero(np.triu(close, k=1))
                cols = np.asarray(columns, dtype=np.int32)
                per_frame.append(np.column_stack([cols[a], cols[b]]).astype(np.int32))
            edges[tid] = per_frame
        return edges


def default_producer_registry() -> ProducerRegistry:
    registry = ProducerRegistry()
    for producer in (
        AttackDirectionsProducer(),
        ShapeGraphProducer(),
        RolesProducer(),
        ProximityEdgesProducer(),
    ):
        registry.register(producer)
    return registry
