"""Shared helpers for built-in render layers."""
from __future__ import annotations

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.presets import LayerSpec
from sopovis.render.elements import ElementMeta


def meta_from_spec(spec: LayerSpec) -> ElementMeta:
    return ElementMeta(
        name=spec.name,
        z_order=spec.z_order,
        display_name=spec.display_name,
        category=spec.category,
        enabled=spec.enabled,
    )


def team_ids(bundle: PrecomputedBundle, which: str) -> list[str]:
    home, away = bundle.meta.home_team_id, bundle.meta.guest_team_id
    return {"home": [home], "away": [away], "both": [home, away]}[which]
