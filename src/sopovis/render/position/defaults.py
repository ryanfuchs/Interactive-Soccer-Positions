"""Default position layer stack when a preset omits ``position:``."""
from __future__ import annotations

from sopovis.config.presets import LayerSpec

DEFAULT_POSITION_LAYERS: list[LayerSpec] = [
    LayerSpec(
        name="role_heatmap",
        display_name="Role heatmap",
        type="RoleHeatmap",
        z_order=10,
        category="data",
    ),
    LayerSpec(
        name="sections",
        display_name="Periods",
        type="SectionBoundaries",
        z_order=20,
        category="overlay",
    ),
    LayerSpec(
        name="substitutions",
        display_name="Substitutions",
        type="SubstitutionMarkers",
        z_order=30,
        category="overlay",
    ),
]
