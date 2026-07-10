"""Possession line chart — signed line across home / away lanes."""
from __future__ import annotations

import numpy as np
from matplotlib.collections import LineCollection

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.presets import LayerSpec
from sopovis.render.common import meta_from_spec
from sopovis.render.elements import ElementMeta
from sopovis.render.timeline.elements import TimelineElement
from sopovis.render.timeline.geometry import DIVIDER_Y, TimelineGeometry


class PossessionChart(TimelineElement):
    """Signed possession line: ``+1`` home, ``-1`` away, ``0`` contested.

    Data source: ``bundle.ball_possession`` (1 = home, 2 = away, 0 = contested).
    Frame values are smoothed with a rolling mean over ``window_seconds`` (default
    90 s), downsampled to one point per second, then mapped to the timeline
    height (home lane up, away lane down, divider at zero).

    The line is **red** while in the home half and **blue** while in the away
    half (colours configurable via ``style``).
    """

    def __init__(
        self,
        meta: ElementMeta,
        window_seconds: float = 90.0,
        linewidth: float = 1.5,
        home_color: str = "#d00000",
        away_color: str = "#215CAF",
    ):
        super().__init__(meta)
        self.window_seconds = float(window_seconds)
        self.linewidth = float(linewidth)
        self.home_color = home_color
        self.away_color = away_color

    @classmethod
    def from_spec(cls, spec: LayerSpec, bundle: PrecomputedBundle) -> "PossessionChart":
        style = dict(spec.style)
        # Legacy preset keys — band/opacity were used by the old area chart.
        style.pop("band", None)
        style.pop("opacity", None)
        if "home_color" not in style:
            style["home_color"] = bundle.teams[bundle.meta.home_team_id].shirt_main_color
        if "away_color" not in style:
            style["away_color"] = bundle.teams[bundle.meta.guest_team_id].shirt_main_color
        return cls(meta_from_spec(spec), **style)

    def _signed_series(self, bundle: PrecomputedBundle) -> tuple[np.ndarray, np.ndarray]:
        poss = np.asarray(bundle.ball_possession, dtype=float)
        values = np.where(poss == 1, 1.0, np.where(poss == 2, -1.0, 0.0))
        w = max(1, int(self.window_seconds * bundle.frame_rate))
        kernel = np.ones(w) / w
        smooth = np.convolve(values, kernel, mode="same")
        step = max(1, int(bundle.frame_rate))  # one point per second
        n = len(smooth)
        xs = np.arange(0, n, step, dtype=int)
        if xs.size == 0 or xs[-1] != n - 1:
            xs = np.unique(np.append(xs, n - 1))
        return xs, np.clip(smooth[xs], -1.0, 1.0)

    def _y_from_signed(self, m: np.ndarray, geom: TimelineGeometry) -> np.ndarray:
        y0, y1 = geom.band("full")
        amp = min(DIVIDER_Y - y0, y1 - DIVIDER_Y)
        return DIVIDER_Y + m * amp

    def build(self, ax, bundle: PrecomputedBundle, geom: TimelineGeometry) -> None:
        self.reset()
        xs, m = self._signed_series(bundle)
        ys = self._y_from_signed(m, geom)
        points = np.column_stack([xs, ys])
        segments = np.stack([points[:-1], points[1:]], axis=1)
        mid = 0.5 * (m[:-1] + m[1:])
        colors = np.where(mid >= 0, self.home_color, self.away_color)
        lc = LineCollection(
            segments,
            colors=colors,
            linewidths=self.linewidth,
            capstyle="round",
            joinstyle="round",
            zorder=self.meta.z_order,
        )
        ax.add_collection(lc)
        self._artists.append(lc)
