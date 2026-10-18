import json
from pathlib import Path
import tempfile
import threading
import time
import unittest

from aion2_farm.engine import Runner
from aion2_farm.models import Profile, Skill, Step, parse_keys, save_profile
from aion2_farm.recorder import RouteRecorder


class FakeInput:
    def __init__(self):
        self.focus = True
        self.held = ()
        self.presses = []
        self.mouse = []
        self.pressed = threading.Event()
        self.lose_focus_on_press = False

    def has_focus(self):
        return self.focus

    def set_held(self, keys, stop_event):
        if not stop_event.is_set():
            self.held = tuple(keys)
            self.presses.append(tuple(keys))
            self.pressed.set()
            if self.lose_focus_on_press:
                self.focus = False

    def release_all(self):
        self.held = ()

    def move_mouse(self, dx, dy, stop_event):
        if not stop_event.is_set():
            self.mouse.append((dx, dy))


def fast_runner(profile, backend, events):
    runner = Runner(profile, backend, lambda kind, value: events.append((kind, value)),
                    preview=True, speed=1)
    wait = runner._wait
    def wait_without_startup(seconds, *, focus=True):
        if focus:
            return wait(seconds, focus=focus)
        runner._check(focus=False)
    runner._wait = wait_without_startup
    return runner


class ProfileTests(unittest.TestCase):
    def test_json_roundtrip_preserves_class_chords_and_routes(self):
        profile = Profile(class_name="Meine Klasse", skills=[Skill("shift+1", 8, .5)],
                          route=[Step("move", 1, "w+shift"), Step("combat", 1), Step("gather", 1)])
        restored = Profile.from_json(profile.to_json())
        restored.validate(for_run=True)
        self.assertEqual(profile, restored)

    def test_reject_invalid_or_reserved_keys(self):
        for value in ("", "f9", "ctrl+f8", "unknown", "w+"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_keys(value)
        self.assertEqual(parse_keys("strg+1"), ("ctrl", "1"))

    def test_reject_nonfinite_and_fractional_limits(self):
        for changes in ({"max_minutes": "nan"}, {"target_every": "inf"},
                        {"round_limit": "1.5"}, {"process": "C:/game.exe"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                Profile(**changes).validate()

    def test_unfinished_route_can_be_saved_but_cannot_run(self):
        profile = Profile(route=[Step("move", 1, "w")])
        profile.validate()
        with self.assertRaisesRegex(ValueError, "Aktionspunkte"):
            profile.validate(for_run=True)

    def test_malformed_import_and_unknown_schema_are_rejected(self):
        for value in ("[]", '{"skills": [3]}', '{"version":2}', '{"unexpected":true}', "{"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Profile.from_json(value)

    def test_save_does_not_destroy_existing_profile_on_invalid_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            save_profile(path, Profile())
            original = path.read_bytes()
            with self.assertRaises(ValueError):
                save_profile(path, Profile(countdown=-1))
            self.assertEqual(path.read_bytes(), original)
            self.assertFalse(path.with_suffix(".json.tmp").exists())


class RecorderTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.recorder = RouteRecorder({"w", "shift"}, lambda: self.now)

    def test_held_combinations_and_repeat_events(self):
        self.now = 1
        self.recorder.key_event("w", True)
        self.now = 2
        self.recorder.key_event("w", True)  # OS key-repeat must not split the route.
        self.recorder.key_event("shift", True)
        self.now = 3
        self.recorder.key_event("shift", False)
        self.now = 4
        self.recorder.key_event("w", False)
        self.now = 5
        steps = self.recorder.finish()
        self.assertEqual([(x.kind, x.keys, x.duration) for x in steps],
                         [("move", "w", 1), ("move", "shift+w", 1), ("move", "w", 1)])

    def test_markers_require_released_keys_and_ignore_unlisted_keys(self):
        self.recorder.key_event("1", True)
        self.assertTrue(self.recorder.marker("combat", 20))
        self.recorder.key_event("w", True)
        self.assertFalse(self.recorder.marker("gather", 6))
        self.now = 1
        self.recorder.key_event("w", False)
        self.assertTrue(self.recorder.marker("gather", 6))
        self.assertEqual([x.kind for x in self.recorder.finish()], ["combat", "move", "gather"])

    def test_late_events_after_finish_are_ignored(self):
        self.recorder.finish()
        self.now = 5
        self.recorder.key_event("w", True)
        self.assertEqual(self.recorder.finish(), [])


class EngineTests(unittest.TestCase):
    def test_mouse_alternates_and_at_most_one_skill_runs_between_clicks(self):
        backend, events = FakeInput(), []
        profile = Profile(mode="combat", round_limit=1, combat_seconds=2.5,
                          mouse_interval=.1, mouse_hold=.02, target_key="", loot_key="",
                          skills=[Skill("1", .1, 0, .02), Skill("2", .1, 0, .02)])
        runner = fast_runner(profile, backend, events)
        self.assertEqual(runner.run(), "completed")
        clicks = [key[0] for key in backend.presses if "mouse" in key[0]]
        self.assertGreaterEqual(len(clicks), 4)
        self.assertEqual(clicks, ["leftmouse" if i % 2 == 0 else "rightmouse" for i in range(len(clicks))])
        skills_since_click = 0
        for keys in backend.presses:
            if "mouse" in keys[0]:
                skills_since_click = 0
            else:
                skills_since_click += 1
                self.assertLessEqual(skills_since_click, 1)

    def test_unknown_hud_blocks_skills_while_basic_mouse_attacks_continue(self):
        backend, events = FakeInput(), []
        profile = Profile(mode="combat", round_limit=1, combat_seconds=.5, target_key="", loot_key="")
        runner = fast_runner(profile, backend, events)
        runner.preview = False
        self.assertEqual(runner.run(), "completed")
        self.assertTrue(backend.presses)
        self.assertTrue(all("mouse" in keys[0] for keys in backend.presses))

    def test_each_mode_executes_only_its_selected_actions(self):
        for mode in ("combat", "gather", "combined"):
            with self.subTest(mode=mode):
                profile = Profile(mode=mode, round_limit=1, target_key="", loot_key="",
                                  skills=[Skill("1", 1, 0)],
                                  route=[Step("combat", .3), Step("gather", .2)])
                backend, events = FakeInput(), []
                runner = fast_runner(profile, backend, events)
                self.assertEqual(runner.run(), "completed")
                self.assertEqual(("1",) in backend.presses, mode != "gather")
                self.assertEqual(("f",) in backend.presses, mode != "combat")
                self.assertEqual(runner.stats.rounds, 1)
                self.assertEqual(backend.held, ())

    def test_focus_loss_releases_keys_and_stops(self):
        profile = Profile(mode="combat", route=[Step("move", 10, "w"), Step("combat", 1)])
        backend, events = FakeInput(), []
        backend.lose_focus_on_press = True
        runner = fast_runner(profile, backend, events)
        self.assertEqual(runner.run(), "error")
        self.assertEqual(backend.held, ())
        self.assertEqual(backend.presses, [("w",)])
        self.assertTrue(any("Spielfokus" in str(value) for kind, value in events))

    def test_wrong_foreground_window_receives_no_keydowns(self):
        backend, events = FakeInput(), []
        backend.focus = False
        self.assertEqual(fast_runner(Profile(), backend, events).run(), "error")
        self.assertEqual(backend.presses, [])

    def test_stop_interrupts_long_movement_and_releases_held_key(self):
        backend, events = FakeInput(), []
        profile = Profile(mode="combat", route=[Step("move", 600, "w"), Step("combat", 1)])
        runner = fast_runner(profile, backend, events)
        thread = threading.Thread(target=runner.run)
        thread.start()
        self.assertTrue(backend.pressed.wait(.5))
        before = time.monotonic()
        runner.stop()
        self.assertEqual(backend.held, ())
        thread.join(.3)
        self.assertFalse(thread.is_alive())
        self.assertLess(time.monotonic() - before, .3)
        self.assertEqual(events[-1], ("finished", "stopped"))

    def test_stop_during_real_startup_sends_nothing(self):
        backend, events = FakeInput(), []
        runner = Runner(Profile(), backend, lambda k, v: events.append((k, v)))
        thread = threading.Thread(target=runner.run)
        thread.start()
        time.sleep(.03)
        runner.stop()
        thread.join(.3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(backend.presses, [])

    def test_runtime_limit_interrupts_a_long_route(self):
        backend, events = FakeInput(), []
        profile = Profile(mode="combat", max_minutes=.01,
                          route=[Step("move", 600, "w"), Step("combat", 1)])
        runner = fast_runner(profile, backend, events)
        self.assertEqual(runner.run(), "completed")
        self.assertEqual(backend.held, ())
        self.assertTrue(any("Laufzeitlimit" in str(v) for k, v in events))

    def test_low_cooldown_first_skill_does_not_starve_other_skills(self):
        backend, events = FakeInput(), []
        profile = Profile(mode="combat", round_limit=1, combat_seconds=2,
                          target_key="", loot_key="", skills=[Skill("1", .1, .2), Skill("2", .1, .2)])
        runner = fast_runner(profile, backend, events)
        runner.run()
        self.assertIn(("1",), backend.presses)
        self.assertIn(("2",), backend.presses)

    def test_camera_step_preserves_total_delta_and_releases_mouse_button(self):
        backend, events = FakeInput(), []
        profile = Profile(mode="gather", round_limit=1,
                          route=[Step("turn", .1, "rightmouse", 157, -13), Step("gather", .1)])
        runner = fast_runner(profile, backend, events)
        self.assertEqual(runner.run(), "completed")
        self.assertEqual(sum(x for x, y in backend.mouse), 157)
        self.assertEqual(sum(y for x, y in backend.mouse), -13)
        self.assertEqual(backend.held, ())

    def test_cleanup_failure_still_notifies_ui(self):
        backend, events = FakeInput(), []
        def broken_release():
            raise RuntimeError("release failed")
        backend.release_all = broken_release
        runner = fast_runner(Profile(mode="gather", round_limit=1, gather_seconds=.1), backend, events)
        self.assertEqual(runner.run(), "error")
        self.assertEqual(events[-1], ("finished", "error"))


if __name__ == "__main__":
    unittest.main()
