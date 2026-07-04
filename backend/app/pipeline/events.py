"""In-memory event bus for run SSE streams.

Each run buffers all its events so a late SSE subscriber can replay from the
start, then follow live. Thread-safe: the pipeline runs in a worker thread and
pushes events; the SSE endpoint (async) drains them.
"""
from __future__ import annotations

import threading
from typing import Any


class _RunChannel:
    def __init__(self):
        self.events: list[dict[str, Any]] = []
        self.done = False
        self.cond = threading.Condition()

    def emit(self, event: dict[str, Any]) -> None:
        with self.cond:
            self.events.append(event)
            if event.get("type") == "run_complete":
                self.done = True
            self.cond.notify_all()

    def read_from(self, index: int, timeout: float = 1.0):
        """Return (new_events, next_index, done). Blocks up to timeout for new events."""
        with self.cond:
            if index >= len(self.events) and not self.done:
                self.cond.wait(timeout=timeout)
            new = self.events[index:]
            return new, len(self.events), self.done


class EventBus:
    def __init__(self):
        self._channels: dict[str, _RunChannel] = {}
        self._lock = threading.Lock()

    def channel(self, run_id: str) -> _RunChannel:
        with self._lock:
            ch = self._channels.get(run_id)
            if ch is None:
                ch = _RunChannel()
                self._channels[run_id] = ch
            return ch

    def emit(self, run_id: str, event: dict[str, Any]) -> None:
        self.channel(run_id).emit(event)


bus = EventBus()
