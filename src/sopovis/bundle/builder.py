"""BundleBuilder — MatchState → PrecomputedBundle."""
from __future__ import annotations

from sopovis.analytics.pipeline import (
    ShapeGraphBuilder,
    TacticalPositionInferer,
    infer_attack_directions,
)
from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.model.state import MatchState


class BundleBuilder:
    def __init__(self, analytics_stride: int = 5):
        self.analytics_stride = analytics_stride

    def build(self, state: MatchState, progress: bool = False) -> PrecomputedBundle:
        if progress:
            n = (state.total_frames + self.analytics_stride - 1) // self.analytics_stride
            print(
                f"      Shape graphs + roles over {n:,} analytics frames "
                f"(stride={self.analytics_stride}, 2 teams) …",
                flush=True,
            )

        # 1. shape graphs (+ per-frame roles inside the same pass)
        builder = ShapeGraphBuilder(stride=self.analytics_stride)
        shape_result = builder.run(state, progress=progress)

        if progress:
            print("      Aggregating role histograms and player rows …", flush=True)

        # 2. tactical roles (temporal aggregation)
        role_result = TacticalPositionInferer().run(state, shape_result, builder)

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
            analytics_frame_indices=shape_result.frame_indices,
            shape_edges=shape_result.edges,
            tactical_roles=role_result.tactical_roles,
            role_counts=role_result.role_counts,
            player_row_order=role_result.player_row_order,
            substitution_frames=role_result.substitution_frames,
            attack_directions=infer_attack_directions(state),
        )


def build_bundle(
    state: MatchState,
    analytics_stride: int = 5,
    cache_dir: str | None = ".cache",
    progress: bool = True,
    verbose: bool = False,
) -> PrecomputedBundle:
    """Build a bundle, using the disk cache when source and config match."""
    from sopovis.bundle.cache import BundleCache

    def _v(msg: str) -> None:
        if verbose:
            print(msg, flush=True)

    if cache_dir is None:
        _v("      Cache disabled — computing from scratch …")
        return BundleBuilder(analytics_stride).build(state, progress=progress)

    cache = BundleCache(cache_dir)
    cached = cache.load(state, analytics_stride)
    if cached is not None:
        _v(f"      Cache hit ({cache_dir}/{state.meta.match_id})")
        return cached

    _v("      Cache miss — this can take several minutes on first run …")
    bundle = BundleBuilder(analytics_stride).build(state, progress=progress)
    _v(f"      Saving cache → {cache_dir}/{state.meta.match_id}")
    cache.save(bundle, state)
    return bundle
