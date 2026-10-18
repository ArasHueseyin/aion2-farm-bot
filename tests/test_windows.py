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
             patch.object(backend, "_check_rights"), \
             patch.object(backend, "_packet", side_effect=lambda key, up=False: f"{key}-{up}"), \
             patch.object(backend, "_send") as send:
            backend.set_held(("shift", "w"), threading.Event())
            backend.release_all()
            self.assertEqual([call.args[0] for call in send.call_args_list],
                             ["shift-False", "w-False", "w-True", "shift-True"])
            self.assertEqual(backend.held, {})

    def test_mouse_packets_are_real_button_events(self):
        from aion2_farm.windows import WindowsInput
        backend = WindowsInput("Aion2.exe")
        for name, down, up in (("leftmouse", 2, 4), ("rightmouse", 8, 16)):
            self.assertEqual(backend._packet(name).mi.dwFlags, down)
            self.assertEqual(backend._packet(name, up=True).mi.dwFlags, up)

    def test_virtual_key_method_encodes_vk_and_release(self):
        from aion2_farm.windows import WindowsInput
        backend = WindowsInput("Aion2.exe", "virtual")
        self.assertEqual(backend._packet("1").ki.wVk, ord("1"))
        self.assertEqual(backend._packet("1", up=True).ki.dwFlags, 2)

    def test_window_messages_keep_target_and_keyboard_release_bits(self):
        from aion2_farm.windows import WindowsInput, WindowMessage
        backend = WindowsInput("Aion2.exe", "messages")
        with patch("aion2_farm.windows.user32.GetForegroundWindow", return_value=123), \
             patch("aion2_farm.windows.foreground_process", return_value=("Aion2.exe", 1)):
            packet = backend._packet("1", up=True)
        self.assertIsInstance(packet, WindowMessage)
        self.assertEqual(packet.hwnd, 123)
        self.assertEqual(packet.message, 0x101)
        self.assertEqual(packet.wparam, ord("1"))
        self.assertEqual(packet.lparam & 0xC0000000, 0xC0000000)

    def test_higher_game_integrity_blocks_before_any_send(self):
        from aion2_farm.windows import WindowsInput
        backend = WindowsInput("Aion2.exe")
        backend.own_integrity = 0x2000
        with patch.object(backend, "has_focus", return_value=True), \
             patch("aion2_farm.windows.process_integrity", return_value=0x3000), \
             patch.object(backend, "_send") as send:
            with self.assertRaises(PermissionError):
                backend.set_held(("1",), threading.Event())
            send.assert_not_called()

    def test_permission_diagnostic_blocks_mismatch_but_allows_equal_levels(self):
        from aion2_farm.windows import check_input_permissions
        with patch("aion2_farm.windows.inspect_game", return_value={"status":"rights", "message":"Higher integrity"}):
            with self.assertRaises(PermissionError):
                check_input_permissions("Aion2.exe")
        with patch("aion2_farm.windows.inspect_game", return_value={"status":"ready", "message":"OK"}):
            self.assertEqual(check_input_permissions("Aion2.exe")["status"], "ready")


if __name__ == "__main__":
    unittest.main()
