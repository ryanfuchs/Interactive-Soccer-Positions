"""User preferences — loaded from ``settings.yaml`` at the repository root.

Missing file or missing keys fall back to the defaults below.
"""
from __future__ import annotations

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


def load_settings(path: str | Path | None = None) -> UserSettings:
    path = Path(path) if path is not None else DEFAULT_SETTINGS_PATH
    if not path.exists():
        return UserSettings()
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return UserSettings.model_validate(data)
