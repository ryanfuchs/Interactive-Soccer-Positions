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

from typing import Callable

from matplotlib.figure import Figure

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.presets import Preset
from sopovis.config.settings import UserSettings, load_settings
from sopovis.render.registry import ElementRegistry, default_registry
from sopovis.render.scene import SceneBuilder
from sopovis.render.timeline import (
    DEFAULT_TIMELINE_LAYERS,
    TimelineElementRegistry,
    TimelineStack,
    TimelineStackBuilder,
    default_timeline_registry,
)
from sopovis.ui.cursor import FrameCursor
from sopovis.ui.hover import HoverLink
from sopovis.ui.pitch_view import PitchAnimationView
from sopovis.ui.position_plot import PositionPlotView
from sopovis.ui.time_window import ViewTimeRange, auto_resolution
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
        timeline_registry: TimelineElementRegistry | None = None,
        settings: UserSettings | None = None,
    ):
        self.bundle = bundle
        self.settings = settings or load_settings()
        self.registry = registry or default_registry()
        self.timeline_registry = timeline_registry or default_timeline_registry()
        self.cursor = FrameCursor(t=0)
        self.hover = HoverLink()
        self.view_range = ViewTimeRange(bundle)
        self.on_view_changed: list[Callable[[], None]] = []

        self.timeline = TimelineControlView(
            self.cursor,
            bundle,
            self._build_timeline_stack(preset),
            fig_timeline,
            view_range=self.view_range,
            min_zoom_seconds=self.settings.min_zoom_seconds,
            on_span_zoom=self.set_zoom,
            on_span_reset=self.reset_zoom,
        )
        self.position_plot = PositionPlotView(
            self.cursor,
            bundle,
            fig_plot,
            view_range=self.view_range,
            resolution=self.settings.default_resolution,
            min_zoom_seconds=self.settings.min_zoom_seconds,
            on_span_zoom=self.set_zoom,
            on_span_reset=self.reset_zoom,
        )
        scene = SceneBuilder(self.registry).build(preset.layers, bundle)
        self.pitch = PitchAnimationView(self.cursor, bundle, scene, fig_pitch)

        self.position_plot.bind_hover(self.hover)
        self.pitch.bind_hover(self.hover)

        self.cursor.subscribe(self.position_plot.on_cursor_change)
        self.cursor.subscribe(self.pitch.on_cursor_change)
        self.position_plot.request_seek = self.timeline.on_scrub

    def _build_timeline_stack(self, preset: Preset) -> TimelineStack:
        specs = preset.timeline or DEFAULT_TIMELINE_LAYERS
        return TimelineStackBuilder(self.timeline_registry).build(specs, self.bundle)

    def on_preset_change(self, preset: Preset) -> None:
        scene = SceneBuilder(self.registry).build(preset.layers, self.bundle)
        self.pitch.set_scene(scene)
        self.timeline.set_stack(self._build_timeline_stack(preset))

    def toggle_layer(self, name: str, enabled: bool) -> None:
        self.pitch.toggle_layer(name, enabled)

    def toggle_timeline_layer(self, name: str, enabled: bool) -> None:
        self.timeline.set_layer_enabled(name, enabled)

    def set_home_at_bottom(self, home_at_bottom: bool) -> None:
        self.pitch.set_home_at_bottom(home_at_bottom)
        self.position_plot.set_home_at_bottom(home_at_bottom)

    def set_period(self, period: str | None) -> None:
        self.view_range.set_period(period)
        self.timeline.set_period(period)
        self.position_plot.set_period(period)
        self._apply_view_change()

    def set_zoom(self, start: int, end: int) -> bool:
        if not self.view_range.set_zoom(start, end, self.settings.min_zoom_seconds):
            return False
        self._apply_view_change()
        return True

    def reset_zoom(self) -> None:
        if not self.view_range.is_zoomed:
            return
        self.view_range.reset_zoom()
        self._apply_view_change()

    def set_resolution(self, resolution: int) -> None:
        self.position_plot.set_resolution(resolution)

    def _apply_view_change(self) -> None:
        t0, t1 = self.view_range.limits()
        if self.settings.auto_resolution_on_zoom:
            res = auto_resolution(self.settings, self.bundle, t0, t1)
            self.position_plot.set_resolution(res)
        else:
            self.position_plot.apply_view_range()
        self.timeline.apply_view_range()
        t = max(t0, min(self.cursor.t, t1 - 1))
        self.timeline.on_scrub(t)
        for cb in self.on_view_changed:
            cb()
