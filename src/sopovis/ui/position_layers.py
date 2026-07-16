"""Backward-compatible re-exports — prefer ``sopovis.render.position``."""
from sopovis.render.position import (
    DEFAULT_POSITION_LAYERS,
    PositionContext,
    PositionElement,
    PositionElementRegistry,
    PositionStack,
    PositionStackBuilder,
    RowBand,
    default_position_registry,
)

__all__ = [
    "DEFAULT_POSITION_LAYERS",
    "PositionContext",
    "PositionElement",
    "PositionElementRegistry",
    "PositionStack",
    "PositionStackBuilder",
    "RowBand",
    "default_position_registry",
]
