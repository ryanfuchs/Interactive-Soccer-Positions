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


def test_desktop_resolution_change(synthetic_bundle):
    app = _make_desktop(synthetic_bundle)
    assert app.app.position_plot.resolution == 150

    app._resolution_var.set(40.0)
    app._on_resolution_release()
    assert app.app.position_plot.resolution == 40

    app._on_close()


def test_desktop_ball_and_possession_filters(synthetic_bundle):
    app = _make_desktop(synthetic_bundle)
    assert app.app.position_plot.ball_in_play is False
    assert app.app.position_plot.possession_filter == "all"

    app._ball_in_play_var.set(True)
    app._on_ball_in_play()
    assert app.app.position_plot.ball_in_play is True

    app._possession_var.set("Home ball")
    app._on_possession_choice("Home ball")
    assert app.app.position_plot.possession_filter == "home"

    app._on_close()


def test_player_tooltip_format(synthetic_bundle):
    from sopovis.ui.tooltips import PlayerTooltipConfig, player_on_field, row_mates

    pid = synthetic_bundle.player_ids[0]
    lines = PlayerTooltipConfig().format_player(synthetic_bundle, pid, 0)
    assert any("#" in line for line in lines)
    assert len(lines) > 1
    assert player_on_field(synthetic_bundle, pid, 0) is True
    assert pid in row_mates(synthetic_bundle, pid)


def test_desktop_speed_change(synthetic_bundle):
    app = _make_desktop(synthetic_bundle)
    app._speed_var.set("4×")
    app._on_speed_choice("4×")
    assert app.app.timeline.speed == 4.0
    assert app._play_step == 8

    app._on_close()


def test_desktop_period_filter(synthetic_bundle):
    app = _make_desktop(synthetic_bundle)
    assert app.app.view_range.period is None

    app._period_var.set("1st Half")
    app._on_period_choice("1st Half")
    assert app.app.view_range.period == "firstHalf"
    assert app.app.position_plot.view_range.period == "firstHalf"
    lo, hi = synthetic_bundle.section_ranges["firstHalf"]
    assert app._t0 == lo
    assert app._t_max == hi - 1

    app._on_close()


def test_time_zoom_and_auto_resolution(synthetic_bundle):
    from matplotlib.backend_bases import MouseEvent

    from sopovis.config.settings import UserSettings
    from sopovis.ui.time_window import ViewTimeRange, auto_resolution

    settings = UserSettings(auto_resolution_on_zoom=True, zoom_target_bins=100)
    vr = ViewTimeRange(synthetic_bundle)
    full_res = auto_resolution(settings, synthetic_bundle, *vr.limits())
    assert vr.set_zoom(100, 400, settings.min_zoom_seconds)
    zoom_res = auto_resolution(settings, synthetic_bundle, *vr.limits())
    assert zoom_res < full_res

    app = _make_desktop(synthetic_bundle)
    assert app.app.timeline._span_zoom is not None
    assert app.app.position_plot._span_zoom is not None
    assert app.app.set_zoom(50, 500)
    assert app.app.view_range.is_zoomed
    z0, z1 = app.app.view_range.limits()
    assert app.app.timeline.ax.get_xlim()[0] == pytest.approx(z0, abs=1)
    app.app.reset_zoom()

    canvas = app.fig_timeline.canvas
    ax = app.app.timeline.ax
    canvas.draw()
    bbox = ax.bbox
    x0p = bbox.x0 + bbox.width * 0.2
    x1p = bbox.x0 + bbox.width * 0.8
    yp = bbox.y0 + bbox.height * 0.5
    for name, xp in [
        ("button_press_event", x0p),
        ("button_release_event", x1p),
    ]:
        canvas.callbacks.process(
            name, MouseEvent(name, canvas, xp, yp, button=1, dblclick=False)
        )
    assert app.app.view_range.is_zoomed
    app._on_close()


def test_desktop_orientation_toggle(synthetic_bundle):
    app = _make_desktop(synthetic_bundle)
    assert app.app.pitch.home_at_bottom is True

    app._on_orientation_toggle()
    assert app._home_bottom_var.get() is False
    assert app.app.pitch.home_at_bottom is False
    assert app.app.position_plot.home_at_bottom is False

    app._on_close()


def test_layer_display_names(synthetic_bundle):
    app = _make_desktop(synthetic_bundle)
    shape = app.app.pitch.scene.get("shape_graph")
    assert shape.meta.ui_label() == "Shape graph"
    assert "_" not in shape.meta.ui_label()
    app._on_close()


def test_timeline_layers_and_tooltips(synthetic_bundle):
    app = _make_desktop(synthetic_bundle)
    timeline = app.app.timeline

    names = [el.meta.name for el in timeline.elements]
    assert "shots" in names
    assert "possession" in names

    # synthetic match has one goal → shots layer exposes a hover target
    shots = timeline.get("shots")
    targets = shots.hover_targets()
    assert targets
    lines = targets[0][2]
    assert any("Goal" in line for line in lines)
    assert any("Time:" in line for line in lines)

    # toggling a timeline layer rebuilds without error
    assert "timeline:shots" in app._layer_vars
    timeline.set_layer_enabled("shots", False)
    assert timeline.get("shots").meta.enabled is False
    assert timeline.get("shots").hover_targets() == []

    app._on_close()


def test_timeline_possession_chart(synthetic_bundle):
    from matplotlib.collections import LineCollection
    from matplotlib.figure import Figure

    from sopovis.render.timeline import PossessionChart, default_geometry, default_timeline_registry
    from sopovis.render.timeline.geometry import DIVIDER_Y
    from sopovis.render.elements import ElementMeta

    fig = Figure()
    ax = fig.add_subplot(111)
    geom = default_geometry()

    chart = PossessionChart(
        ElementMeta(name="possession", z_order=2),
        home_color="#d00000",
        away_color="#215CAF",
    )
    chart.build(ax, synthetic_bundle, geom)
    assert len(chart._artists) == 1
    assert isinstance(chart._artists[0], LineCollection)

    xs, m = chart._signed_series(synthetic_bundle)
    assert xs[0] == 0
    assert xs[-1] == synthetic_bundle.total_frames - 1
    assert m.min() >= -1.0 and m.max() <= 1.0
    ys = chart._y_from_signed(m, geom)
    assert ys.min() >= geom.band("away")[0] - 0.01
    assert ys.max() <= geom.band("home")[1] + 0.01
    # synthetic match: all home possession → line stays in home half
    assert float(m.mean()) > 0
    assert float(ys.mean()) > DIVIDER_Y

    reg = default_timeline_registry()
    assert "PossessionChart" in reg.types
