import ctypes
import sys
import threading
import unittest
from unittest.mock import patch


@unittest.skipUnless(sys.platform == "win32", "Windows input adapter")
class WindowsInputTests(unittest.TestCase):
    def test_native_input_struct_has_correct_abi_size(self):
        from aion2_farm.windows import INPUT
        self.assertEqual(ctypes.sizeof(INPUT), 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)

    def test_focus_guard_prevents_any_keydown(self):
        from aion2_farm.windows import WindowsInput
        backend = WindowsInput("Aion2.exe")
        with patch.object(backend, "has_focus", return_value=False), patch.object(backend, "_send") as send:
            with self.assertRaises(RuntimeError):
                backend.set_held(("w",), threading.Event())
            send.assert_not_called()

    def test_emergency_stop_prevents_late_keydown(self):
        from aion2_farm.windows import WindowsInput
        backend = WindowsInput("Aion2.exe")
        stopped = threading.Event()
        stopped.set()
        with patch.object(backend, "_send") as send:
            backend.set_held(("w",), stopped)
            backend.move_mouse(10, 10, stopped)
            send.assert_not_called()

    def test_releases_use_cached_scancode_even_after_layout_changes(self):
        from aion2_farm.windows import WindowsInput
        backend = WindowsInput("Aion2.exe")
        with patch.object(backend, "has_focus", return_value=True), \
             patch.object(backend, "_packet", side_effect=lambda key, up=False: f"{key}-{up}"), \
             patch.object(backend, "_send") as send:
            backend.set_held(("shift", "w"), threading.Event())
            backend.release_all()
            self.assertEqual([call.args[0] for call in send.call_args_list],
                             ["shift-False", "w-False", "w-True", "shift-True"])
            self.assertEqual(backend.held, {})


if __name__ == "__main__":
    unittest.main()
