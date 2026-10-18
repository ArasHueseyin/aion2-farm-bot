from __future__ import annotations

import threading
import time
from .models import Step


class RouteRecorder:
    """Record durations of physical movement keys, with explicit farm markers."""

    def __init__(self, allowed_keys, clock=time.monotonic):
        self.allowed = set(allowed_keys)
        self.clock = clock
        self.lock = threading.Lock()
        self.held: set[str] = set()
        self.steps: list[Step] = []
        self.since = clock()
        self.active = True

    def _flush(self):
        now = self.clock()
        duration = round(now - self.since, 3)
        if duration >= 0.01:
            kind = "move" if self.held else "wait"
            keys = "+".join(sorted(self.held))
            if self.steps and self.steps[-1].kind == kind and self.steps[-1].keys == keys:
                self.steps[-1].duration += duration
            else:
                self.steps.append(Step(kind, duration, keys))
        self.since = now

    def key_event(self, key: str, pressed: bool):
        with self.lock:
            if not self.active or key not in self.allowed or ((key in self.held) == pressed):
                return
            self._flush()
            if pressed:
                self.held.add(key)
            else:
                self.held.discard(key)

    def marker(self, kind: str, duration: float) -> bool:
        with self.lock:
            if not self.active or self.held:
                return False
            self._flush()
            self.steps.append(Step(kind, duration, ""))
            return True

    def finish(self) -> list[Step]:
        with self.lock:
            if self.active:
                self._flush()
                self.active = False
                self.held.clear()
            # Drop reaction time around the recording hotkey.
            if self.steps and self.steps[0].kind == "wait":
                self.steps.pop(0)
            if self.steps and self.steps[-1].kind == "wait":
                self.steps.pop()
            return list(self.steps)
