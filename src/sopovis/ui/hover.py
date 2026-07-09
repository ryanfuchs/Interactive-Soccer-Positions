"""HoverLink — shared player highlight state between pitch and position plot."""
from __future__ import annotations

from typing import Callable


class HoverLink:
    """Observable hovered player (person_id), independent of FrameCursor."""

    def __init__(self) -> None:
        self._person_id: str | None = None
        self._subscribers: list[Callable[[str | None], None]] = []

    def subscribe(self, callback: Callable[[str | None], None]) -> None:
        self._subscribers.append(callback)

    def set(self, person_id: str | None) -> None:
        person_id = person_id or None
        if person_id == self._person_id:
            return
        self._person_id = person_id
        for callback in self._subscribers:
            callback(person_id)

    @property
    def person_id(self) -> str | None:
        return self._person_id
