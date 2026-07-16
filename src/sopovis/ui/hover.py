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


class TimeHoverLink:
    """Observable hovered time (tracking-frame index), shared across time views.

    Written by whichever time view the mouse is over (timeline / position
    plot); every subscriber draws a vertical guide line at that frame so the
    hover position is mirrored between the views.
    """

    def __init__(self) -> None:
        self._frame: int | None = None
        self._subscribers: list[Callable[[int | None], None]] = []

    def subscribe(self, callback: Callable[[int | None], None]) -> None:
        self._subscribers.append(callback)

    def set(self, frame: int | None) -> None:
        frame = int(frame) if frame is not None else None
        if frame == self._frame:
            return
        self._frame = frame
        for callback in self._subscribers:
            callback(frame)

    @property
    def frame(self) -> int | None:
        return self._frame
