"""User preferences — loaded from ``settings.yaml`` at the repository root.

Missing file or missing keys fall back to the defaults below.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import BaseModel

#: Default location: <repo root>/settings.yaml
DEFAULT_SETTINGS_PATH = Path(__file__).resolve().parents[3] / "settings.yaml"


class UserSettings(BaseModel):
    #: Position-analysis bin width (analytics frames per bin) at startup.
    default_resolution: int = 150

    #: Adapt resolution to the visible time window: finer bins when zoomed
    #: in, coarser when zoomed out.
    auto_resolution_on_zoom: bool = True

    #: Approximate number of bins across the visible window when
    #: auto-resolution is active.
    zoom_target_bins: int = 180

    #: Smallest selectable zoom window in seconds (drag selection).
    min_zoom_seconds: float = 5.0

    # --- Startup / session -------------------------------------------------

    #: Layer preset loaded at startup (name of a file in ``presets/``).
    default_preset: str = "tactical"

    #: Folder holding the DFL match XML. ``None`` uses the bundled sample data.
    data_dir: str | None = None

    #: Analytics cache folder. ``None`` disables the on-disk cache.
    cache_dir: str | None = ".cache"

    # --- Playback ----------------------------------------------------------

    #: Playback speed selected at startup (one of 0.5, 1, 2, 4, 8).
    default_playback_speed: float = 1.0

    #: Timer interval between playback steps in milliseconds
    #: (smaller = smoother animation, more CPU).
    play_interval_ms: int = 80

    # --- Default view state ------------------------------------------------

    #: Position-plot team focus at startup: ``home`` | ``both`` | ``away``.
    default_team_focus: str = "both"

    #: Position-plot possession filter at startup:
    #: ``all`` | ``home`` | ``away`` | ``contested``.
    default_possession_filter: str = "all"

    #: Blank position-plot bins where the ball is out of play.
    default_ball_in_play: bool = False

    #: Pitch orientation at startup: home team along the bottom edge.
    default_home_at_bottom: bool = True

    # --- Analytics / resolution bounds ------------------------------------

    #: Tracking-frame stride for the analytics pass. Affects build time and
    #: the cache key (changing it forces a rebuild).
    analytics_stride: int = 5

    #: Lower / upper bounds of the resolution slider (analytics frames per bin).
    min_resolution: int = 5
    max_resolution: int = 600


def load_settings(path: str | Path | None = None) -> UserSettings:
    path = Path(path) if path is not None else DEFAULT_SETTINGS_PATH
    if not path.exists():
        return UserSettings()
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return UserSettings.model_validate(data)


def _yaml_line(key: str, value: object) -> str:
    """One ``key: value`` line, formatted by the YAML dumper (scalars only)."""
    return yaml.safe_dump(
        {key: value}, sort_keys=False, default_flow_style=False, allow_unicode=True
    ).strip()


def save_settings(settings: UserSettings, path: str | Path | None = None) -> None:
    """Write settings back to ``settings.yaml``.

    Existing files are updated in place: the value of each known key is rewritten
    while surrounding comments and layout are preserved; unset (``None``) keys are
    left untouched. A missing file is created from scratch.
    """
    path = Path(path) if path is not None else DEFAULT_SETTINGS_PATH
    data = settings.model_dump(exclude_none=True)
    new_lines = {key: _yaml_line(key, value) for key, value in data.items()}

    if not path.exists():
        header = "# SoPoVis user preferences (written from the UI).\n\n"
        path.write_text(header + yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
        return

    lines = path.read_text().splitlines()
    seen: set[str] = set()
    for i, line in enumerate(lines):
        match = re.match(r"^([A-Za-z_]\w*):", line)
        if match and match.group(1) in new_lines:
            key = match.group(1)
            lines[i] = new_lines[key]
            seen.add(key)

    missing = [key for key in new_lines if key not in seen]
    if missing:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(new_lines[key] for key in missing)

    path.write_text("\n".join(lines) + "\n")
