"""Config-driven timeline overlays — layered rendering on the event strip.

Vertical placement uses named *bands* (``full``, ``home``, ``away``); see
``geometry`` for layout constants. Layers are registered via
``TimelineElementRegistry`` and listed under ``timeline:`` in preset YAML.
"""
from sopovis.render.timeline.defaults import DEFAULT_TIMELINE_LAYERS
from sopovis.render.timeline.elements import HoverTarget, TimelineElement
from sopovis.render.timeline.geometry import TIMELINE_BG, TimelineGeometry, default_geometry
from sopovis.render.timeline.layers import (
    EventMarkers,
    LaneFurniture,
    PossessionChart,
    SectionBoundaries,
    ShotMarkers,
)
from sopovis.render.timeline.registry import TimelineElementRegistry, default_timeline_registry
from sopovis.render.timeline.stack import TimelineStack, TimelineStackBuilder

__all__ = [
    "DEFAULT_TIMELINE_LAYERS",
    "EventMarkers",
    "HoverTarget",
    "LaneFurniture",
    "PossessionChart",
    "SectionBoundaries",
    "ShotMarkers",
    "TIMELINE_BG",
    "TimelineElement",
    "TimelineElementRegistry",
    "TimelineGeometry",
    "TimelineStack",
    "TimelineStackBuilder",
    "default_geometry",
    "default_timeline_registry",
]
