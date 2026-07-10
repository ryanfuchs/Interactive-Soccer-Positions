"""Configurable player hover tooltips.

Extend or customize by editing ``DEFAULT_PLAYER_FIELDS`` or passing a custom
``PlayerTooltipConfig`` / field formatter into ``PlayerTooltip``.

When several players share a position-analysis row (starter + substitute),
the tooltip lists all of them. The player currently on the pitch is drawn
at full opacity; others (not yet on / subbed off) are light gray.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
from matplotlib.offsetbox import AnnotationBbox, TextArea, VPacker

from sopovis.analytics.roles import UNSET, role_label
from sopovis.bundle.bundle import PrecomputedBundle

#: Ordered list of field keys shown by default. Add / remove / reorder here
#: or override via ``PlayerTooltipConfig.fields``.
DEFAULT_PLAYER_FIELDS: tuple[str, ...] = (
    "name",
    "shirt_number",
    "team",
    "playing_position",
    "starting",
    "captain",
    "substitution",
    "tactical_role",
    "speed",
)

_ACTIVE_COLOR = "#111111"
_INACTIVE_COLOR = "#b0b0b0"
_OFFSET_PT = 12

FieldFormatter = Callable[[PrecomputedBundle, str, int], str | None]


def player_on_field(bundle: PrecomputedBundle, person_id: str, t: int) -> bool:
    col = bundle.player_index.get(person_id)
    if col is None:
        return False
    xy = bundle.frames[t, col, :2]
    return bool(np.isfinite(xy).all())


def row_mates(bundle: PrecomputedBundle, person_id: str) -> list[str]:
    """Players that share the same position-analysis row (same team)."""
    row = bundle.player_row_order.get(person_id)
    team = bundle.team_map.get(person_id)
    if row is None or team is None:
        return [person_id]
    mates = [
        pid
        for pid, r in bundle.player_row_order.items()
        if r == row and bundle.team_map.get(pid) == team
    ]
    return mates or [person_id]


def _is_substitution_event(event) -> bool:
    base = event.base_type
    return base in ("Substitution", "OutSubstitution") or "Substitution" in event.event_type


def substitution_frames(bundle: PrecomputedBundle, person_id: str) -> dict[str, int]:
    """Frame indices when this player was subbed in / out (from event qualifiers).

    Returns keys ``"in"`` and/or ``"out"`` when known.
    """
    result: dict[str, int] = {}
    for ev in bundle.events:
        if not _is_substitution_event(ev):
            continue
        raw = ev.raw or {}
        player_in = raw.get("PlayerIn")
        player_out = raw.get("PlayerOut")
        if person_id == player_in and "in" not in result:
            result["in"] = ev.frame_idx
        if person_id == player_out and "out" not in result:
            result["out"] = ev.frame_idx
        # floodlight often sets pID to the outgoing player
        if person_id == ev.player_id and player_out is None and "out" not in result:
            result["out"] = ev.frame_idx
    return result


def _name(bundle: PrecomputedBundle, person_id: str, _t: int) -> str | None:
    p = bundle.player_registry.get(person_id)
    if p is None:
        return None
    full = f"{p.first_name} {p.last_name}".strip()
    return full or p.short_name or person_id


def _shirt(bundle: PrecomputedBundle, person_id: str, _t: int) -> str | None:
    p = bundle.player_registry.get(person_id)
    return None if p is None else f"#{p.shirt_number}"


def _team(bundle: PrecomputedBundle, person_id: str, _t: int) -> str | None:
    p = bundle.player_registry.get(person_id)
    if p is None:
        return None
    team = bundle.teams.get(p.team_id)
    return None if team is None else team.team_name


def _playing_position(bundle: PrecomputedBundle, person_id: str, _t: int) -> str | None:
    p = bundle.player_registry.get(person_id)
    if p is None or not p.playing_position:
        return None
    return f"Listed: {p.playing_position}"


def _starting(bundle: PrecomputedBundle, person_id: str, _t: int) -> str | None:
    p = bundle.player_registry.get(person_id)
    if p is None:
        return None
    return "Starter" if p.starting else "Substitute"


def _captain(bundle: PrecomputedBundle, person_id: str, _t: int) -> str | None:
    p = bundle.player_registry.get(person_id)
    if p is None or not p.team_leader:
        return None
    return "Captain"


def _substitution(bundle: PrecomputedBundle, person_id: str, _t: int) -> str | None:
    times = substitution_frames(bundle, person_id)
    parts: list[str] = []
    if "in" in times:
        parts.append(f"Subbed in: {bundle.clock_label(times['in'])}")
    if "out" in times:
        parts.append(f"Subbed out: {bundle.clock_label(times['out'])}")
    return " · ".join(parts) if parts else None


def _tactical_role(bundle: PrecomputedBundle, person_id: str, t: int) -> str | None:
    col = bundle.player_index.get(person_id)
    if col is None:
        return None
    xr, yr = bundle.roles_at(t)[col]
    if xr == UNSET:
        return None
    return f"Role: {role_label(int(xr), int(yr))}"


def _speed(bundle: PrecomputedBundle, person_id: str, t: int) -> str | None:
    col = bundle.player_index.get(person_id)
    if col is None:
        return None
    speed = bundle.frames[t, col, 2]
    if not np.isfinite(speed):
        return None
    return f"Speed: {float(speed):.1f} m/s"


#: Registry of built-in field formatters. Register custom ones with
#: ``PlayerTooltipConfig.register`` or by mutating this dict before UI start.
FIELD_FORMATTERS: dict[str, FieldFormatter] = {
    "name": _name,
    "shirt_number": _shirt,
    "team": _team,
    "playing_position": _playing_position,
    "starting": _starting,
    "captain": _captain,
    "substitution": _substitution,
    "tactical_role": _tactical_role,
    "speed": _speed,
}


@dataclass
class PlayerTooltipConfig:
    """Which fields to show and how to format them.

    Example — only name and role::

        PlayerTooltipConfig(fields=("name", "tactical_role"))

    Example — add a custom field::

        def _id(bundle, pid, t):
            return f"ID: {pid}"
        cfg = PlayerTooltipConfig()
        cfg.register("person_id", _id)
        cfg.fields = (*cfg.fields, "person_id")
    """

    fields: tuple[str, ...] = DEFAULT_PLAYER_FIELDS
    formatters: dict[str, FieldFormatter] = field(default_factory=lambda: dict(FIELD_FORMATTERS))

    def register(self, key: str, formatter: FieldFormatter) -> None:
        self.formatters[key] = formatter

    def format_player(self, bundle: PrecomputedBundle, person_id: str, t: int) -> list[str]:
        lines: list[str] = []
        for key in self.fields:
            fmt = self.formatters.get(key)
            if fmt is None:
                continue
            line = fmt(bundle, person_id, t)
            if line:
                lines.append(line)
        return lines

    def format(self, bundle: PrecomputedBundle, person_id: str, t: int) -> str:
        return "\n".join(self.format_player(bundle, person_id, t))


class PlayerTooltip:
    """Offset-box tooltip; lists row-mates with on-field vs off-field colours."""

    def __init__(self, ax, config: PlayerTooltipConfig | None = None):
        self.ax = ax
        self.config = config or PlayerTooltipConfig()
        self._box: AnnotationBbox | None = None

    def hide(self) -> None:
        if self._box is not None:
            self._box.set_visible(False)

    def _place_offset(self, x: float, y: float) -> tuple[float, float, str, str]:
        disp = self.ax.transData.transform((x, y))
        bbox = self.ax.bbox
        width = max(bbox.width, 1.0)
        height = max(bbox.height, 1.0)
        nx = (disp[0] - bbox.x0) / width
        ny = (disp[1] - bbox.y0) / height
        dx = -_OFFSET_PT if nx > 0.65 else _OFFSET_PT
        dy = -_OFFSET_PT if ny > 0.65 else _OFFSET_PT
        ha = "right" if dx < 0 else "left"
        va = "top" if dy < 0 else "bottom"
        return dx, dy, ha, va

    def _ordered_mates(
        self,
        bundle: PrecomputedBundle,
        person_ids: list[str],
        t: int,
    ) -> list[str]:
        """On-field players first, then by shirt number."""
        def key(pid: str) -> tuple[int, int, str]:
            p = bundle.player_registry.get(pid)
            shirt = p.shirt_number if p is not None else 999
            return (0 if player_on_field(bundle, pid, t) else 1, shirt, pid)

        return sorted(person_ids, key=key)

    def _build_content(
        self,
        bundle: PrecomputedBundle,
        person_ids: list[str],
        t: int,
    ) -> VPacker | None:
        blocks: list = []
        for i, pid in enumerate(person_ids):
            on_field = player_on_field(bundle, pid, t)
            color = _ACTIVE_COLOR if on_field else _INACTIVE_COLOR
            lines = self.config.format_player(bundle, pid, t)
            if not lines:
                continue
            status = "on field" if on_field else "off field"
            header = f"{lines[0]}  ({status})"
            body = lines[1:]
            if i > 0:
                blocks.append(
                    TextArea("────────", textprops={"color": "#cccccc", "size": 6})
                )
            blocks.append(
                TextArea(header, textprops={"color": color, "size": 7, "weight": "bold"})
            )
            for line in body:
                # Live stats only meaningful when on the pitch — still show grayed
                blocks.append(TextArea(line, textprops={"color": color, "size": 7}))
        if not blocks:
            return None
        return VPacker(children=blocks, align="left", pad=0, sep=1)

    def show_at(
        self,
        bundle: PrecomputedBundle,
        person_id: str,
        t: int,
        x: float,
        y: float,
        related_ids: list[str] | None = None,
    ) -> None:
        mates = list(related_ids) if related_ids is not None else row_mates(bundle, person_id)
        if person_id not in mates:
            mates = [person_id, *mates]
        mates = self._ordered_mates(bundle, mates, t)
        content = self._build_content(bundle, mates, t)
        if content is None:
            self.hide()
            return

        dx, dy, _ha, _va = self._place_offset(x, y)
        if self._box is not None:
            self._box.remove()
            self._box = None

        self._box = AnnotationBbox(
            content,
            (x, y),
            xybox=(dx, dy),
            xycoords="data",
            boxcoords="offset points",
            frameon=True,
            box_alignment=(0.0 if dx >= 0 else 1.0, 0.0 if dy >= 0 else 1.0),
            bboxprops={
                "boxstyle": "round,pad=0.35",
                "facecolor": "#ffffe8",
                "edgecolor": "#888888",
                "linewidth": 0.8,
                "alpha": 0.95,
            },
            pad=0.3,
            zorder=200,
        )
        self._box.set_clip_on(False)
        self.ax.add_artist(self._box)
