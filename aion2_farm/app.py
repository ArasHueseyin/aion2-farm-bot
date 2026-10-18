from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import queue
import re
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .engine import Runner
from .models import Profile, Skill, Step, number, parse_keys, profile_directory, save_profile
from .recorder import RouteRecorder
from .windows import KeyboardService, PreviewInput, WindowsInput, foreground_process

MODE_LABELS = {"combat": "Kampf", "gather": "Sammeln", "combined": "Kombiniert"}
KIND_LABELS = {"move": "Tasten halten", "turn": "Maus bewegen", "combat": "Kämpfen",
               "gather": "Sammeln", "wait": "Warten"}
BG, PANEL, TEXT, MUTED, ACCENT = "#10151e", "#192230", "#edf3fc", "#a5b4c9", "#58d9b1"


class App:
    def __init__(self, root: tk.Tk, *, enable_hotkeys=True):
        self.root = root
        self.events = queue.Queue()
        self.runner = None
        self.worker = None
        self.recorder = None
        self.record_backend = None
        self.record_pending = False
        self.record_generation = 0
        self.record_profile = None
        self.closed = False
        self.service = None
        self.vars: dict[str, tk.StringVar] = {}
        self.skills: list[Skill] = []
        self.route: list[Step] = []
        self.controls = []
        self.saved_profiles = {}
        self.profile_dir = profile_directory()
        self.last_focus_check = 0.0
        self._style()
        self._build()
        self._load(Profile())
        self._refresh_profiles()
        if enable_hotkeys:
            self.service = KeyboardService(self._hotkey, self._key,
                                           lambda text: self.emit("log", text))
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(50, self._drain)
        self.log("Bereit. Beispielbelegung an dein Spiel anpassen; Vorschau ist eingeschaltet.")

    def _style(self):
        self.root.title(f"AION2 Farm · {__version__}")
        self.root.geometry("1120x850")
        self.root.minsize(1000, 760)
        self.root.configure(bg=BG)
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10), background=BG, foreground=TEXT,
                        bordercolor="#304056", lightcolor=PANEL, darkcolor=PANEL,
                        troughcolor=BG, focuscolor=ACCENT)
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 25))
        style.configure("State.TLabel", font=("Segoe UI Semibold", 12), foreground=ACCENT)
        style.configure("TButton", background="#263549", padding=(12, 8))
        style.map("TButton", background=[("active", "#344a65"), ("disabled", "#202937")],
                  foreground=[("disabled", "#77869b")])
        style.configure("Go.TButton", background="#236955", foreground="#ffffff")
        style.map("Go.TButton", background=[("active", "#31886e"), ("disabled", "#263549")])
        style.configure("Stop.TButton", background="#793b45", foreground="white")
        style.configure("TEntry", fieldbackground=PANEL, foreground=TEXT, padding=5)
        style.configure("TCombobox", fieldbackground=PANEL, foreground=TEXT, padding=5,
                        arrowcolor=TEXT)
        style.map("TCombobox", fieldbackground=[("readonly", PANEL)],
                  foreground=[("readonly", TEXT)])
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL, padding=(18, 9))
        style.map("TNotebook.Tab", background=[("selected", "#2a4054")],
                  foreground=[("disabled", "#78879b")])
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL,
                        foreground=TEXT, rowheight=29, borderwidth=0)
        style.configure("Treeview.Heading", background="#263549", foreground=TEXT, padding=5)
        style.map("Treeview", background=[("selected", "#365972")])
        style.configure("TLabelframe", padding=12)
        style.configure("TLabelframe.Label", foreground=ACCENT)
        self.root.option_add("*TCombobox*Listbox.background", PANEL)
        self.root.option_add("*TCombobox*Listbox.foreground", TEXT)

    def _build(self):
        outer = ttk.Frame(self.root, padding=22)
        outer.pack(fill="both", expand=True)
        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 15))
        ttk.Label(header, text="AION2 FARM", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text=f"v{__version__}  ·  WINDOWS", style="Muted.TLabel").pack(side="right")
        ttk.Label(outer, text="Eigene Klassenprofile. Aufnehmbare Tastaturrouten. Kampf und Sammeln kombinieren.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 15))
        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=(0, 15))
        self.profile_picker = ttk.Combobox(bar, state="readonly", width=30)
        self.profile_picker.pack(side="left", padx=(0, 8))
        self.profile_picker.bind("<<ComboboxSelected>>", self._select_profile)
        self.controls.append(self.profile_picker)
        for text, command in (("Neu", self._new), ("Speichern", self._save),
                              ("Importieren", self._import), ("Exportieren", self._export)):
            button = ttk.Button(bar, text=text, command=command)
            button.pack(side="left", padx=3)
            self.controls.append(button)
        modes = ttk.Frame(outer)
        modes.pack(fill="x", pady=(0, 12))
        ttk.Label(modes, text="Farmmodus", style="Muted.TLabel").pack(side="left", padx=(0, 14))
        self.mode = tk.StringVar(value="combined")
        for key, label in MODE_LABELS.items():
            radio = ttk.Radiobutton(modes, text=label, variable=self.mode, value=key)
            radio.pack(side="left", padx=(0, 20))
            self.controls.append(radio)

        self.tabs = ttk.Notebook(outer, height=280)
        self.tabs.pack(fill="both", expand=True)
        profile_tab, combat_tab, gather_tab, route_tab = [ttk.Frame(self.tabs, padding=16) for _ in range(4)]
        for tab, text in zip((profile_tab, combat_tab, gather_tab, route_tab),
                             ("Profil & Laufzeit", "Kampf & Skills", "Sammeln", "Route")):
            self.tabs.add(tab, text=text)
        self._profile_tab(profile_tab)
        self._combat_tab(combat_tab)
        self._gather_tab(gather_tab)
        self._route_tab(route_tab)

        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=(14, 10))
        self.start_button = ttk.Button(controls, text="Start  ·  F8", command=self.start, style="Go.TButton")
        self.start_button.pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="Stopp  ·  F9", command=self.stop, style="Stop.TButton").pack(side="left")
        self.preview = tk.BooleanVar(value=True)
        self.preview_check = ttk.Checkbutton(controls, text="Vorschau (10×, ohne Eingaben)", variable=self.preview)
        self.preview_check.pack(side="left", padx=18)
        self.controls.extend((self.start_button, self.preview_check))
        self.status = tk.StringVar(value="Bereit")
        ttk.Label(controls, textvariable=self.status, style="State.TLabel").pack(side="right")
        self.stats_text = tk.StringVar(value="0 Runden   ·   0 Skills   ·   0 Sammelversuche   ·   00:00")
        ttk.Label(outer, textvariable=self.stats_text, style="Muted.TLabel").pack(anchor="w", pady=(0, 6))
        self.logbox = tk.Text(outer, height=4, bg="#0c1119", fg=MUTED, insertbackground=TEXT,
                              relief="flat", font=("Consolas", 9), padx=10, pady=8, state="disabled")
        self.logbox.pack(fill="x")
        self.focus_text = tk.StringVar(value="Aktives Fenster: —")
        ttk.Label(outer, textvariable=self.focus_text, style="Muted.TLabel").pack(anchor="w", pady=(6, 0))

    def _field(self, parent, key, label, row, column=0, width=25):
        ttk.Label(parent, text=label).grid(row=row * 2, column=column, sticky="w", padx=(0, 25), pady=(2, 2))
        variable = self.vars[key] = tk.StringVar()
        entry = ttk.Entry(parent, textvariable=variable, width=width)
        entry.grid(row=row * 2 + 1, column=column, sticky="ew", padx=(0, 25), pady=(0, 5))
        parent.columnconfigure(column, weight=1)
        return entry

    def _profile_tab(self, tab):
        form = ttk.Frame(tab)
        form.pack(fill="x")
        for key, label, row, column in (
            ("name", "Profilname", 0, 0), ("class_name", "Klasse / Charakter (frei wählbar)", 0, 1),
            ("process", "Spielprozess (Dateiname)", 1, 0), ("countdown", "Startverzögerung in Sekunden", 1, 1),
            ("max_minutes", "Laufzeitlimit in Minuten · 0 = unbegrenzt", 2, 0),
            ("round_limit", "Rundenlimit · 0 = unbegrenzt", 2, 1),
        ):
            self._field(form, key, label, row, column)
        ttk.Label(tab, text="Live-Eingaben werden nur an den eingestellten Spielprozess im Vordergrund gesendet.\n"
                  "Beim Fensterwechsel stoppt der Lauf. F9 gibt gehaltene Tasten sofort frei.\n"
                  "Beispielbelegungen anpassen. Jede Klasse verwendet ihre eigene Skillfolge.\n"
                  "Aion2 verbietet Bots und unbeaufsichtigte Makros; ein Einsatz kann zur Accountsperre führen.",
                  style="Muted.TLabel", wraplength=920, justify="left").pack(anchor="w", pady=(10, 0))

    def _combat_tab(self, tab):
        form = ttk.Frame(tab)
        form.pack(fill="x")
        for key, label, row, column in (
            ("target_key", "Zielwechsel-Taste · leer = aus", 0, 0),
            ("target_every", "Zielwechsel alle … Sekunden", 0, 1),
            ("loot_key", "Loot-Taste · leer = aus", 0, 2),
            ("loot_every", "Looten alle … Sekunden", 0, 3),
            ("combat_seconds", "Kampfpunkt: Standarddauer in Sekunden", 1, 0),
        ):
            self._field(form, key, label, row, column, 16)
        ttk.Label(tab, text="Skillfolge · bereite Skills der Reihe nach; Cooldowns gelten auch zwischen Kampfpunkten.",
                  style="Muted.TLabel").pack(anchor="w", pady=(6, 7))
        buttons = ttk.Frame(tab)
        buttons.pack(side="bottom", fill="x", pady=(8, 0))
        for label, command in (("Skill hinzufügen", self._skill_dialog),
                                ("Bearbeiten", lambda: self._skill_dialog(edit=True)),
                                ("Entfernen", self._delete_skill)):
            ttk.Button(buttons, text=label, command=command).pack(side="left", padx=(0, 6))
        self.skill_tree = self._tree(tab, ("key", "cooldown", "pause"),
                                     ("Taste / Kombination", "Cooldown (s)", "Pause nach Taste (s)"), 5)
        self.skill_tree.bind("<Double-1>", lambda e: self._skill_dialog(edit=True))

    def _gather_tab(self, tab):
        form = ttk.Frame(tab)
        form.pack(fill="x")
        self._field(form, "interact_key", "Sammeln / Interagieren: Taste", 0, 0)
        self._field(form, "gather_every", "Interagieren alle … Sekunden", 0, 1)
        self._field(form, "gather_seconds", "Sammelpunkt: Standarddauer in Sekunden", 1, 0)
        ttk.Label(tab, text="Setze in der Route Sammelpunkte dort, wo dein Charakter vor einer Ressource steht.\n"
                  "Am Punkt wird die Interaktionstaste für die eingestellte Dauer wiederholt.\n\n"
                  "Ohne Route bleibt der Charakter am aktuellen Standort. Im kombinierten Modus\n"
                  "wechseln sich Kampf und Sammeln dort ab.\n\n"
                  "Die erste Version arbeitet mit festen Zeiten und Wegen. Sie erkennt keine Gegner,\n"
                  "Ressourcen, Hindernisse, Lebenspunkte oder vollen Taschen.",
                  style="Muted.TLabel", justify="left", wraplength=900).pack(anchor="w", pady=(20, 0))

    def _route_tab(self, tab):
        self._field(tab, "movement_keys", "Aufnahme: diese Tastaturtasten mitschreiben", 0, width=65)
        ttk.Label(tab, text="F10 Aufnahme starten/beenden  ·  F6 Kampfpunkt  ·  F7 Sammelpunkt  ·  F9 abbrechen\n"
                  "Vor einem Aktionspunkt Bewegungstasten loslassen. Aufnahmen werden hinten angehängt.\n"
                  "Kamera-Mausbewegungen werden nicht aufgenommen; als eigenen Schritt ergänzen.",
                  style="Muted.TLabel", wraplength=950).grid(row=2, column=0, sticky="w", pady=(0, 8))
        container = ttk.Frame(tab)
        container.grid(row=3, column=0, sticky="nsew")
        tab.rowconfigure(3, weight=1)
        self.route_tree = self._tree(container, ("index", "kind", "keys", "duration", "mouse"),
                                     ("#", "Aktion", "Tasten", "Dauer (s)", "Maus X / Y"), 5)
        for col, width in (("index", 40), ("kind", 150), ("keys", 190), ("duration", 100), ("mouse", 130)):
            self.route_tree.column(col, width=width)
        self.route_tree.bind("<Double-1>", lambda e: self._step_dialog(edit=True))
        buttons = ttk.Frame(tab)
        buttons.grid(row=4, column=0, sticky="w", pady=(9, 0))
        for label, command in (("Aufnahme · F10", self.toggle_record),
                                ("Schritt +", self._step_dialog),
                                ("Bearbeiten", lambda: self._step_dialog(edit=True)),
                                ("↑", lambda: self._move_step(-1)), ("↓", lambda: self._move_step(1)),
                                ("Entfernen", self._delete_step), ("Leeren", self._clear_route)):
            ttk.Button(buttons, text=label, command=command).pack(side="left", padx=(0, 5))

    def _tree(self, parent, columns, headings, height):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=height, selectmode="browse")
        for key, label in zip(columns, headings):
            tree.heading(key, text=label)
            tree.column(key, width=150)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        return tree

    def _busy(self):
        return self.runner is not None or self.recorder is not None or self.record_pending

    def _set_busy(self, busy):
        for control in self.controls:
            if isinstance(control, ttk.Combobox):
                control.configure(state="disabled" if busy else "readonly")
            else:
                control.state(["disabled"] if busy else ["!disabled"])
        def update_children(parent):
            for child in parent.winfo_children():
                if isinstance(child, (ttk.Entry, ttk.Button, ttk.Combobox)):
                    child.state(["disabled"] if busy else ["!disabled"])
                update_children(child)
        update_children(self.tabs)

    def _read(self, *, validate=True):
        raw = {key: variable.get() for key, variable in self.vars.items()}
        raw.update(mode=self.mode.get(), skills=copy.deepcopy(self.skills), route=copy.deepcopy(self.route))
        profile = Profile(**raw)
        if validate:
            profile.validate()
        return profile

    def _load(self, profile):
        for key, variable in self.vars.items():
            variable.set(str(getattr(profile, key)))
        self.mode.set(profile.mode)
        self.skills = copy.deepcopy(profile.skills)
        self.route = copy.deepcopy(profile.route)
        self._render_skills()
        self._render_route()

    def _refresh_profiles(self, selected=None):
        self.saved_profiles = {}
        if self.profile_dir.exists():
            for path in sorted(self.profile_dir.glob("*.json")):
                try:
                    profile = Profile.from_json(path.read_text(encoding="utf-8"))
                    label = profile.name
                    if label in self.saved_profiles:
                        label += " · " + path.stem
                    self.saved_profiles[label] = path
                except (OSError, ValueError) as exc:
                    self.log(f"Profil übersprungen: {path.name}: {exc}")
        self.profile_picker["values"] = list(self.saved_profiles)
        self.profile_picker.set(selected or "Gespeichertes Profil wählen")

    def _select_profile(self, event=None):
        if self._busy():
            return
        try:
            path = self.saved_profiles[self.profile_picker.get()]
            profile = Profile.from_json(path.read_text(encoding="utf-8"))
            self._load(profile)
            self.log("Profil geladen: " + profile.name)
        except (OSError, ValueError, KeyError) as exc:
            self.error(exc)

    def _new(self):
        if not self._busy():
            self._load(Profile())
            self.profile_picker.set("Neues Profil")

    def _save(self):
        try:
            profile = self._read()
            slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", profile.name).strip("-")[:60] or "profil"
            digest = hashlib.sha256(profile.name.encode()).hexdigest()[:8]
            path = self.profile_dir / f"{slug}-{digest}.json"
            save_profile(path, profile)
            self._refresh_profiles(profile.name)
            self.log("Gespeichert: " + str(path))
        except (ValueError, OSError) as exc:
            self.error(exc)

    def _import(self):
        path = filedialog.askopenfilename(parent=self.root, filetypes=[("Farm-Profil", "*.json")])
        if path:
            try:
                self._load(Profile.from_json(Path(path).read_text(encoding="utf-8-sig")))
                self.log("Importiert: " + path)
            except (OSError, ValueError) as exc:
                self.error(exc)

    def _export(self):
        try:
            profile = self._read()
            path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".json",
                                               initialfile="aion2-profil.json", filetypes=[("Farm-Profil", "*.json")])
            if path:
                save_profile(Path(path), profile)
                self.log("Exportiert: " + path)
        except (OSError, ValueError) as exc:
            self.error(exc)

    def _selected(self, tree):
        values = tree.selection()
        return int(values[0]) if values else None

    def _render_skills(self):
        self.skill_tree.delete(*self.skill_tree.get_children())
        for index, skill in enumerate(self.skills):
            self.skill_tree.insert("", "end", iid=str(index), values=(skill.key, skill.cooldown, skill.pause))

    def _render_route(self, select=None):
        self.route_tree.delete(*self.route_tree.get_children())
        for index, step in enumerate(self.route):
            self.route_tree.insert("", "end", iid=str(index), values=(index + 1, KIND_LABELS[step.kind],
                                   step.keys if step.kind in ("move", "turn") else "—", f"{step.duration:.3f}".rstrip("0").rstrip("."),
                                   f"{step.dx} / {step.dy}" if step.kind == "turn" else "—"))
        if select is not None and 0 <= select < len(self.route):
            self.route_tree.selection_set(str(select))
            self.route_tree.see(str(select))

    def _dialog(self, title, fields, initial, apply, *, kind=False):
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.configure(bg=BG)
        dialog.transient(self.root)
        dialog.resizable(False, False)
        body = ttk.Frame(dialog, padding=20)
        body.pack(fill="both", expand=True)
        values = {}
        for row, (key, label) in enumerate(fields):
            ttk.Label(body, text=label).grid(row=row, column=0, sticky="w", padx=(0, 20), pady=6)
            var = values[key] = tk.StringVar(value=str(initial[key]))
            if key == "kind":
                entry = ttk.Combobox(body, textvariable=var, state="readonly", values=list(KIND_LABELS.values()), width=28)
                def on_kind(event):
                    selected_kind = values["kind"].get()
                    if selected_kind == KIND_LABELS["turn"] and values["keys"].get() == "w":
                        values["keys"].set("rightmouse")
                    elif selected_kind == KIND_LABELS["move"] and values["keys"].get() == "rightmouse":
                        values["keys"].set("w")
                entry.bind("<<ComboboxSelected>>", on_kind)
            else:
                entry = ttk.Entry(body, textvariable=var, width=31)
            entry.grid(row=row, column=1, pady=6)
        ttk.Label(body, text="Tasten z. B. 1, shift+1, w+shift, rightmouse.\nF6–F10 sind für die Steuerung reserviert.",
                  style="Muted.TLabel").grid(row=len(fields), columnspan=2, sticky="w", pady=10)
        def submit():
            try:
                apply({key: var.get() for key, var in values.items()})
                dialog.destroy()
            except ValueError as exc:
                messagebox.showerror("Eingabe prüfen", str(exc), parent=dialog)
        ttk.Button(body, text="Übernehmen", command=submit, style="Go.TButton").grid(row=len(fields) + 1, column=1, sticky="e")
        dialog.bind("<Return>", lambda event: submit())
        dialog.bind("<Escape>", lambda event: dialog.destroy())
        dialog.grab_set()

    def _skill_dialog(self, edit=False):
        if self._busy():
            return
        index = self._selected(self.skill_tree) if edit else None
        if edit and index is None:
            return
        skill = self.skills[index] if index is not None else Skill()
        def apply(values):
            replacement = Skill(**values)
            replacement.validate()
            if index is None:
                self.skills.append(replacement)
            else:
                self.skills[index] = replacement
            self._render_skills()
        self._dialog("Skill bearbeiten", [("key", "Taste / Kombination"), ("cooldown", "Cooldown in Sekunden"),
                                         ("pause", "Pause nach Taste in Sekunden")], vars(skill), apply)

    def _delete_skill(self):
        index = self._selected(self.skill_tree)
        if not self._busy() and index is not None:
            self.skills.pop(index)
            self._render_skills()

    def _step_dialog(self, edit=False):
        if self._busy():
            return
        index = self._selected(self.route_tree) if edit else None
        if edit and index is None:
            return
        step = self.route[index] if index is not None else Step()
        initial = vars(step).copy()
        initial["kind"] = KIND_LABELS[step.kind]
        def apply(values):
            values["kind"] = next(key for key, label in KIND_LABELS.items() if label == values["kind"])
            replacement = Step(**values)
            replacement.validate()
            if index is None:
                self.route.append(replacement)
            else:
                self.route[index] = replacement
            self._render_route(index if index is not None else len(self.route) - 1)
        self._dialog("Routenschritt", [("kind", "Aktion"), ("duration", "Dauer in Sekunden"),
                                       ("keys", "Gehaltene Tasten (Bewegen / Maus)"),
                                       ("dx", "Mausbewegung X (relativ)"), ("dy", "Mausbewegung Y (relativ)")],
                     initial, apply, kind=True)

    def _delete_step(self):
        index = self._selected(self.route_tree)
        if not self._busy() and index is not None:
            self.route.pop(index)
            self._render_route(min(index, len(self.route) - 1))

    def _move_step(self, offset):
        index = self._selected(self.route_tree)
        if not self._busy() and index is not None and 0 <= index + offset < len(self.route):
            self.route[index], self.route[index + offset] = self.route[index + offset], self.route[index]
            self._render_route(index + offset)

    def _clear_route(self):
        if not self._busy() and self.route and messagebox.askyesno("Route leeren", "Alle Routenschritte entfernen?", parent=self.root):
            self.route.clear()
            self._render_route()

    def emit(self, kind, data):
        self.events.put((kind, data))

    def _hotkey(self, command):
        if command == "stop" and self.runner:
            self.runner.stop()
        self.emit("command", command)

    def _key(self, key, pressed):
        recorder, backend = self.recorder, self.record_backend
        if recorder and backend:
            if backend.has_focus():
                recorder.key_event(key, pressed)
            else:
                self.emit("record_focus_lost", None)

    def start(self):
        if self._busy():
            return
        try:
            profile = self._read()
            profile.validate(for_run=True)
            preview = self.preview.get()
            if not preview and (not self.service or "stop" not in self.service.registered):
                raise ValueError("Live-Start gesperrt: F9 konnte nicht als globaler Stopp-Hotkey registriert werden.")
            backend = PreviewInput(self.emit) if preview else WindowsInput(profile.process)
            self.runner = Runner(profile, backend, self.emit, preview=preview, speed=10)
            self._set_busy(True)
            self.status.set("VORSCHAU" if preview else "LIVE · Startverzögerung")
            self.worker = threading.Thread(target=self.runner.run, name="farm-runner", daemon=True)
            self.worker.start()
        except ValueError as exc:
            self.error(exc)

    def stop(self):
        if self.runner:
            self.runner.stop()
        if self.record_pending:
            self.record_pending = False
            self.record_generation += 1
            self._set_busy(False)
            self.status.set("Bereit")
            self.log("Aufnahmevorbereitung abgebrochen.")
        if self.recorder:
            self._finish_record()

    def toggle_record(self):
        if self.recorder:
            self._finish_record()
            return
        if self.record_pending:
            self.stop()
            return
        if self.runner:
            return
        try:
            if not self.service or not getattr(self.service, "hook_available", False) or "stop" not in self.service.registered:
                raise ValueError("Aufnahme nicht verfügbar: Tastatur-Hook und globaler F9-Hotkey werden benötigt.")
            profile = self._read()
            self.record_profile = profile
            self.record_pending = True
            self.record_generation += 1
            generation = self.record_generation
            self._set_busy(True)
            self.status.set("Aufnahme vorbereitet")
            self.log(f"Aufnahme startet in {profile.countdown:g} s. Zum Spiel wechseln. F10 beendet, F9 stoppt.")
            self.root.after(int(profile.countdown * 1000), lambda: self._begin_record(generation))
        except ValueError as exc:
            self.error(exc)

    def _begin_record(self, generation):
        if self.closed or not self.record_pending or generation != self.record_generation:
            return
        profile = self.record_profile
        backend = WindowsInput(profile.process)
        self.record_pending = False
        if not backend.has_focus():
            self._set_busy(False)
            self.status.set("Bereit")
            self.log("Aufnahme nicht gestartet: Spiel ist nicht im Vordergrund.")
            return
        self.record_backend = backend
        self.recorder = RouteRecorder(parse_keys(profile.movement_keys))
        self.status.set("AUFNAHME · F10 beendet")
        self.log("Aufnahme läuft. F6 setzt Kampf-, F7 Sammelpunkte. Kamera wird nicht aufgenommen.")

    def _finish_record(self):
        recorder = self.recorder
        self.recorder = None
        self.record_backend = None
        if recorder:
            steps = recorder.finish()
            self.route.extend(steps)
            self._render_route()
            self.log(f"Aufnahme beendet: {len(steps)} Schritte angehängt. Profil speichern.")
        self._set_busy(False)
        self.status.set("Bereit")

    def _marker(self, kind):
        if not self.recorder:
            return
        duration = self.record_profile.combat_seconds if kind == "combat" else self.record_profile.gather_seconds
        if self.recorder.marker(kind, duration):
            self.log(f"{KIND_LABELS[kind]}-Punkt gesetzt ({duration:g} s).")
        else:
            self.log("Für einen Aktionspunkt zuerst alle Bewegungstasten loslassen.")

    def _drain(self):
        if self.closed:
            return
        for _ in range(250):
            try:
                kind, data = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self.log(data)
            elif kind == "phase":
                prefix = "VORSCHAU · " if self.runner and self.runner.preview else "LIVE · "
                self.status.set(prefix + data)
            elif kind == "stats":
                seconds = int(data["elapsed"])
                self.stats_text.set(f"{data['rounds']} Runden   ·   {data['skills']} Skills   ·   "
                                    f"{data['gathers']} Sammelversuche   ·   {seconds // 60:02d}:{seconds % 60:02d}")
            elif kind == "finished":
                self.runner = None
                self.worker = None
                self._set_busy(False)
                self.status.set({"completed": "Abgeschlossen", "stopped": "Gestoppt", "error": "Fehler – siehe Log"}[data])
            elif kind == "command":
                {"start": self.start, "stop": self.stop, "record": self.toggle_record,
                 "combat_marker": lambda: self._marker("combat"),
                 "gather_marker": lambda: self._marker("gather")}[data]()
            elif kind == "record_focus_lost" and self.recorder:
                self._finish_record()
                self.log("Aufnahme gestoppt: Spielfokus verloren.")
        if time.monotonic() - self.last_focus_check > 0.7:
            self.last_focus_check = time.monotonic()
            name = foreground_process()[0]
            self.focus_text.set("Aktives Fenster: " + (name or "nicht lesbar") + "   ·   Profile werden lokal gespeichert")
            if self.recorder and self.record_backend and not self.record_backend.has_focus():
                self._finish_record()
                self.log("Aufnahme gestoppt: Spielfokus verloren.")
        self.root.after(50, self._drain)

    def log(self, text):
        self.logbox.configure(state="normal")
        self.logbox.insert("end", time.strftime("%H:%M:%S") + "  " + text + "\n")
        lines = int(self.logbox.index("end-1c").split(".")[0])
        if lines > 500:
            self.logbox.delete("1.0", f"{lines - 500}.0")
        self.logbox.see("end")
        self.logbox.configure(state="disabled")

    def error(self, error):
        self.log(str(error))
        messagebox.showerror("Eingabe prüfen", str(error), parent=self.root)

    def close(self):
        self.closed = True
        self.stop()
        if self.worker:
            self.worker.join(timeout=1)
        if self.service:
            self.service.close()
        self.root.destroy()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--report")
    parser.add_argument("--screenshot")
    args = parser.parse_args()
    root = tk.Tk()
    app = App(root, enable_hotkeys=not args.smoke_test)
    if args.smoke_test:
        # Exercise the complete preview path without registering hooks or sending input.
        app.vars["countdown"].set("1")
        app.vars["round_limit"].set("1")
        app.vars["combat_seconds"].set("1")
        app.vars["gather_seconds"].set("0.5")
        app.start()
        deadline = time.monotonic() + 6
        while app.runner and time.monotonic() < deadline:
            root.update()
            time.sleep(0.02)
        root.update()
        result = {"ok": app.runner is None and app.status.get() == "Abgeschlossen" and bool(app.tabs.select()),
                  "version": __version__, "status": app.status.get(), "stats": app.stats_text.get()}
        if args.screenshot:
            from PIL import ImageGrab
            root.lift()
            root.update()
            time.sleep(0.15)
            x, y = root.winfo_rootx(), root.winfo_rooty()
            ImageGrab.grab(bbox=(x, y, x + root.winfo_width(), y + root.winfo_height())).save(args.screenshot)
        if args.report:
            Path(args.report).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        app.close()
        raise SystemExit(0 if result["ok"] else 1)
    root.mainloop()
