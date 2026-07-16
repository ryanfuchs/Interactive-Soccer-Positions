"""Preset configuration — YAML layer stacks + styles."""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

#: Directory shipped with the repository containing the default presets.
BUILTIN_PRESET_DIR = Path(__file__).resolve().parents[3] / "presets"


class LayerSpec(BaseModel):
    name: str
    type: str  # registered element class name
    z_order: int
    display_name: str | None = None  # UI label; defaults to title-cased name
    category: str | None = None
    enabled: bool = True
    style: dict = Field(default_factory=dict)  # passed to element constructor

    def ui_label(self) -> str:
        if self.display_name:
            return self.display_name
        return self.name.replace("_", " ").title()


class Preset(BaseModel):
    name: str = "unnamed"
    styles: dict = Field(default_factory=dict)  # global style defaults per group
    layers: list[LayerSpec]
    timeline: list[LayerSpec] = Field(default_factory=list)  # empty → default stack
    position: list[LayerSpec] = Field(default_factory=list)  # empty → default stack


def load_preset(path: str | Path) -> Preset:
    path = Path(path)
    with open(path) as f:
        data = yaml.safe_load(f)
    data.setdefault("name", path.stem)
    return Preset.model_validate(data)


def find_presets(directory: str | Path) -> dict[str, Path]:
    """name → path for all YAML presets in a directory."""
    directory = Path(directory)
    return {p.stem: p for p in sorted(directory.glob("*.yaml"))}
