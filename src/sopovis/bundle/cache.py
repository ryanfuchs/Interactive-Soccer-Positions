"""Per-product disk cache for analytics.

One pickle per (match, product): ``.cache/{match_id}.{product}.pkl``. Each
file stores its own key (source hash + the producer's cache token), so
adding or re-versioning one producer never invalidates the others. The large
pass-through arrays are never cached — they are rebuilt from MatchState.
"""
from __future__ import annotations

import hashlib
import pickle
from pathlib import Path
from typing import Any

from sopovis.analytics.producers import Producer
from sopovis.model.state import MatchState


def _source_hash(state: MatchState) -> str:
    key = f"{state.meta.match_id}:{state.total_frames}:{len(state.player_ids)}"
    return hashlib.sha256(key.encode()).hexdigest()


class ProductCache:
    def __init__(self, directory: str | Path = ".cache"):
        self.directory = Path(directory)

    def _path(self, state: MatchState, producer: Producer) -> Path:
        return self.directory / f"{state.meta.match_id}.{producer.name}.pkl"

    def _key(self, state: MatchState, producer: Producer, stride: int) -> str:
        return f"{_source_hash(state)}|{producer.cache_token(stride)}"

    def load(self, state: MatchState, producer: Producer, stride: int) -> Any | None:
        path = self._path(state, producer)
        if not path.is_file():
            return None
        try:
            with open(path, "rb") as f:
                payload = pickle.load(f)
        except (pickle.PickleError, EOFError, OSError, ModuleNotFoundError, AttributeError):
            return None
        if payload.get("key") != self._key(state, producer, stride):
            return None
        return payload["data"]

    def save(
        self, state: MatchState, producer: Producer, stride: int, value: Any
    ) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        payload = {"key": self._key(state, producer, stride), "data": value}
        with open(self._path(state, producer), "wb") as f:
            pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
