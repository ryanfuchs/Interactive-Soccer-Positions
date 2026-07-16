"""Pitch layers — static (built once) and dynamic (per-frame) elements.

Counterpart of ``sopovis.render.timeline``; both stacks are registered via
their registries and declared in preset YAML (``layers:`` / ``timeline:``).
"""
from sopovis.render.pitch.dynamic import (
    BallGlyph,
    DefensiveLineOverlay,
    ShapeGraphOverlay,
    ShirtNumberLabel,
    TeamColorGlyph,
    VelocityArrow,
)
from sopovis.render.pitch.static import HalfSpaceLines, PitchMarkings

__all__ = [
    "BallGlyph",
    "DefensiveLineOverlay",
    "HalfSpaceLines",
    "PitchMarkings",
    "ShapeGraphOverlay",
    "ShirtNumberLabel",
    "TeamColorGlyph",
    "VelocityArrow",
]
