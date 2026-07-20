"""Red zone area chart — per-team filled area in the team lanes."""
from __future__ import annotations

import numpy as np

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.presets import LayerSpec
from sopovis.render.common import meta_from_spec
from sopovis.render.elements import ElementMeta
from sopovis.render.timeline.common import team_label_color
from sopovis.render.timeline.elements import TimelineElement
from sopovis.render.timeline.geometry import DIVIDER_Y, TimelineGeometry


class RedzoneAreaChart(TimelineElement):
    """How big each team's red zone is over the match.

    One filled curve per team lane, both bottom-aligned and growing upward:
    the home curve sits directly on the lane divider line, the away curve on
    the strip bottom, and both spans (divider to strip top, strip bottom to
    divider) are equal, so the two curves share one scale. Undefined zones
    plot as zero. The signal is smoothed with a short rolling mean
    (``window_seconds``) purely for readability; hover targets report the
    smoothed square-metre value.
    """

    def __init__(
        self,
        meta: ElementMeta,
        window_seconds: float = 5.0,
        opacity: float = 0.45,
        linewidth: float = 1.0,
        home_color: str | None = None,
        away_color: str | None = None,
    ):
        super().__init__(meta)
        self.window_seconds = float(window_seconds)
        self.opacity = float(opacity)
        self.linewidth = float(linewidth)
        self.home_color = home_color
        self.away_color = away_color

    @classmethod
    def from_spec(cls, spec: LayerSpec, bundle: PrecomputedBundle) -> "RedzoneAreaChart":
        style = dict(spec.style)
        # Shirt colors can match the strip background (white home shirts);
        # fall back to the secondary color like the lane labels do.
        for key, tid in (
            ("home_color", bundle.meta.home_team_id),
            ("away_color", bundle.meta.guest_team_id),
        ):
            if key not in style:
                team = bundle.teams[tid]
                style[key] = team_label_color(
                    team.shirt_main_color, team.shirt_secondary_color
                )
        return cls(meta_from_spec(spec), **style)

    def _smoothed(self, bundle: PrecomputedBundle, tid: str) -> np.ndarray:
        areas = np.asarray(bundle.product("redzone").areas[tid], dtype=float)
        per_second = bundle.frame_rate / bundle.analytics_stride
        w = max(1, int(self.window_seconds * per_second))
        kernel = np.ones(w) / w
        return np.convolve(areas, kernel, mode="same")

    def build(self, ax, bundle: PrecomputedBundle, geom: TimelineGeometry) -> None:
        self.reset()
        xs = bundle.analytics_frame_indices
        series = {
            "home": (bundle.meta.home_team_id, self.home_color),
            "away": (bundle.meta.guest_team_id, self.away_color),
        }
        smoothed = {
            lane: self._smoothed(bundle, tid) for lane, (tid, _c) in series.items()
        }
        scale = max(float(s.max()) for s in smoothed.values())
        if scale <= 0:
            return

        # Bottom-align both curves: home on the divider, away on the strip
        # bottom. The two spans are equal by construction of the lane layout,
        # so one normalization serves both.
        spans = {
            "home": (DIVIDER_Y, geom.band("home")[1]),
            "away": (geom.band("away")[0], DIVIDER_Y),
        }
        for lane, (tid, color) in series.items():
            y0, y1 = spans[lane]
            values = smoothed[lane] / scale  # 0..1 within the lane
            ys = y0 + values * (y1 - y0)
            fill = ax.fill_between(
                xs, y0, ys, color=color, alpha=self.opacity, linewidth=0
            )
            (line,) = ax.plot(xs, ys, color=color, linewidth=self.linewidth)
            self._register(fill, line)

            step = max(1, len(xs) // 200)
            name = bundle.teams[tid].team_name
            for i in range(0, len(xs), step):
                self._hover_targets.append(
                    (
                        float(xs[i]),
                        float(ys[i]),
                        [f"{name} red zone", f"{smoothed[lane][i]:.0f} m²"],
                    )
                )
