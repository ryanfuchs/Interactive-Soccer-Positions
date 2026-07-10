"""Default timeline layer stack when a preset omits ``timeline:``."""
from __future__ import annotations

from sopovis.config.presets import LayerSpec

DEFAULT_TIMELINE_LAYERS: list[LayerSpec] = [
    LayerSpec(
        name="possession",
        display_name="Possession",
        type="PossessionChart",
        z_order=2,
        enabled=False,
        style={"window_seconds": 90, "linewidth": 1.5},
    ),
    LayerSpec(name="lanes", display_name="Lanes", type="LaneFurniture", z_order=4),
    LayerSpec(name="sections", display_name="Periods", type="SectionBoundaries", z_order=6),
    LayerSpec(
        name="whistles",
        display_name="Whistles",
        type="EventMarkers",
        z_order=10,
        style={"kinds": ["whistle"]},
    ),
    LayerSpec(
        name="cards",
        display_name="Cards",
        type="EventMarkers",
        z_order=12,
        style={"kinds": ["card"]},
    ),
    LayerSpec(
        name="subs",
        display_name="Substitutions",
        type="EventMarkers",
        z_order=14,
        style={"kinds": ["sub"]},
    ),
    LayerSpec(name="shots", display_name="Shots & goals", type="ShotMarkers", z_order=16),
]
