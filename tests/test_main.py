"""CLI and desktop shell smoke tests."""
import pytest


def test_match_id_default():
    from sopovis.main import DEFAULT_MATCH, match_id_from_argv

    assert match_id_from_argv([]) == DEFAULT_MATCH


def test_match_id_override():
    from sopovis.main import match_id_from_argv

    assert match_id_from_argv(["DFL-MAT-FOO"]) == "DFL-MAT-FOO"


def _make_desktop(synthetic_bundle):
    pytest.importorskip("tkinter")
    import matplotlib

    matplotlib.use("TkAgg")
    from sopovis.ui.desktop import MatchDesktopApp

    return MatchDesktopApp(synthetic_bundle, preset="tactical")


def test_desktop_play_advances_cursor(synthetic_bundle):
    app = _make_desktop(synthetic_bundle)

    app._on_scrub(10)
    assert app.app.cursor.t == 10
    assert app.app.pitch.ax.get_title().endswith(app.app.bundle.clock_label(10))

    app._play_step = 5
    app._playing = True
    app._play_tick()
    assert app.app.cursor.t == 15

    app._on_close()


def test_desktop_preset_change(synthetic_bundle):
    app = _make_desktop(synthetic_bundle)
    assert app.preset.name == "tactical"

    app._preset_var.set("broadcast")
    app._on_preset_choice("broadcast")

    assert app.preset.name == "broadcast"
    assert app.app.pitch.scene.get("pitch_markings").grass_color == "#2e7d46"
    app._on_close()


def test_desktop_layer_toggle(synthetic_bundle):
    app = _make_desktop(synthetic_bundle)
    layer = app.app.pitch.scene.get("shape_graph")
    assert layer.meta.enabled is True

    app._layer_vars["shape_graph"].set(False)
    app._on_layer_toggle("shape_graph", app._layer_vars["shape_graph"])
    assert layer.meta.enabled is False

    app._on_close()


def test_desktop_team_focus(synthetic_bundle):
    app = _make_desktop(synthetic_bundle)
    assert app.app.position_plot.team_focus == "both"

    app._team_var.set("home")
    app._on_team_focus()
    assert app.app.position_plot.team_focus == "home"
    assert len(app.app.position_plot.ax.get_yticks()) < 30

    app._on_close()


def test_desktop_smoothing_change(synthetic_bundle):
    app = _make_desktop(synthetic_bundle)
    assert app.app.position_plot.smoothing == 150

    app._smoothing_var.set(40.0)
    app._on_smoothing_release()
    assert app.app.position_plot.smoothing == 40

    app._on_close()


def test_desktop_speed_change(synthetic_bundle):
    app = _make_desktop(synthetic_bundle)
    app._speed_var.set("4×")
    app._on_speed_choice("4×")
    assert app.app.timeline.speed == 4.0
    assert app._play_step == 8

    app._on_close()
