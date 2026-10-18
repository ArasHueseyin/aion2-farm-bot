from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from .models import Profile, Step, parse_keys, key_label


class StopRun(Exception):
    pass


class LimitReached(Exception):
    pass


@dataclass
class Stats:
    rounds: int = 0
    skills: int = 0
    gathers: int = 0
    elapsed: float = 0.0
    clicks: int = 0


class Runner:
    def __init__(self, profile: Profile, backend, emit=lambda kind, data: None,
                 *, preview=False, speed=1.0, perception=None):
        self.profile = profile
        self.backend = backend
        self.emit = emit
        self.preview = preview
        self.speed = speed if preview else 1.0
        self.stop_event = threading.Event()
        self.stats = Stats()
        self.started = 0.0
        self.deadline = float("inf")
        self.next_target = 0.0
        self.next_loot = 0.0
        self.next_skill = [0.0] * len(profile.skills)
        self.perception = perception
        self.next_mouse = 0.0
        self.mouse_right = False
        self.skill_between_clicks = False

    def stop(self):
        self.stop_event.set()
        # Release immediately, including during a long movement or cast wait.
        try:
            self.backend.release_all()
        except Exception as exc:
            self.emit("log", f"Fehler beim Freigeben der Tasten: {exc}")

    def _check(self, focus=True):
        if self.stop_event.is_set():
            raise StopRun()
        if time.monotonic() >= self.deadline:
            raise LimitReached()
        if focus and not self.backend.has_focus():
            raise RuntimeError("Spielfokus verloren. Bot wurde gestoppt.")

    def _wait(self, seconds: float, *, focus=True):
        end = time.monotonic() + max(0, seconds) / self.speed
        while True:
            self._check(focus)
            remaining = end - time.monotonic()
            if remaining <= 0:
                return
            self.stop_event.wait(min(0.02, remaining))

    def _press(self, chord: str, label: str, hold=0.08):
        keys = parse_keys(chord, optional=True)
        if not keys:
            return
        self._check()
        try:
            self.backend.set_held(keys, self.stop_event)
            self.emit("log", f"{label}: {key_label('+'.join(keys))}")
            self._wait(hold)
        finally:
            self.backend.release_all()

    def _combat(self, duration: float):
        end = time.monotonic() + duration / self.speed
        self.emit("phase", "Kämpfen")
        while time.monotonic() < end:
            self._check()
            now = time.monotonic()
            if now >= self.next_target and self.profile.target_key:
                self._press(self.profile.target_key, "Zielwechsel")
                self.next_target = time.monotonic() + self.profile.target_every / self.speed
            if time.monotonic() >= end:
                break
            if self.profile.alternate_mouse and time.monotonic() >= self.next_mouse:
                button = "rightmouse" if self.mouse_right else "leftmouse"
                self._press(button, "Grundangriff", self.profile.mouse_hold)
                self.stats.clicks += 1
                self.mouse_right = not self.mouse_right
                self.next_mouse = time.monotonic() + self.profile.mouse_interval / self.speed
                self.skill_between_clicks = False
            if time.monotonic() >= end:
                break
            # Rotate the priority cursor so a short-cooldown first skill cannot starve later skills.
            for offset in range(len(self.profile.skills)):
                index = (getattr(self, "skill_cursor", 0) + offset) % len(self.profile.skills)
                skill = self.profile.skills[index]
                if self.profile.alternate_mouse and self.skill_between_clicks:
                    break
                available = self.preview or not self.profile.vision_enabled
                if not available and self.perception is not None:
                    available = self.perception.can_use(index, skill)
                if time.monotonic() >= self.next_skill[index] and available:
                    self._press(skill.key, "Skill", skill.hold)
                    self.stats.skills += 1
                    self.skill_between_clicks = True
                    if self.perception is not None and not self.preview:
                        self.perception.consumed(index, skill)
                    self.next_skill[index] = time.monotonic() + skill.cooldown / self.speed
                    self.skill_cursor = (index + 1) % len(self.profile.skills)
                    self._wait(min(skill.pause, max(0, end - time.monotonic()) * self.speed))
                    break
            if time.monotonic() >= end:
                break
            if time.monotonic() >= self.next_loot and self.profile.loot_key:
                self._press(self.profile.loot_key, "Looten")
                self.next_loot = time.monotonic() + self.profile.loot_every / self.speed
            self._publish_stats()
            self._wait(min(0.05, max(0, end - time.monotonic()) * self.speed))

    def _gather(self, duration: float):
        end = time.monotonic() + duration / self.speed
        self.emit("phase", "Sammeln")
        while time.monotonic() < end:
            self._press(self.profile.interact_key, "Sammeln / Interagieren")
            self.stats.gathers += 1
            self._publish_stats()
            self._wait(min(self.profile.gather_every, max(0, end - time.monotonic()) * self.speed))

    def _step(self, step: Step):
        if step.kind == "combat":
            if self.profile.mode != "gather":
                self._combat(step.duration)
        elif step.kind == "gather":
            if self.profile.mode != "combat":
                self._gather(step.duration)
        elif step.kind == "move":
            self.emit("phase", "Route: " + step.keys)
            self._check()
            try:
                self.backend.set_held(parse_keys(step.keys), self.stop_event)
                self._wait(step.duration)
            finally:
                self.backend.release_all()
        elif step.kind == "turn":
            self.emit("phase", "Mausbewegung")
            ticks = max(1, int(step.duration / 0.02))
            last_x = last_y = 0
            try:
                self._check()
                self.backend.set_held(parse_keys(step.keys, optional=True), self.stop_event)
                for tick in range(1, ticks + 1):
                    self._check()
                    x, y = round(step.dx * tick / ticks), round(step.dy * tick / ticks)
                    self.backend.move_mouse(x - last_x, y - last_y, self.stop_event)
                    last_x, last_y = x, y
                    self._wait(step.duration / ticks)
            finally:
                self.backend.release_all()
        else:
            self.emit("phase", "Warten")
            self._wait(step.duration)

    def _publish_stats(self):
        self.stats.elapsed = max(0, time.monotonic() - self.started)
        self.emit("stats", vars(self.stats).copy())

    def run(self):
        outcome = "stopped"
        try:
            self.profile.validate(for_run=True)
            label = f"Vorschau ({self.speed:g}×)" if self.preview else "LIVE"
            self.emit("log", f"{label}: Start in {self.profile.countdown:g} Sekunden.")
            self.emit("phase", "Startverzögerung – zum Spiel wechseln")
            # The startup delay is always real time.
            original_speed = self.speed
            self.speed = 1.0
            try:
                self._wait(self.profile.countdown, focus=False)
            finally:
                self.speed = original_speed
            self._check()
            self.started = time.monotonic()
            if self.profile.max_minutes:
                self.deadline = self.started + self.profile.max_minutes * 60 / self.speed
            route = self.profile.route or [
                Step("combat", self.profile.combat_seconds, ""),
                Step("gather", self.profile.gather_seconds, ""),
            ]
            self.emit("log", f"{label}: {self.profile.name} / {self.profile.class_name}")
            while True:
                for step in route:
                    self._check()
                    self._step(step)
                    self._publish_stats()
                self.stats.rounds += 1
                self._publish_stats()
                if self.profile.round_limit and self.stats.rounds >= self.profile.round_limit:
                    outcome = "completed"
                    break
        except StopRun:
            self.emit("log", "Gestoppt.")
        except LimitReached:
            outcome = "completed"
            self.emit("log", "Laufzeitlimit erreicht.")
        except Exception as exc:
            outcome = "error"
            self.emit("log", f"Fehler: {exc}")
        finally:
            try:
                self.backend.release_all()
            except Exception as exc:
                outcome = "error"
                self.emit("log", f"Tasten konnten nicht freigegeben werden: {exc}")
            if self.started:
                self._publish_stats()
            self.emit("finished", outcome)
        return outcome
