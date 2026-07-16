"""PrecomputedBundle — immutable data container for render-time O(1) lookups.

Analytics live in ``products``, a name → value map filled by registered
producers (``analytics.producers``). Core products are computed eagerly at
build time; anything else is computed (and disk-cached) on first access via
``product(name)`` — enabling a layer therefore triggers exactly the analytics
it needs, once.

Analytics are computed on a strided subsample of frames ("analytics frames").
`to_analytics_frame(t)` maps a tracking frame index to the nearest analytics
frame. Shape graphs are stored as compact per-frame edge arrays (player column
pairs); `shape_graph_nx()` materialises a networkx.Graph on demand.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from sopovis.model.events import EventMoment
from sopovis.model.meta import MatchMeta, PlayerMeta, TeamMeta


@dataclass
class PrecomputedBundle:
    # pass-through from MatchState
    frames: np.ndarray  # (T, N, 5)
    ball: np.ndarray  # (T, 4)
    ball_possession: np.ndarray  # (T,)
    player_ids: list[str]
    player_registry: dict[str, PlayerMeta]
    team_map: dict[str, str]
    events: list[EventMoment]
    event_index: dict[int, list[EventMoment]]
    section_ranges: dict[str, tuple[int, int]]
    frame_rate: float
    meta: MatchMeta
    teams: dict[str, TeamMeta]  # team_id → TeamMeta (colors, names)

    # analytics (strided subsample)
    analytics_stride: int
    products: dict[str, Any] = field(default_factory=dict)
    #: Computes missing products on demand (None → products is exhaustive).
    supplier: Any = field(default=None, repr=False, compare=False)

    player_index: dict[str, int] = field(init=False)
    analytics_frame_indices: np.ndarray = field(init=False)  # (Ta,)

    def __post_init__(self) -> None:
        self.player_index = {pid: i for i, pid in enumerate(self.player_ids)}
        self.analytics_frame_indices = np.arange(
            0, self.total_frames, self.analytics_stride
        )

    # -------------------------------------------------------------- products

    def product(self, name: str) -> Any:
        """Analytics product by name; computed lazily (and cached) if absent."""
        if name not in self.products:
            if self.supplier is None:
                raise KeyError(f"product {name!r} not computed and no supplier set")
            self.products[name] = self.supplier.get(name, self.products)
        return self.products[name]

    # typed views onto core products (kept for convenience and old call sites)

    @property
    def shape_edges(self) -> dict[str, list[np.ndarray]]:
        return self.product("shape_graph")

    @property
    def tactical_roles(self) -> np.ndarray:  # (Ta, N, 2) int8
        return self.product("roles").tactical_roles

    @property
    def role_counts(self) -> np.ndarray:  # (Ta, N, 25) int32 cumulative
        return self.product("roles").role_counts

    @property
    def player_row_order(self) -> dict[str, int]:
        return self.product("roles").player_row_order

    @property
    def substitution_frames(self) -> list[int]:
        return self.product("roles").substitution_frames

    @property
    def attack_directions(self) -> dict[tuple[str, str], bool]:
        return self.product("attack_directions")

    # ------------------------------------------------------------------ time

    @property
    def total_frames(self) -> int:
        return self.frames.shape[0]

    @property
    def total_analytics_frames(self) -> int:
        return len(self.analytics_frame_indices)

    def to_analytics_frame(self, t: int) -> int:
        ta = int(t) // self.analytics_stride
        return min(max(ta, 0), self.total_analytics_frames - 1)

    def section_of(self, t: int) -> str:
        for name, (lo, hi) in self.section_ranges.items():
            if lo <= t < hi:
                return name
        return "firstHalf"

    # ------------------------------------------------------------- accessors

    def positions(self, t: int) -> np.ndarray:
        return self.frames[t]  # (N, 5)

    def ball_at(self, t: int) -> np.ndarray:
        return self.ball[t]  # (4,)

    def roles_at(self, t: int) -> np.ndarray:
        return self.tactical_roles[self.to_analytics_frame(t)]  # (N, 2)

    def edges_at(self, t: int, relation: str, team_id: str) -> np.ndarray:
        """(E, 2) edges of any edge-valued product ("relation") at frame t."""
        return self.product(relation)[team_id][self.to_analytics_frame(t)]

    def shape_edges_at(self, t: int, team_id: str) -> np.ndarray:
        return self.edges_at(t, "shape_graph", team_id)  # (E, 2)

    def shape_graph_nx(self, t: int, team_id: str):
        import networkx as nx

        g = nx.Graph()
        g.add_edges_from(map(tuple, self.shape_edges_at(t, team_id)))
        return g

    def events_at(self, t: int) -> list[EventMoment]:
        return self.event_index.get(t, [])

    def team_columns(self, team_id: str) -> list[int]:
        return [
            i
            for i, pid in enumerate(self.player_ids)
            if self.team_map.get(pid) == team_id
        ]

    def clock_label(self, t: int) -> str:
        """MM:SS match clock with 45:00 offset in the second half."""
        section = self.section_of(t)
        lo, _hi = self.section_ranges[section]
        seconds = (t - lo) / self.frame_rate
        if section == "secondHalf":
            seconds += 45 * 60
        elif section == "firstHalfExtra":
            seconds += 90 * 60
        elif section == "secondHalfExtra":
            seconds += 105 * 60
        m, s = divmod(int(seconds), 60)
        return f"{m:02d}:{s:02d}"
