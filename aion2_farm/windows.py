from __future__ import annotations

import ctypes as C
from ctypes import wintypes as W
import os
import threading
import subprocess
import sys
from pathlib import Path
from dataclasses import dataclass
from .models import INPUT_METHODS

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
kernel32.GetCurrentProcess.restype = W.HANDLE
user32.GetWindowTextLengthW.argtypes = [W.HWND]
user32.GetWindowTextW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
user32.GetClientRect.argtypes = [W.HWND, C.POINTER(W.RECT)]
user32.ClientToScreen.argtypes = [W.HWND, C.POINTER(W.POINT)]
user32.GetCursorPos.argtypes = [C.POINTER(W.POINT)]
user32.ScreenToClient.argtypes = [W.HWND, C.POINTER(W.POINT)]
user32.PostMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
user32.PostMessageW.restype = W.BOOL
user32.WindowFromPoint.argtypes = [W.POINT]
user32.WindowFromPoint.restype = W.HWND
user32.IsChild.argtypes = [W.HWND, W.HWND]
user32.IsChild.restype = W.BOOL
user32.SendMessageTimeoutW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM, W.UINT, W.UINT, C.POINTER(ULONG_PTR)]
user32.SendMessageTimeoutW.restype = LRESULT
user32.keybd_event.argtypes = [W.BYTE, W.BYTE, W.DWORD, ULONG_PTR]
user32.mouse_event.argtypes = [W.DWORD, W.DWORD, W.DWORD, W.DWORD, ULONG_PTR]
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


def enable_dpi_awareness():
    # Keep window bounds, mouse coordinates and captured HUD pixels in the same physical space.
    try:
        method = user32.SetProcessDpiAwarenessContext
        method.argtypes = [W.HANDLE]
        method.restype = W.BOOL
        if method(C.c_void_p(-4)):
            return
    except AttributeError:
        pass
    try:
        user32.SetProcessDPIAware()
    except AttributeError:
        pass


class PROCESSENTRY32(C.Structure):
    _fields_ = [("dwSize", W.DWORD), ("cntUsage", W.DWORD), ("th32ProcessID", W.DWORD),
                ("th32DefaultHeapID", ULONG_PTR), ("th32ModuleID", W.DWORD), ("cntThreads", W.DWORD),
                ("th32ParentProcessID", W.DWORD), ("pcPriClassBase", W.LONG),
                ("dwFlags", W.DWORD), ("szExeFile", W.WCHAR * 260)]


kernel32.CreateToolhelp32Snapshot.argtypes = [W.DWORD, W.DWORD]
kernel32.CreateToolhelp32Snapshot.restype = W.HANDLE
kernel32.Process32FirstW.argtypes = [W.HANDLE, C.POINTER(PROCESSENTRY32)]
kernel32.Process32FirstW.restype = W.BOOL
kernel32.Process32NextW.argtypes = [W.HANDLE, C.POINTER(PROCESSENTRY32)]
kernel32.Process32NextW.restype = W.BOOL
ENUMWINDOWSPROC = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
user32.EnumWindows.argtypes = [ENUMWINDOWSPROC, W.LPARAM]
user32.IsWindowVisible.argtypes = [W.HWND]
user32.IsWindowVisible.restype = W.BOOL
advapi32 = C.WinDLL("advapi32", use_last_error=True)
advapi32.OpenProcessToken.argtypes = [W.HANDLE, W.DWORD, C.POINTER(W.HANDLE)]
advapi32.OpenProcessToken.restype = W.BOOL
advapi32.GetTokenInformation.argtypes = [W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.POINTER(W.DWORD)]
advapi32.GetTokenInformation.restype = W.BOOL
advapi32.GetSidSubAuthorityCount.argtypes = [C.c_void_p]
advapi32.GetSidSubAuthorityCount.restype = C.POINTER(W.BYTE)
advapi32.GetSidSubAuthority.argtypes = [C.c_void_p, W.DWORD]
advapi32.GetSidSubAuthority.restype = C.POINTER(W.DWORD)


def process_list():
    result = []
    snapshot = kernel32.CreateToolhelp32Snapshot(2, 0)
    if not snapshot or snapshot == C.c_void_p(-1).value:
        return result
    try:
        entry = PROCESSENTRY32(dwSize=C.sizeof(PROCESSENTRY32))
        ok = kernel32.Process32FirstW(snapshot, C.byref(entry))
        while ok:
            result.append({"pid": entry.th32ProcessID, "name": entry.szExeFile})
            ok = kernel32.Process32NextW(snapshot, C.byref(entry))
        return result
    finally:
        kernel32.CloseHandle(snapshot)


def process_integrity(pid=None):
    process = kernel32.GetCurrentProcess() if pid is None else kernel32.OpenProcess(0x1000, False, pid)
    if not process:
        return None
    token = W.HANDLE()
    try:
        if not advapi32.OpenProcessToken(process, 0x0008, C.byref(token)):
            return None
        length = W.DWORD()
        advapi32.GetTokenInformation(token, 25, None, 0, C.byref(length))
        if not length.value:
            return None
        buffer = C.create_string_buffer(length.value)
        if not advapi32.GetTokenInformation(token, 25, buffer, length.value, C.byref(length)):
            return None
        # TOKEN_MANDATORY_LABEL starts with SID_AND_ATTRIBUTES; its first member is PSID.
        sid = C.cast(buffer, C.POINTER(C.c_void_p)).contents.value
        count = advapi32.GetSidSubAuthorityCount(sid)[0]
        return advapi32.GetSidSubAuthority(sid, count - 1)[0] if count else None
    finally:
        if token:
            kernel32.CloseHandle(token)
        if pid is not None:
            kernel32.CloseHandle(process)


def integrity_label(level):
    if level is None:
        return "nicht lesbar"
    if level >= 0x4000:
        return "System"
    if level >= 0x3000:
        return "Administrator"
    if level >= 0x2000:
        return "Normal"
    return "Eingeschränkt"


def inspect_game(process):
    candidates = [row for row in process_list() if row["name"].casefold() == process.casefold()]
    by_pid = {row["pid"]: row for row in candidates}
    def collect(hwnd, unused):
        pid = W.DWORD()
        user32.GetWindowThreadProcessId(hwnd, C.byref(pid))
        if pid.value in by_pid and user32.IsWindowVisible(hwnd):
            by_pid[pid.value]["hwnd"] = int(hwnd)
        return True
    callback = ENUMWINDOWSPROC(collect)
    user32.EnumWindows(callback, 0)
    windowed = [row for row in candidates if row.get("hwnd")]
    targets = windowed or candidates
    own = process_integrity()
    for row in targets:
        row["integrity"] = process_integrity(row["pid"])
    report = {"bot_integrity": own, "targets": targets, "status": "ready", "message": "Rechteprüfung erfolgreich."}
    if not targets:
        report.update(status="missing", message=f"Kein laufender Prozess {process} gefunden.")
    elif own is None or any(row["integrity"] is None for row in targets):
        report.update(status="unknown", message="Die Rechteebenen konnten nicht vollständig gelesen werden.")
    elif any(row["integrity"] > own for row in targets):
        report.update(status="rights", message="Das Spiel läuft mit höheren Rechten als die App. "
                      "Unter Diagnose mit Administratorrechten neu starten und die Windows-Abfrage selbst bestätigen.")
    return report


def check_input_permissions(process):
    report = inspect_game(process)
    if report["status"] == "rights":
        raise PermissionError(report["message"])
    if report["status"] == "missing":
        raise RuntimeError(report["message"])
    return report


def relaunch_elevated(profile_path, *, control=False):
    frozen = getattr(sys, "frozen", False)
    arguments = ["--profile", str(profile_path)]
    if control:
        arguments.append("--mcp-control")
    if not frozen:
        arguments = ["-m", "aion2_farm", *arguments]
    working = Path(sys.executable).parent if frozen else Path(__file__).resolve().parent.parent
    shell = C.WinDLL("shell32", use_last_error=True)
    shell.ShellExecuteW.argtypes = [W.HWND, W.LPCWSTR, W.LPCWSTR, W.LPCWSTR, W.LPCWSTR, C.c_int]
    shell.ShellExecuteW.restype = C.c_void_p
    C.set_last_error(0)
    result = shell.ShellExecuteW(None, "runas", sys.executable, subprocess.list2cmdline(arguments), str(working), 1)
    if not result or result <= 32:
        raise OSError(C.get_last_error() or result or 1, "Administrator-Neustart wurde abgebrochen oder abgelehnt.")


def game_client_bounds(process):
    hwnd = user32.GetForegroundWindow()
    if foreground_process()[0].casefold() != process.casefold():
        raise RuntimeError("Für die HUD-Erkennung muss das Spiel im Vordergrund sein.")
    rect, origin = W.RECT(), W.POINT(0, 0)
    if not user32.GetClientRect(hwnd, C.byref(rect)) or not user32.ClientToScreen(hwnd, C.byref(origin)):
        raise RuntimeError("Größe des Spielfensters nicht lesbar.")
    width, height = rect.right - rect.left, rect.bottom - rect.top
    if width < 100 or height < 100:
        raise RuntimeError("Spielfenster ist minimiert oder zu klein.")
    return int(hwnd), (origin.x, origin.y, origin.x + width, origin.y + height)


def foreground_process() -> tuple[str, int]:
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return "", 0
    pid = W.DWORD()
    thread = user32.GetWindowThreadProcessId(hwnd, C.byref(pid))
    handle = kernel32.OpenProcess(0x1000, False, pid.value)
    if not handle:
        return next((row["name"] for row in process_list() if row["pid"] == pid.value), ""), thread
    try:
        size = W.DWORD(32768)
        buffer = C.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, C.byref(size)):
            return next((row["name"] for row in process_list() if row["pid"] == pid.value), ""), thread
        return os.path.basename(buffer.value), thread
    finally:
        kernel32.CloseHandle(handle)


@dataclass
class WindowMessage:
    hwnd: int
    message: int
    wparam: int
    lparam: int


class WindowsInput:
    def __init__(self, process: str, method="scancode"):
        if method not in INPUT_METHODS:
            raise ValueError("Unbekannte Eingabemethode.")
        self.method = method
        self.process = process.casefold()
        self.held: dict[str, INPUT] = {}
        self.lock = threading.RLock()
        self.own_integrity = process_integrity()
        self.checked_pid = None

    def _check_rights(self):
        pid = W.DWORD()
        user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), C.byref(pid))
        if self.checked_pid != pid.value:
            target = process_integrity(pid.value)
            if target is not None and self.own_integrity is not None and target > self.own_integrity:
                raise PermissionError("Spiel: Administratorrechte; App: normale Rechte. Unter Diagnose als Administrator neu starten.")
            self.checked_pid = pid.value

    def has_focus(self):
        return foreground_process()[0].casefold() == self.process

    def _send(self, packet):
        C.set_last_error(0)
        if isinstance(packet, WindowMessage):
            if self.method == "sendmessage":
                result = ULONG_PTR()
                if not user32.SendMessageTimeoutW(packet.hwnd, packet.message, packet.wparam, packet.lparam,
                                                  2, 200, C.byref(result)):
                    raise RuntimeError(f"Fensternachricht nicht bestätigt (Windows-Fehler {C.get_last_error()}).")
                return
            if not user32.PostMessageW(packet.hwnd, packet.message, packet.wparam, packet.lparam):
                raise RuntimeError(f"Fensternachricht abgelehnt (Windows-Fehler {C.get_last_error()}).")
            return
        if self.method == "legacy":
            if packet.type == 0:
                data = packet.mi
                user32.mouse_event(data.dwFlags, data.dx, data.dy, data.mouseData, data.dwExtraInfo)
            else:
                data = packet.ki
                user32.keybd_event(data.wVk, data.wScan, data.dwFlags, data.dwExtraInfo)
            return
        if user32.SendInput(1, C.byref(packet), C.sizeof(INPUT)) != 1:
            error = C.get_last_error()
            raise RuntimeError(f"Windows hat die Eingabe abgelehnt (Fehler {error}). Rechte unter Diagnose prüfen.")

    def _packet(self, key, up=False):
        if self.method in ("messages", "sendmessage"):
            hwnd = user32.GetForegroundWindow()
            if key in MOUSE_FLAGS:
                point = W.POINT()
                if not user32.GetCursorPos(C.byref(point)):
                    raise RuntimeError("Mausposition nicht lesbar.")
                child = user32.WindowFromPoint(point)
                if child and user32.IsChild(hwnd, child):
                    hwnd = child
                if not user32.ScreenToClient(hwnd, C.byref(point)):
                    raise RuntimeError("Mausposition nicht lesbar.")
                messages = {"leftmouse": (0x201, 0x202, 1), "rightmouse": (0x204, 0x205, 2),
                            "middlemouse": (0x207, 0x208, 16)}
                down, release, flag = messages[key]
                return WindowMessage(int(hwnd), release if up else down, 0 if up else flag,
                                     (point.x & 0xFFFF) | ((point.y & 0xFFFF) << 16))
            _, thread = foreground_process()
            scan = user32.MapVirtualKeyExW(VK[key], 4, user32.GetKeyboardLayout(thread))
            lparam = 1 | ((scan & 0xFF) << 16) | (0x01000000 if scan & 0xFF00 else 0)
            if up:
                lparam |= 0xC0000000
            return WindowMessage(int(hwnd), 0x101 if up else 0x100, VK[key], lparam)
        if key in MOUSE_FLAGS:
            flags = MOUSE_FLAGS[key][int(up)]
            return INPUT(type=0, mi=MOUSEINPUT(dwFlags=flags))
        if self.method == "virtual":
            return INPUT(type=1, ki=KEYBDINPUT(wVk=VK[key], dwFlags=0x0002 if up else 0))
        _, thread = foreground_process()
        layout = user32.GetKeyboardLayout(thread)
        scan = user32.MapVirtualKeyExW(VK[key], 4, layout)
        if not scan:
            raise RuntimeError(f"Kein Windows-Scancode für {key} gefunden.")
        if self.method == "legacy":
            return INPUT(type=1, ki=KEYBDINPUT(wVk=VK[key], wScan=scan & 0xFF,
                                             dwFlags=(1 if scan & 0xFF00 else 0) | (2 if up else 0)))
        flags = 0x0008 | (0x0001 if scan & 0xFF00 else 0) | (0x0002 if up else 0)
        return INPUT(type=1, ki=KEYBDINPUT(wScan=scan & 0xFF, dwFlags=flags))

    def set_held(self, keys, stop_event):
        with self.lock:
            self.release_all()
            if stop_event.is_set():
                return
            if not self.has_focus():
                raise RuntimeError("Spielfokus verloren. Keine Eingabe gesendet.")
            self._check_rights()
            if any(key in MOUSE_FLAGS for key in keys):
                _, bounds = game_client_bounds(self.process)
                point = W.POINT()
                if not user32.GetCursorPos(C.byref(point)) or not (
                        bounds[0] <= point.x < bounds[2] and bounds[1] <= point.y < bounds[3]):
                    raise RuntimeError("Mauszeiger liegt außerhalb des Spielfensters. Vor dem Start auf die Spielwelt richten.")
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
            self._check_rights()
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
