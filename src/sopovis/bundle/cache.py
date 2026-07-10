"""Disk cache for precomputed analytics.

Only the analytics outputs are cached (shape edges, roles, counts, ordering);
the large pass-through arrays are rebuilt from MatchState, which keeps cache
files ~100 MB instead of ~400 MB.
"""
from __future__ import annotations

import hashlib
import pickle
import time
from dataclasses import dataclass
from pathlib import Path

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.model.state import MatchState

_CACHE_VERSION = 3  # zeilenweise row order with shirt-number tiebreak


@dataclass
class BundleManifest:
    source_hash: str
    config_hash: str
    created_at: float
    version: int = _CACHE_VERSION


def _source_hash(state: MatchState) -> str:
    key = f"{state.meta.match_id}:{state.total_frames}:{len(state.player_ids)}"
    return hashlib.sha256(key.encode()).hexdigest()


def _config_hash(stride: int) -> str:
    return hashlib.sha256(f"stride={stride}:v={_CACHE_VERSION}".encode()).hexdigest()


class BundleCache:
    def __init__(self, directory: str | Path = ".cache"):
        self.directory = Path(directory)

    def _paths(self, state: MatchState) -> tuple[Path, Path]:
        base = self.directory / state.meta.match_id
        return base.with_suffix(".manifest.pkl"), base.with_suffix(".analytics.pkl")

    def load(self, state: MatchState, stride: int) -> PrecomputedBundle | None:
        manifest_path, data_path = self._paths(state)
        if not (manifest_path.is_file() and data_path.is_file()):
            return None
        try:
            with open(manifest_path, "rb") as f:
                manifest: BundleManifest = pickle.load(f)
            if (
                manifest.version != _CACHE_VERSION
                or manifest.source_hash != _source_hash(state)
                or manifest.config_hash != _config_hash(stride)
            ):
                return None
            with open(data_path, "rb") as f:
                analytics = pickle.load(f)
        except (pickle.PickleError, EOFError, OSError, ModuleNotFoundError, AttributeError):
            return None

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
            **analytics,
        )

    def save(self, bundle: PrecomputedBundle, state: MatchState) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        manifest_path, data_path = self._paths(state)
        analytics = {
            "analytics_stride": bundle.analytics_stride,
            "analytics_frame_indices": bundle.analytics_frame_indices,
            "shape_edges": bundle.shape_edges,
            "tactical_roles": bundle.tactical_roles,
            "role_counts": bundle.role_counts,
            "player_row_order": bundle.player_row_order,
            "substitution_frames": bundle.substitution_frames,
            "attack_directions": bundle.attack_directions,
        }
        manifest = BundleManifest(
            source_hash=_source_hash(state),
            config_hash=_config_hash(bundle.analytics_stride),
            created_at=time.time(),
        )
        with open(data_path, "wb") as f:
            pickle.dump(analytics, f, protocol=pickle.HIGHEST_PROTOCOL)
        with open(manifest_path, "wb") as f:
            pickle.dump(manifest, f, protocol=pickle.HIGHEST_PROTOCOL)
