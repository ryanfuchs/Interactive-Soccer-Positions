"""Visible time range — period filter plus optional zoom span."""
from __future__ import annotations

from dataclasses import dataclass

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.settings import UserSettings


@dataclass
class ViewTimeRange:
    """Match-time window shown on the timeline and position analysis.

    ``period`` restricts to a half / extra-time section; ``zoom`` further
    narrows to a user-selected span (drag on the timeline or position plot).
    """

    bundle: PrecomputedBundle
    period: str | None = None
    zoom: tuple[int, int] | None = None  # (start, end) tracking frames, end exclusive

    def period_limits(self) -> tuple[int, int]:
        if self.period and self.period in self.bundle.section_ranges:
            lo, hi = self.bundle.section_ranges[self.period]
            return int(lo), int(hi)
        return 0, self.bundle.total_frames

    def limits(self) -> tuple[int, int]:
        lo, hi = self.period_limits()
        if self.zoom is not None:
            zlo, zhi = self.zoom
            lo = max(lo, int(zlo))
            hi = min(hi, int(zhi))
        return lo, max(lo + 1, hi)

    @property
    def is_zoomed(self) -> bool:
        return self.zoom is not None

    def set_period(self, period: str | None) -> None:
        self.period = period
        self.reset_zoom()

    def reset_zoom(self) -> None:
        self.zoom = None

    def set_zoom(self, start: int, end: int, min_seconds: float) -> bool:
        """Apply zoom if the span is wide enough; returns False if rejected."""
        plo, phi = self.period_limits()
        lo, hi = sorted((int(start), int(end)))
        lo = max(plo, lo)
        hi = min(phi, hi)
        min_frames = max(1, int(min_seconds * self.bundle.frame_rate))
        if hi - lo < min_frames:
            return False
        self.zoom = (lo, hi)
        return True


def auto_resolution(settings: UserSettings, bundle: PrecomputedBundle, t0: int, t1: int) -> int:
    """Pick a position-analysis bin width for the visible tracking window."""
    visible = max(1, t1 - t0)
    visible_ta = max(1, visible // bundle.analytics_stride)
    target = max(1, settings.zoom_target_bins)
    res = visible_ta // target
    return max(5, min(600, max(1, res)))
