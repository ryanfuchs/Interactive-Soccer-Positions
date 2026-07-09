"""Matplotlib canvas refresh helpers for desktop TkAgg figures."""
from __future__ import annotations

from matplotlib.figure import Figure


def _needs_sync_draw(canvas) -> bool:
    """Embedded TkAgg canvases have no window manager; draw_idle never flushes."""
    return "TkAgg" in type(canvas).__name__


def refresh_figure(fig: Figure, *, force: bool = False) -> None:
    """Redraw a figure so widget-driven updates become visible."""
    canvas = fig.canvas
    if force or _needs_sync_draw(canvas) or getattr(canvas, "manager", None) is not None:
        canvas.draw()
    else:
        canvas.draw_idle()
