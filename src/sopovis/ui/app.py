"""AppController — wires the three coordinated views through FrameCursor.

Control flow:

    scrub/click/play ──► TimelineControlView.on_scrub ──► FrameCursor.set
                                                            │
                                    ┌───────────────────────┴───────┐
                                    ▼                               ▼
                     PositionPlotView.on_cursor_change   PitchAnimationView.on_cursor_change

Position-plot clicks request a seek through the timeline — they never set
the cursor directly.
"""
from __future__ import annotations

from matplotlib.figure import Figure

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.presets import Preset
from sopovis.render.registry import ElementRegistry, default_registry
from sopovis.render.scene import SceneBuilder
from sopovis.ui.cursor import FrameCursor
from sopovis.ui.hover import HoverLink
from sopovis.ui.pitch_view import PitchAnimationView
from sopovis.ui.position_plot import PositionPlotView
from sopovis.ui.timeline import TimelineControlView


class AppController:
    def __init__(
        self,
        bundle: PrecomputedBundle,
        preset: Preset,
        fig_timeline: Figure,
        fig_plot: Figure,
        fig_pitch: Figure,
        registry: ElementRegistry | None = None,
    ):
        self.bundle = bundle
        self.registry = registry or default_registry()
        self.cursor = FrameCursor(t=0)
        self.hover = HoverLink()

        self.timeline = TimelineControlView(self.cursor, bundle, fig_timeline)
        self.position_plot = PositionPlotView(self.cursor, bundle, fig_plot)
        scene = SceneBuilder(self.registry).build(preset.layers, bundle)
        self.pitch = PitchAnimationView(self.cursor, bundle, scene, fig_pitch)

        self.position_plot.bind_hover(self.hover)
        self.pitch.bind_hover(self.hover)

        self.cursor.subscribe(self.position_plot.on_cursor_change)
        self.cursor.subscribe(self.pitch.on_cursor_change)
        self.position_plot.request_seek = self.timeline.on_scrub

    def on_preset_change(self, preset: Preset) -> None:
        scene = SceneBuilder(self.registry).build(preset.layers, self.bundle)
        self.pitch.set_scene(scene)

    def toggle_layer(self, name: str, enabled: bool) -> None:
        self.pitch.toggle_layer(name, enabled)
