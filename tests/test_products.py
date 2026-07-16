"""Producer registry, lazy products and per-product cache."""
import numpy as np


def test_core_products_present(synthetic_bundle):
    assert set(synthetic_bundle.products) >= {
        "attack_directions",
        "shape_graph",
        "roles",
    }
    assert synthetic_bundle.tactical_roles.shape[0] == synthetic_bundle.total_analytics_frames


def test_lazy_product_computed_on_first_access(synthetic_bundle):
    assert "proximity" not in synthetic_bundle.products
    edges = synthetic_bundle.edges_at(0, "proximity", synthetic_bundle.meta.home_team_id)
    assert "proximity" in synthetic_bundle.products
    assert edges.ndim == 2 and edges.shape[1] == 2


def test_unknown_product_raises(synthetic_bundle):
    import pytest

    with pytest.raises(KeyError):
        synthetic_bundle.product("does_not_exist")


def test_product_cache_roundtrip(synthetic_state, tmp_path):
    from sopovis.analytics.producers import AttackDirectionsProducer
    from sopovis.bundle.cache import ProductCache

    cache = ProductCache(tmp_path)
    producer = AttackDirectionsProducer()
    assert cache.load(synthetic_state, producer, stride=5) is None

    value = producer.compute(synthetic_state, {}, stride=5)
    cache.save(synthetic_state, producer, stride=5, value=value)
    assert cache.load(synthetic_state, producer, stride=5) == value
    # a different stride is a different key
    assert cache.load(synthetic_state, producer, stride=10) is None


def test_version_bump_invalidates_only_that_product(synthetic_state, tmp_path):
    from sopovis.analytics.producers import AttackDirectionsProducer, ShapeGraphProducer
    from sopovis.bundle.cache import ProductCache

    cache = ProductCache(tmp_path)
    directions = AttackDirectionsProducer()
    shape = ShapeGraphProducer()
    cache.save(synthetic_state, directions, 5, directions.compute(synthetic_state, {}, 5))
    cache.save(synthetic_state, shape, 5, shape.compute(synthetic_state, {}, 5))

    directions.version = 99
    assert cache.load(synthetic_state, directions, 5) is None
    assert cache.load(synthetic_state, shape, 5) is not None


def test_edge_set_overlay_renders_any_relation(synthetic_bundle):
    from matplotlib.figure import Figure

    from sopovis.render.elements import ElementMeta
    from sopovis.render.pitch import EdgeSetOverlay

    fig = Figure()
    ax = fig.add_subplot(111)
    overlay = EdgeSetOverlay(
        ElementMeta(name="proximity", z_order=25), relation="proximity"
    )
    overlay.draw(ax, synthetic_bundle, 0)
    home = synthetic_bundle.meta.home_team_id
    assert home in overlay._collections
    segments = overlay._collections[home].get_segments()
    expected = synthetic_bundle.edges_at(0, "proximity", home)
    assert len(segments) == len(expected)
    if len(segments):
        assert np.isfinite(np.asarray(segments)).all()
