"""Red zone product (Tanner 2026) and its three overlays."""
import numpy as np


def test_closed_nurbs_stays_in_convex_hull():
    from sopovis.analytics.redzone import evaluate_closed_nurbs, polygon_area

    square = np.array([[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]])
    weights = np.ones(4)
    boundary = evaluate_closed_nurbs(square, weights, samples=100)

    assert boundary.shape == (100, 2)
    # convex hull property of B-splines
    assert boundary.min() >= -1e-9
    assert boundary.max() <= 10.0 + 1e-9
    # closed, non-degenerate zone
    assert polygon_area(boundary) > 10.0


def test_redzone_product_shapes(synthetic_bundle):
    result = synthetic_bundle.product("redzone")
    ta_total = synthetic_bundle.total_analytics_frames
    n = len(synthetic_bundle.player_ids)
    home = synthetic_bundle.meta.home_team_id
    away = synthetic_bundle.meta.guest_team_id

    for tid in (home, away):
        assert len(result.control_points[tid]) == ta_total
        assert len(result.weights[tid]) == ta_total
        assert result.areas[tid].shape == (ta_total,)
        assert (result.areas[tid] >= 0).all()
    assert result.inside_opponent.shape == (ta_total, n)

    # wherever a zone exists it has enough control points for a cubic curve
    for tid in (home, away):
        for ctrl, w in zip(result.control_points[tid], result.weights[tid]):
            if ctrl is not None:
                assert len(ctrl) >= 4
                assert len(w) == len(ctrl)
                assert (w > 0).all()


def test_redzone_pitch_overlay_draws(synthetic_bundle):
    from matplotlib.figure import Figure

    from sopovis.render.elements import ElementMeta
    from sopovis.render.pitch import RedzoneOverlay

    fig = Figure()
    ax = fig.add_subplot(111)
    overlay = RedzoneOverlay(ElementMeta(name="redzone", z_order=28))
    overlay.draw(ax, synthetic_bundle, 0)
    assert set(overlay._patches) == {
        synthetic_bundle.meta.home_team_id,
        synthetic_bundle.meta.guest_team_id,
    }


def test_redzone_timeline_chart_builds(synthetic_bundle):
    from matplotlib.figure import Figure

    from sopovis.render.elements import ElementMeta
    from sopovis.render.timeline import RedzoneAreaChart, default_geometry

    fig = Figure()
    ax = fig.add_subplot(111)
    chart = RedzoneAreaChart(ElementMeta(name="redzone_area", z_order=3))
    chart.build(ax, synthetic_bundle, default_geometry())
    # either the synthetic match has no zone at all (flat zero → no artists)
    # or the chart drew one fill + one line per team
    assert len(chart._artists) in (0, 4)


def test_redzone_presence_builds_without_heatmap(synthetic_bundle):
    """Row layout lives on the context, so the overlay works standalone."""
    from matplotlib.figure import Figure

    from sopovis.render.elements import ElementMeta
    from sopovis.render.position import PositionContext, RedzonePresence

    fig = Figure()
    ax = fig.add_subplot(111)
    ctx = PositionContext.prepare(
        synthetic_bundle,
        resolution=10,
        team_focus="both",
        home_at_bottom=True,
        ball_in_play=False,
        possession_filter="all",
        time_window=(0, synthetic_bundle.total_frames),
    )
    assert ctx.row_bands  # layout computed by prepare, no heatmap needed
    assert ctx.total_rows >= max(band.y1 for band in ctx.row_bands)
    presence = RedzonePresence(ElementMeta(name="redzone_presence", z_order=15))
    presence.build(ax, synthetic_bundle, ctx)
    assert len(presence._artists) == 1
