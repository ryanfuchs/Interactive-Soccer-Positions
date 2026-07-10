"""Backward-compatible re-exports — prefer ``sopovis.render.timeline``."""
from sopovis.render.timeline import (
    DEFAULT_TIMELINE_LAYERS,
    TIMELINE_BG,
    TimelineElement,
    TimelineElementRegistry,
    TimelineStackBuilder,
    default_geometry,
    default_timeline_registry,
)


def build_timeline_elements(layer_specs, bundle, registry=None):
    """Legacy helper — use ``TimelineStackBuilder`` instead."""
    reg = registry or default_timeline_registry()
    return TimelineStackBuilder(reg).build(layer_specs, bundle).elements


__all__ = [
    "DEFAULT_TIMELINE_LAYERS",
    "TIMELINE_BG",
    "TimelineElement",
    "TimelineElementRegistry",
    "build_timeline_elements",
    "default_geometry",
    "default_timeline_registry",
]
