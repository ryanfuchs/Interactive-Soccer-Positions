"""Canvas refresh behavior."""
from unittest.mock import MagicMock

from sopovis.ui.canvas import _needs_sync_draw, refresh_figure


def test_needs_sync_draw_for_tkagg():
    canvas = MagicMock()
    canvas.__class__.__name__ = "FigureCanvasTkAgg"
    assert _needs_sync_draw(canvas) is True


def test_refresh_figure_draws_tkagg_without_manager():
    fig = MagicMock()
    canvas = MagicMock()
    canvas.__class__.__name__ = "FigureCanvasTkAgg"
    canvas.manager = None
    fig.canvas = canvas

    refresh_figure(fig)

    canvas.draw.assert_called_once()
    canvas.draw_idle.assert_not_called()
