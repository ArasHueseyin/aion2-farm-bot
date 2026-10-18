from __future__ import annotations

import ctypes as C
from ctypes import wintypes as W
import os
import threading

user32 = C.WinDLL("user32", use_last_error=True)
kernel32 = C.WinDLL("kernel32", use_last_error=True)
ULONG_PTR = C.c_size_t
LRESULT = C.c_ssize_t


class MOUSEINPUT(C.Structure):
    _fields_ = [("dx", W.LONG), ("dy", W.LONG), ("mouseData", W.DWORD),
                ("dwFlags", W.DWORD), ("time", W.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(C.Structure):
    _fields_ = [("wVk", W.WORD), ("wScan", W.WORD), ("dwFlags", W.DWORD),
                ("time", W.DWORD), ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(C.Structure):
    _fields_ = [("uMsg", W.DWORD), ("wParamL", W.WORD), ("wParamH", W.WORD)]


class INPUTUNION(C.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(C.Structure):
    _anonymous_ = ("value",)
    _fields_ = [("type", W.DWORD), ("value", INPUTUNION)]


class KBDLLHOOKSTRUCT(C.Structure):
    _fields_ = [("vkCode", W.DWORD), ("scanCode", W.DWORD), ("flags", W.DWORD),
                ("time", W.DWORD), ("dwExtraInfo", ULONG_PTR)]


HOOKPROC = C.WINFUNCTYPE(LRESULT, C.c_int, W.WPARAM, W.LPARAM)
user32.SendInput.argtypes = [W.UINT, C.POINTER(INPUT), C.c_int]
user32.SendInput.restype = W.UINT
user32.GetForegroundWindow.restype = W.HWND
user32.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
user32.GetWindowThreadProcessId.restype = W.DWORD
user32.GetKeyboardLayout.argtypes = [W.DWORD]
user32.GetKeyboardLayout.restype = W.HANDLE
user32.MapVirtualKeyExW.argtypes = [W.UINT, W.UINT, W.HANDLE]
user32.MapVirtualKeyExW.restype = W.UINT
kernel32.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
kernel32.OpenProcess.restype = W.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)]
kernel32.QueryFullProcessImageNameW.restype = W.BOOL
kernel32.CloseHandle.argtypes = [W.HANDLE]
kernel32.GetModuleHandleW.argtypes = [W.LPCWSTR]
kernel32.GetModuleHandleW.restype = W.HMODULE
kernel32.GetCurrentThreadId.restype = W.DWORD
user32.SetWindowsHookExW.argtypes = [C.c_int, HOOKPROC, W.HINSTANCE, W.DWORD]
user32.SetWindowsHookExW.restype = W.HHOOK
user32.CallNextHookEx.argtypes = [W.HHOOK, C.c_int, W.WPARAM, W.LPARAM]
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = [W.HHOOK]
user32.RegisterHotKey.argtypes = [W.HWND, C.c_int, W.UINT, W.UINT]
user32.RegisterHotKey.restype = W.BOOL
user32.UnregisterHotKey.argtypes = [W.HWND, C.c_int]
user32.GetMessageW.argtypes = [C.POINTER(W.MSG), W.HWND, W.UINT, W.UINT]
user32.GetMessageW.restype = C.c_int
user32.PostThreadMessageW.argtypes = [W.DWORD, W.UINT, W.WPARAM, W.LPARAM]

VK = {key: ord(key.upper()) for key in "abcdefghijklmnopqrstuvwxyz0123456789"}
VK.update({f"f{i}": 0x6F + i for i in range(1, 13)})
VK.update({"tab": 0x09, "space": 0x20, "enter": 0x0D, "escape": 0x1B,
           "shift": 0xA0, "ctrl": 0xA2, "alt": 0xA4, "backspace": 0x08,
           "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
           "home": 0x24, "end": 0x23, "insert": 0x2D, "delete": 0x2E,
           "pageup": 0x21, "pagedown": 0x22})
KEY_FROM_VK = {value: key for key, value in VK.items()}
KEY_FROM_VK.update({0x10: "shift", 0x11: "ctrl", 0x12: "alt",
                    0xA1: "shift", 0xA3: "ctrl", 0xA5: "alt"})
MOUSE_FLAGS = {"leftmouse": (0x0002, 0x0004), "rightmouse": (0x0008, 0x0010),
               "middlemouse": (0x0020, 0x0040)}


def foreground_process() -> tuple[str, int]:
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return "", 0
    pid = W.DWORD()
    thread = user32.GetWindowThreadProcessId(hwnd, C.byref(pid))
    handle = kernel32.OpenProcess(0x1000, False, pid.value)
    if not handle:
        return "", thread
    try:
        size = W.DWORD(32768)
        buffer = C.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, C.byref(size)):
            return "", thread
        return os.path.basename(buffer.value), thread
    finally:
        kernel32.CloseHandle(handle)


class WindowsInput:
    def __init__(self, process: str):
        self.process = process.casefold()
        self.held: dict[str, INPUT] = {}
        self.lock = threading.RLock()

    def has_focus(self):
        return foreground_process()[0].casefold() == self.process

    def _send(self, packet):
        if user32.SendInput(1, C.byref(packet), C.sizeof(INPUT)) != 1:
            raise RuntimeError("Windows hat die Eingabe abgelehnt. Rechte von Spiel und Bot prüfen.")

    def _packet(self, key, up=False):
        if key in MOUSE_FLAGS:
            flags = MOUSE_FLAGS[key][int(up)]
            return INPUT(type=0, mi=MOUSEINPUT(dwFlags=flags))
        _, thread = foreground_process()
        layout = user32.GetKeyboardLayout(thread)
        scan = user32.MapVirtualKeyExW(VK[key], 4, layout)
        if not scan:
            raise RuntimeError(f"Kein Windows-Scancode für {key} gefunden.")
        flags = 0x0008 | (0x0001 if scan & 0xFF00 else 0) | (0x0002 if up else 0)
        return INPUT(type=1, ki=KEYBDINPUT(wScan=scan & 0xFF, dwFlags=flags))

    def set_held(self, keys, stop_event):
        with self.lock:
            self.release_all()
            if stop_event.is_set():
                return
            if not self.has_focus():
                raise RuntimeError("Spielfokus verloren. Keine Eingabe gesendet.")
            for key in keys:
                if stop_event.is_set():
                    break
                if not self.has_focus():
                    raise RuntimeError("Spielfokus verloren. Keine Eingabe gesendet.")
                # Cache the release packet now; a later keyboard-layout change must not alter it.
                down = self._packet(key)
                up = self._packet(key, up=True)
                self._send(down)
                self.held[key] = up

    def move_mouse(self, dx, dy, stop_event):
        with self.lock:
            if stop_event.is_set():
                return
            if not self.has_focus():
                raise RuntimeError("Spielfokus verloren. Keine Mausbewegung gesendet.")
            self._send(INPUT(type=0, mi=MOUSEINPUT(dx=dx, dy=dy, dwFlags=0x0001)))

    def release_all(self):
        with self.lock:
            errors = []
            for key, packet in reversed(list(self.held.items())):
                try:
                    self._send(packet)
                    del self.held[key]
                except Exception as exc:
                    errors.append(exc)
            if errors:
                raise errors[0]


class PreviewInput:
    def __init__(self, emit):
        self.emit = emit

    def has_focus(self):
        return True

    def set_held(self, keys, stop_event):
        if not stop_event.is_set():
            self.emit("log", "Vorschau · Tasten halten: " + "+".join(keys))

    def move_mouse(self, dx, dy, stop_event):
        pass

    def release_all(self):
        pass


class KeyboardService:
    COMMANDS = {0x75: "combat_marker", 0x76: "gather_marker", 0x77: "start",
                0x78: "stop", 0x79: "record"}

    def __init__(self, on_command, on_key, on_error):
        self.on_command = on_command
        self.on_key = on_key
        self.on_error = on_error
        self.ready = threading.Event()
        self.registered = set()
        self.thread_id = 0
        self.thread = threading.Thread(target=self._run, name="global-hotkeys", daemon=True)
        self.thread.start()
        self.ready.wait(2)

    def _run(self):
        self.thread_id = kernel32.GetCurrentThreadId()
        self.hook_proc = HOOKPROC(self._hook)
        hook = user32.SetWindowsHookExW(13, self.hook_proc, kernel32.GetModuleHandleW(None), 0)
        try:
            if not hook:
                self.on_error("Tastaturaufnahme nicht verfügbar: Windows-Hook konnte nicht starten.")
            self.hook_available = bool(hook)
            for vk, command in self.COMMANDS.items():
                if user32.RegisterHotKey(None, vk, 0x4000, vk):
                    self.registered.add(command)
                else:
                    self.on_error(f"F{vk - 0x6F} ist bereits durch ein anderes Programm belegt.")
            self.ready.set()
            message = W.MSG()
            while user32.GetMessageW(C.byref(message), None, 0, 0) > 0:
                if message.message == 0x0312:
                    try:
                        self.on_command(self.COMMANDS[message.wParam])
                    except Exception as exc:
                        self.on_error(str(exc))
        finally:
            for vk, command in self.COMMANDS.items():
                if command in self.registered:
                    user32.UnregisterHotKey(None, vk)
            if hook:
                user32.UnhookWindowsHookEx(hook)
            self.ready.set()

    def _hook(self, code, wparam, lparam):
        if code >= 0:
            data = C.cast(lparam, C.POINTER(KBDLLHOOKSTRUCT)).contents
            if not data.flags & 0x10 and wparam in (0x100, 0x101, 0x104, 0x105):
                key = KEY_FROM_VK.get(data.vkCode)
                if key:
                    try:
                        self.on_key(key, wparam in (0x100, 0x104))
                    except Exception as exc:
                        self.on_error(str(exc))
        return user32.CallNextHookEx(None, code, wparam, lparam)

    def close(self):
        if self.thread_id:
            user32.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)
        self.thread.join(timeout=1)
