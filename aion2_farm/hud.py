"""Conservative screen-based gates. No game memory or client hooks are used."""
from __future__ import annotations

import base64
import time
from PIL import Image, ImageChops, ImageGrab, ImageStat


def reference_image(image):
    small = image.convert("RGB").resize((16, 16), Image.Resampling.BILINEAR)
    return base64.b64encode(small.tobytes()).decode("ascii")


def decode_reference(value):
    raw = base64.b64decode(value, validate=True)
    if len(raw) != 768:
        raise ValueError("Ungültiges Referenzbild.")
    return Image.frombytes("RGB", (16, 16), raw)


def region_crop(image, region):
    x, y, width, height = region
    if min(x, y) < 0 or width < 3 or height < 3 or x + width > image.width or y + height > image.height:
        raise ValueError("Kalibrierter Bereich liegt außerhalb des Spielfensters.")
    return image.crop((x, y, x + width, y + height))


def mana_fraction(current, reference):
    """Compare a thin colored bar with its full-mana reference; err towards undercounting."""
    expected = reference.convert("RGB").resize((128, 8), Image.Resampling.BILINEAR)
    actual = current.convert("RGB").resize((128, 8), Image.Resampling.BILINEAR)
    mean = ImageStat.Stat(expected).mean
    if max(mean) - min(mean) < 20 or max(mean) < 60:
        raise ValueError("Manabereich muss den farbigen Balken ohne Zahlen und Rahmen enthalten.")
    ready = []
    for x in range(128):
        a = ImageStat.Stat(actual.crop((x, 0, x + 1, 8))).mean
        b = ImageStat.Stat(expected.crop((x, 0, x + 1, 8))).mean
        distance = sum(abs(v - w) for v, w in zip(a, b)) / (3 * 255)
        ready.append(distance <= 0.16 and sum(a) >= sum(b) * .62)
    # A left-filled bar must not be reconstructed from scattered matching UI pixels.
    end = 0
    for index in range(0, 128, 4):
        if sum(ready[index:index + 4]) < 3:
            break
        end = index + 4
    return end / 128


def icon_is_ready(current, reference):
    current = current.convert("RGB").resize((16, 16), Image.Resampling.BILINEAR)
    diff = ImageChops.difference(current, reference.convert("RGB"))
    whole = sum(ImageStat.Stat(diff).mean) / (3 * 255)
    center = sum(ImageStat.Stat(diff.crop((4, 4, 12, 12))).mean) / (3 * 255)
    return whole <= .065 and center <= .09


def capture_game(process):
    from .windows import game_client_bounds
    hwnd, bounds = game_client_bounds(process)
    image = ImageGrab.grab(bbox=bounds, all_screens=True).convert("RGB")
    after_hwnd, after_bounds = game_client_bounds(process)
    if hwnd != after_hwnd or bounds != after_bounds:
        raise RuntimeError("Spielfenster hat sich während der HUD-Aufnahme geändert.")
    return image


class HudMonitor:
    def __init__(self, profile, emit=lambda kind, value: None, capture=capture_game, clock=time.monotonic):
        self.profile = profile
        self.emit = emit
        self.capture = capture
        self.clock = clock
        self.last_poll = -float("inf")
        self.mana = None
        self.stable = [0] * len(profile.skills)
        self.reservations = []
        self.last_message = None

    def _message(self, text):
        self.emit("hud", text)
        # Changing mana values belong in status, not in a log line on every frame.
        if text.startswith("HUD nicht") and text != self.last_message:
            self.emit("log", text + " Skills bleiben aus; Grundangriffe können weiterlaufen.")
        self.last_message = text

    def poll(self):
        now = self.clock()
        if now - self.last_poll < .15:
            return
        self.last_poll = now
        self.reservations = [(expiry, cost) for expiry, cost in self.reservations if expiry > now]
        try:
            p = self.profile
            if not p.vision_size or not p.mana_region or not p.mana_reference or p.max_mana <= 0:
                raise ValueError("Manabalken und maximales Mana zuerst unter HUD-Erkennung einrichten.")
            image = self.capture(p.process)
            if list(image.size) != p.vision_size:
                raise ValueError("Auflösung geändert; HUD-Bereiche neu kalibrieren.")
            self.mana = mana_fraction(region_crop(image, p.mana_region), decode_reference(p.mana_reference)) * p.max_mana
            for index, skill in enumerate(p.skills):
                ready = False
                if skill.ready_region and skill.ready_reference:
                    ready = icon_is_ready(region_crop(image, skill.ready_region), decode_reference(skill.ready_reference))
                self.stable[index] = min(2, self.stable[index] + 1) if ready else 0
            available = sum(value >= 2 for value in self.stable)
            self._message(f"Mana geschätzt: {self.mana:.0f} / {p.max_mana:g} · {available}/{len(p.skills)} Symbole bereit")
        except Exception as exc:
            self.mana = None
            self.stable = [0] * len(self.profile.skills)
            self._message(f"HUD nicht eindeutig: {exc}")

    def can_use(self, index, skill):
        self.poll()
        if self.mana is None or skill.mana_cost is None or self.stable[index] < 2:
            return False
        reserve = sum(cost for expiry, cost in self.reservations)
        safety_margin = self.profile.max_mana * .02 if skill.mana_cost else 0
        return self.mana - reserve >= skill.mana_cost + safety_margin

    def consumed(self, index, skill):
        self.stable[index] = 0
        self.reservations.append((self.clock() + max(2.0, skill.pause + skill.hold + .5), skill.mana_cost or 0))
