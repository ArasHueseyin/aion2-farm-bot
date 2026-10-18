from __future__ import annotations

import json
import math
import os
import base64
from dataclasses import asdict, dataclass, field
from pathlib import Path


MODES = ("combat", "gather", "combined")
KINDS = ("move", "turn", "combat", "gather", "wait")
RESERVED = {"f6", "f7", "f8", "f9", "f10"}
KEYS = set("abcdefghijklmnopqrstuvwxyz0123456789") | {
    "tab", "space", "enter", "escape", "shift", "ctrl", "alt", "backspace",
    "up", "down", "left", "right", "home", "end", "insert", "delete",
    "pageup", "pagedown", "leftmouse", "rightmouse", "middlemouse",
} | {f"f{i}" for i in range(1, 13)}
ALIASES = {"strg": "ctrl", "steuerung": "ctrl", "leer": "space",
           "leertaste": "space", "esc": "escape", "return": "enter",
           "linke maustaste": "leftmouse", "rechte maustaste": "rightmouse",
           "linksklick": "leftmouse", "rechtsklick": "rightmouse", "lmb": "leftmouse", "rmb": "rightmouse"}


def key_label(value: str) -> str:
    names = {"leftmouse": "Linke Maustaste", "rightmouse": "Rechte Maustaste", "middlemouse": "Mittlere Maustaste"}
    return " + ".join(names.get(key, key) for key in parse_keys(value, optional=True))


def validate_reference(region, reference, label):
    if region:
        if not isinstance(region, list) or len(region) != 4 or any(type(x) is not int for x in region):
            raise ValueError(f"{label}: ungültiger Bildbereich.")
        if min(region[:2]) < 0 or min(region[2:]) < 3 or max(region) > 32000:
            raise ValueError(f"{label}: ungültige Bereichsgröße.")
    if reference:
        try:
            valid = len(base64.b64decode(reference, validate=True)) == 16 * 16 * 3
        except (ValueError, TypeError):
            valid = False
        if not valid:
            raise ValueError(f"{label}: ungültiges Referenzbild.")


def parse_keys(value: str, *, optional: bool = False) -> tuple[str, ...]:
    if not value.strip() and optional:
        return ()
    tokens = value.lower().replace(",", "+").split("+")
    keys = tuple(dict.fromkeys(ALIASES.get(x.strip(), x.strip()) for x in tokens))
    for key in keys:
        if key not in KEYS:
            raise ValueError(f"Unbekannte Taste: {key or '(leer)'}. Beispiel: 1 oder shift+1.")
        if key in RESERVED:
            raise ValueError(f"{key.upper()} ist für die Bot-Steuerung reserviert.")
    return keys


def number(value, label: str, minimum: float, maximum: float) -> float:
    try:
        result = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        raise ValueError(f"{label}: Bitte eine Zahl eingeben.") from None
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise ValueError(f"{label}: erlaubt sind {minimum:g} bis {maximum:g}.")
    return result


@dataclass
class Skill:
    key: str = "1"
    cooldown: float = 3.0
    pause: float = 0.4
    hold: float = 0.08
    mana_cost: float | None = None
    ready_region: list[int] = field(default_factory=list)
    ready_reference: str = ""

    def validate(self):
        self.key = "+".join(parse_keys(self.key))
        self.cooldown = number(self.cooldown, "Skill-Cooldown", 0.1, 3600)
        self.pause = number(self.pause, "Skill-Pause", 0, 120)
        self.hold = number(self.hold, "Haltedauer", 0.02, 30)
        if self.mana_cost is not None:
            self.mana_cost = number(self.mana_cost, "Manakosten", 0, 1000000)
        validate_reference(self.ready_region, self.ready_reference, "Skill-Symbol")


@dataclass
class Step:
    kind: str = "move"
    duration: float = 1.0
    keys: str = "w"
    dx: int = 0
    dy: int = 0

    def validate(self):
        if self.kind not in KINDS:
            raise ValueError(f"Unbekannter Routenschritt: {self.kind}")
        self.duration = number(self.duration, "Schrittdauer", 0.01, 3600)
        if self.kind in ("move", "turn"):
            parse_keys(self.keys, optional=self.kind == "turn")
        self.dx = int(number(self.dx, "Maus X", -10000, 10000))
        self.dy = int(number(self.dy, "Maus Y", -10000, 10000))


@dataclass
class Profile:
    version: int = 1
    name: str = "Mein Charakter"
    class_name: str = "Eigene Klasse"
    mode: str = "combined"
    process: str = "Aion2.exe"
    input_method: str = "scancode"
    countdown: float = 5.0
    max_minutes: float = 30.0
    round_limit: int = 0
    target_key: str = "tab"
    target_every: float = 12.0
    loot_key: str = "f"
    loot_every: float = 4.0
    interact_key: str = "f"
    gather_every: float = 3.0
    combat_seconds: float = 20.0
    gather_seconds: float = 6.0
    alternate_mouse: bool = True
    mouse_interval: float = 0.7
    mouse_hold: float = 0.1
    vision_enabled: bool = True
    max_mana: float = 0
    vision_size: list[int] = field(default_factory=list)
    mana_region: list[int] = field(default_factory=list)
    mana_reference: str = ""
    movement_keys: str = "w,a,s,d,q,e,space,shift,ctrl,up,down,left,right"
    skills: list[Skill] = field(default_factory=lambda: [
        Skill("1", 1.0, 0.3), Skill("2", 5.0, 0.5), Skill("3", 8.0, 0.5),
    ])
    route: list[Step] = field(default_factory=list)

    def validate(self, *, for_run=False):
        if self.version != 1:
            raise ValueError("Diese Profilversion wird nicht unterstützt.")
        self.name = self.name.strip()
        if not self.name or len(self.name) > 100:
            raise ValueError("Der Profilname muss 1 bis 100 Zeichen lang sein.")
        if self.mode not in MODES:
            raise ValueError("Unbekannter Farmmodus.")
        if self.input_method not in ("scancode", "virtual", "messages"):
            raise ValueError("Unbekannte Eingabemethode.")
        self.process = self.process.strip()
        if not self.process.lower().endswith(".exe") or any(x in self.process for x in "\\/:"):
            raise ValueError("Prozess: Nur den Dateinamen eingeben, etwa Aion2.exe.")
        for attr, label, lo, hi in (
            ("countdown", "Startverzögerung", 1, 60),
            ("max_minutes", "Laufzeitlimit in Minuten", 0, 1440),
            ("target_every", "Zielwechsel-Intervall", 0.2, 3600),
            ("loot_every", "Loot-Intervall", 0.2, 3600),
            ("gather_every", "Sammel-Intervall", 0.2, 3600),
            ("combat_seconds", "Kampfdauer", 0.1, 3600),
            ("gather_seconds", "Sammeldauer", 0.1, 3600),
            ("mouse_interval", "Abstand der Mausklicks", 0.1, 30),
            ("mouse_hold", "Maus-Haltedauer", 0.02, 10),
            ("max_mana", "Maximales Mana", 0, 1000000),
        ):
            setattr(self, attr, number(getattr(self, attr), label, lo, hi))
        rounds = number(self.round_limit, "Rundenlimit", 0, 1000000)
        if not rounds.is_integer():
            raise ValueError("Das Rundenlimit muss eine ganze Zahl sein.")
        self.round_limit = int(rounds)
        parse_keys(self.target_key, optional=True)
        parse_keys(self.loot_key, optional=True)
        parse_keys(self.interact_key)
        parse_keys(self.movement_keys)
        if type(self.alternate_mouse) is not bool or type(self.vision_enabled) is not bool:
            raise ValueError("Maus- und HUD-Optionen müssen ein- oder ausgeschaltet sein.")
        if self.vision_size and (not isinstance(self.vision_size, list) or len(self.vision_size) != 2 or
                                 any(type(x) is not int or not 100 <= x <= 32000 for x in self.vision_size)):
            raise ValueError("Ungültige HUD-Auflösung.")
        validate_reference(self.mana_region, self.mana_reference, "Manabalken")
        if for_run and self.mode != "gather" and not self.skills and not self.alternate_mouse:
            raise ValueError("Mindestens einen Skill oder die abwechselnden Mausklicks aktivieren.")
        if len(self.skills) > 100 or len(self.route) > 20000:
            raise ValueError("Zu viele Skills oder Routenschritte.")
        for skill in self.skills:
            skill.validate()
        for step in self.route:
            step.validate()
        if for_run and self.route:
            required = {"combat"} if self.mode == "combat" else {"gather"}
            if self.mode == "combined":
                required = {"combat", "gather"}
            missing = required - {step.kind for step in self.route}
            if missing:
                names = {"combat": "Kämpfen", "gather": "Sammeln"}
                raise ValueError("In der Route fehlen Aktionspunkte: " +
                                 ", ".join(names[k] for k in sorted(missing)))

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2) + "\n"

    @classmethod
    def from_json(cls, value: str) -> Profile:
        try:
            raw = json.loads(value)
            if not isinstance(raw, dict):
                raise TypeError("Profil muss ein Objekt sein")
            raw["skills"] = [Skill(**x) for x in raw.get("skills", [])]
            raw["route"] = [Step(**x) for x in raw.get("route", [])]
            profile = cls(**raw)
            profile.validate()
            return profile
        except (TypeError, KeyError, AttributeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Ungültige Profildatei: {exc}") from None


def profile_directory() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    return base / "Aion2Farm" / "profiles"


def save_profile(path: Path, profile: Profile):
    profile.validate()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(profile.to_json(), encoding="utf-8")
    temporary.replace(path)
