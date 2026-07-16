"""BundleBuilder — MatchState → PrecomputedBundle via registered producers.

Core products are computed eagerly so the UI opens fully populated; every
other registered product is computed lazily on first ``bundle.product(name)``
access. Both paths share the same per-product disk cache.
"""
from __future__ import annotations

from typing import Any

from sopovis.analytics.producers import (
    ProducerRegistry,
    default_producer_registry,
)
from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.bundle.cache import ProductCache
from sopovis.model.state import MatchState

#: Products required by the default presets' always-on layers.
CORE_PRODUCTS = ("attack_directions", "shape_graph", "roles")


class ProductSupplier:
    """Resolves a product name to a value: cache hit or compute (with deps)."""

    def __init__(
        self,
        state: MatchState,
        registry: ProducerRegistry,
        stride: int,
        cache: ProductCache | None = None,
        progress: bool = False,
    ):
        self.state = state
        self.registry = registry
        self.stride = stride
        self.cache = cache
        self.progress = progress

    def get(self, name: str, memo: dict[str, Any]) -> Any:
        producer = self.registry.get(name)
        if self.cache is not None:
            cached = self.cache.load(self.state, producer, self.stride)
            if cached is not None:
                return cached

        deps: dict[str, Any] = {}
        for dep in producer.requires:
            if dep not in memo:
                memo[dep] = self.get(dep, memo)
            deps[dep] = memo[dep]
        if self.progress:
            print(f"      Computing {name!r} …", flush=True)
        value = producer.compute(self.state, deps, self.stride, progress=self.progress)

        if self.cache is not None:
            self.cache.save(self.state, producer, self.stride, value)
        return value


class BundleBuilder:
    def __init__(
        self,
        analytics_stride: int = 5,
        registry: ProducerRegistry | None = None,
        cache: ProductCache | None = None,
    ):
        self.analytics_stride = analytics_stride
        self.registry = registry or default_producer_registry()
        self.cache = cache

    def build(self, state: MatchState, progress: bool = False) -> PrecomputedBundle:
        supplier = ProductSupplier(
            state, self.registry, self.analytics_stride, self.cache, progress
        )
        products: dict[str, Any] = {}
        for name in CORE_PRODUCTS:
            if name not in products:
                products[name] = supplier.get(name, products)

        return PrecomputedBundle(
            frames=state.frames,
            ball=state.ball,
            ball_possession=state.ball_possession,
            player_ids=state.player_ids,
            player_registry=state.player_registry,
            team_map=state.team_map,
            events=state.events,
            event_index=state.event_index,
            section_ranges=state.section_ranges,
            frame_rate=state.frame_rate,
            meta=state.meta,
            teams=state.teams,
            analytics_stride=self.analytics_stride,
            products=products,
            supplier=supplier,
        )


def build_bundle(
    state: MatchState,
    analytics_stride: int = 5,
    cache_dir: str | None = ".cache",
    progress: bool = True,
    verbose: bool = False,
) -> PrecomputedBundle:
    """Build a bundle, using the per-product disk cache when available."""
    cache = ProductCache(cache_dir) if cache_dir is not None else None
    if verbose and cache is None:
        print("      Cache disabled — computing from scratch …", flush=True)
    return BundleBuilder(analytics_stride, cache=cache).build(state, progress=progress)
