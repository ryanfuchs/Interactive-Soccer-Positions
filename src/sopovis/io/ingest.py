"""IngestionController — DFL XML triplet → MatchState."""
from __future__ import annotations

from pathlib import Path

from sopovis.io.events import EventLoader
from sopovis.io.files import MatchFileSet, file_set_for
from sopovis.io.metadata import MetadataLoader
from sopovis.io.tracking import TrackingDataLoader
from sopovis.model.state import MatchState


class IngestionController:
    def load_match(self, files: MatchFileSet) -> MatchState:
        files.validate()
        meta_info = MetadataLoader().load(files.metadata)
        track = TrackingDataLoader(files.metadata).load(files.tracking, meta_info)
        events = EventLoader().load(
            files.events,
            files.metadata,
            section_ranges=track.section_ranges,
            frame_rate=track.frame_rate,
            pitch_length=meta_info.meta.pitch_length,
        )
        return MatchState.from_parts(meta_info, events, track)


def load_match(directory: str | Path, match_id: str) -> MatchState:
    """Convenience entry point: scan directory, load one match by id."""
    return IngestionController().load_match(file_set_for(directory, match_id))
