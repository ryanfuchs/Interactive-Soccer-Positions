"""Match file discovery — group DFL XML triplets by MatchId."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_FILE_RE = re.compile(
    r"DFL_(?P<type>\d{2}_\d{2})_(?P<feed>[a-z_]+)_(?P<comp>DFL-COM-\d+)_(?P<match>DFL-MAT-\w+)\.xml"
)

_TYPE_TO_FIELD = {
    "02_01": "metadata",
    "03_02": "events",
    "04_03": "tracking",
}


@dataclass(frozen=True)
class MatchFileSet:
    match_id: str
    metadata: Path  # 02_01 matchinformation
    events: Path  # 03_02 events_raw
    tracking: Path  # 04_03 positions_raw_observed

    def validate(self) -> None:
        for name in ("metadata", "events", "tracking"):
            path: Path = getattr(self, name)
            if path is None or not path.is_file():
                raise FileNotFoundError(
                    f"{self.match_id}: missing {name} file ({path})"
                )


def discover_matches(directory: str | Path) -> dict[str, dict[str, Path]]:
    """Scan a directory and group DFL files by MatchId.

    Returns match_id → {"metadata": Path, "events": Path, "tracking": Path}
    (keys present only for files found — some matches lack tracking).
    """
    directory = Path(directory)
    groups: dict[str, dict[str, Path]] = {}
    for path in sorted(directory.glob("*.xml")):
        m = _FILE_RE.match(path.name)
        if not m:
            continue
        field = _TYPE_TO_FIELD.get(m.group("type"))
        if field is None:
            continue
        groups.setdefault(m.group("match"), {})[field] = path
    return groups


def file_set_for(directory: str | Path, match_id: str) -> MatchFileSet:
    """Build a validated MatchFileSet for one match in a directory."""
    groups = discover_matches(directory)
    if match_id not in groups:
        raise FileNotFoundError(f"no DFL files for {match_id} in {directory}")
    parts = groups[match_id]
    missing = {"metadata", "events", "tracking"} - parts.keys()
    if missing:
        raise FileNotFoundError(f"{match_id}: incomplete triplet, missing {sorted(missing)}")
    fs = MatchFileSet(match_id=match_id, **parts)
    fs.validate()
    return fs
