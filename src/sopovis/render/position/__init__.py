"""Config-driven position overlays — layered rendering on the heatmap.

Layers share a ``PositionContext`` (resolution, filters, bin geometry, time
window) built once per redraw. ``RoleHeatmap`` publishes row bands for hover;
``SubstitutionMarkers`` registers vline artists for emphasis.

Vertical stacking uses ``meta.z_order``; runtime filters (team focus,
possession, in-play) live on the context, not in preset YAML.
"""
from sopovis.render.position.context import PositionContext, RowBand
from sopovis.render.position.defaults import DEFAULT_POSITION_LAYERS
from sopovis.render.position.elements import PositionElement
from sopovis.render.position.filters import (
    POSSESSION_ALL,
    POSSESSION_AWAY,
    POSSESSION_CONTESTED,
    POSSESSION_HOME,
)
from sopovis.render.position.geometry import (
    BIN_VISIBLE_FRAC,
    PLAYER_BAND,
    PLAYER_GAP,
    TEAM_GAP_ROWS,
)
from sopovis.render.position.layers import (
    RoleHeatmap,
    SectionBoundaries,
    SubstitutionMarkers,
)
from sopovis.render.position.registry import (
    PositionElementRegistry,
    default_position_registry,
)
from sopovis.render.position.stack import PositionStack, PositionStackBuilder

__all__ = [
    "DEFAULT_POSITION_LAYERS",
    "PositionContext",
    "PositionElement",
    "PositionElementRegistry",
    "PositionStack",
    "PositionStackBuilder",
    "BIN_VISIBLE_FRAC",
    "PLAYER_BAND",
    "PLAYER_GAP",
    "POSSESSION_ALL",
    "POSSESSION_AWAY",
    "POSSESSION_CONTESTED",
    "POSSESSION_HOME",
    "RoleHeatmap",
    "RowBand",
    "SectionBoundaries",
    "SubstitutionMarkers",
    "TEAM_GAP_ROWS",
    "default_position_registry",
]
