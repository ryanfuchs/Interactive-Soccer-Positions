"""Event classification, placement, and tooltip formatting for timeline markers."""
from __future__ import annotations

from typing import Callable

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.model.events import EventMoment
from sopovis.render.timeline.geometry import DIVIDER_Y, EVENT_STYLES, SHOT_OFFSET, event_y, team_lane

EVENT_KIND_LABELS = {
    "goal": "Goal",
    "shot_on_goal": "Shot on target",
    "shot_off": "Shot off target",
    "card": "Card",
    "sub": "Substitution",
    "whistle": "Whistle",
}

EventFieldFormatter = Callable[[PrecomputedBundle, EventMoment, str], "str | None"]


def classify_event(event: EventMoment) -> str | None:
    if event.is_goal:
        return "goal"
    if event.is_shot_on_target:
        return "shot_on_goal"
    if event.is_shot_off_target:
        return "shot_off"
    if event.is_shot:
        return "shot_on_goal"
    base = event.base_type
    if base in ("Caution", "SendingOff"):
        return "card"
    if base in ("Substitution", "OutSubstitution"):
        return "sub"
    if base in ("KickOff", "FinalWhistle"):
        return "whistle"
    return None


def _player_display(bundle: PrecomputedBundle, person_id: str | None) -> str | None:
    if not person_id:
        return None
    p = bundle.player_registry.get(person_id)
    if p is None:
        return person_id
    name = f"{p.first_name} {p.last_name}".strip() or p.short_name or person_id
    return f"{name} (#{p.shirt_number})"


def _fmt_kind(bundle: PrecomputedBundle, ev: EventMoment, kind: str) -> str | None:
    label = EVENT_KIND_LABELS.get(kind, ev.base_type)
    if kind == "card":
        label = "Red card" if ev.base_type == "SendingOff" else "Yellow card"
    if kind == "whistle":
        label = "Kick-off" if ev.base_type == "KickOff" else "Final whistle"
    return label


def _fmt_time(bundle: PrecomputedBundle, ev: EventMoment, _kind: str) -> str | None:
    return f"Time: {bundle.clock_label(ev.frame_idx)}"


def _fmt_team(bundle: PrecomputedBundle, ev: EventMoment, _kind: str) -> str | None:
    if ev.team_id is None:
        return None
    team = bundle.teams.get(ev.team_id)
    return None if team is None else team.team_name


def _fmt_player(bundle: PrecomputedBundle, ev: EventMoment, kind: str) -> str | None:
    if kind == "sub":
        return None  # handled by _fmt_sub_players
    return _player_display(bundle, ev.player_id)


def _fmt_sub_players(bundle: PrecomputedBundle, ev: EventMoment, kind: str) -> str | None:
    if kind != "sub":
        return None
    raw = ev.raw or {}
    lines = []
    player_in = _player_display(bundle, raw.get("PlayerIn"))
    player_out = _player_display(bundle, raw.get("PlayerOut") or ev.player_id)
    if player_in:
        lines.append(f"In: {player_in}")
    if player_out:
        lines.append(f"Out: {player_out}")
    return "\n".join(lines) or None


#: Ordered tooltip content; extend or reorder to customize event tooltips.
EVENT_TOOLTIP_FIELDS: tuple[str, ...] = ("kind", "time", "team", "player", "sub_players")

EVENT_FIELD_FORMATTERS: dict[str, EventFieldFormatter] = {
    "kind": _fmt_kind,
    "time": _fmt_time,
    "team": _fmt_team,
    "player": _fmt_player,
    "sub_players": _fmt_sub_players,
}


def format_event(bundle: PrecomputedBundle, ev: EventMoment, kind: str) -> list[str]:
    lines: list[str] = []
    for key in EVENT_TOOLTIP_FIELDS:
        fmt = EVENT_FIELD_FORMATTERS.get(key)
        if fmt is None:
            continue
        text = fmt(bundle, ev, kind)
        if text:
            lines.extend(text.split("\n"))
    return lines


def iter_events(
    bundle: PrecomputedBundle, kinds: set[str], team: str
) -> list[tuple[EventMoment, str, float]]:
    """Deduplicated (event, kind, y) tuples for the requested kinds/team filter."""
    out: list[tuple[EventMoment, str, float]] = []
    seen: set[tuple] = set()
    for ev in bundle.events:
        kind = classify_event(ev)
        if kind is None or kind not in kinds:
            continue
        lane = team_lane(bundle, ev.team_id)
        if team != "both" and lane != team:
            continue
        y = event_y(bundle, ev.team_id, kind)
        if y is None:
            continue
        key = (ev.frame_idx, kind, ev.player_id, ev.team_id)
        if key in seen:
            continue
        seen.add(key)
        out.append((ev, kind, y))
    return out
