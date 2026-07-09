"""FrameCursor — observable current frame, owned by the timeline."""
from __future__ import annotations

from typing import Callable


class FrameCursor:
    """Observable integer frame index.

    Only TimelineControlView may call set(); all other views subscribe and
    request seeks through the timeline.
    """

    def __init__(self, t: int = 0):
        self._t = t
        self._subscribers: list[Callable[[int], None]] = []

    def subscribe(self, callback: Callable[[int], None]) -> None:
        self._subscribers.append(callback)

    def set(self, t: int) -> None:
        t = int(t)
        if t == self._t:
            return
        self._t = t
        for callback in self._subscribers:
            callback(t)

    @property
    def t(self) -> int:
        return self._t
