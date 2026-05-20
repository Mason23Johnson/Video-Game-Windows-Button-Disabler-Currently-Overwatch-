"""
OW WinKey Guard
Sits in the system tray and disables the Windows key while Overwatch is running.
"""

import ctypes
import os
import sys
import threading
import time
import winreg
from ctypes import wintypes

import psutil
import pystray
from PIL import Image, ImageDraw

# Low-level keyboard hook 

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WH_KEYBOARD_LL = 13
VK_LWIN = 0x5B
VK_RWIN = 0x5C

_blocking = False
_hook_id = None


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)


def _hook_proc(nCode, wParam, lParam):
    if nCode >= 0 and _blocking:
        kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        if kb.vkCode in (VK_LWIN, VK_RWIN):
            return 1  # swallow the key
    return user32.CallNextHookEx(_hook_id, nCode, wParam, lParam)


# Keep a module-level reference so the callback isn't garbage collected
_hook_func = HOOKPROC(_hook_proc)


def _run_hook():
    """Install the hook and pump messages so it stays active."""
    global _hook_id
    _hook_id = user32.SetWindowsHookExW(
        WH_KEYBOARD_LL,
        _hook_func,
        kernel32.GetModuleHandleW(None),
        0,
    )
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))


# Overwatch process detection

OW_PROCESSES = {"Overwatch.exe", "Overwatch_retail_rendering_worker.exe"}
CHECK_INTERVAL = 2  # seconds


def _is_overwatch_running():
    for proc in psutil.process_iter(["name"]):
        try:
            if proc.info["name"] in OW_PROCESSES:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False


# Tray icon image

def _make_icon(dot_color):
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, 60, 60], fill=dot_color)
    return img


ICON_IDLE = _make_icon((80, 200, 80, 255))    # green  — Overwatch not running
ICON_ACTIVE = _make_icon((220, 60, 60, 255))  # red    — Win key is blocked


# Startup registry helpers

APP_NAME = "OWWinKeyGuard"
STARTUP_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _exe_path():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    return f'pythonw "{os.path.abspath(__file__)}"'


def _startup_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_KEY) as k:
            winreg.QueryValueEx(k, APP_NAME)
            return True
    except FileNotFoundError:
        return False


def _toggle_startup(icon, item):
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, STARTUP_KEY, 0, winreg.KEY_SET_VALUE
    ) as k:
        if _startup_enabled():
            winreg.DeleteValue(k, APP_NAME)
        else:
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, _exe_path())
    icon.update_menu()


# Monitor loop 

_tray_icon = None


def _monitor():
    global _blocking, _tray_icon
    was_running = False
    while True:
        running = _is_overwatch_running()
        if running != was_running:
            _blocking = running
            was_running = running
            if _tray_icon:
                _tray_icon.icon = ICON_ACTIVE if running else ICON_IDLE
                status = "ACTIVE – Win key blocked" if running else "Idle – Overwatch not running"
                _tray_icon.title = f"OW WinKey Guard  ·  {status}"
                _tray_icon.update_menu()
        time.sleep(CHECK_INTERVAL)


# Tray menu 

def _status_label(item):
    return "● Blocking Win key" if _blocking else "● Idle"


def _quit(icon, item):
    global _blocking
    _blocking = False
    icon.stop()


def main():
    global _tray_icon

    threading.Thread(target=_run_hook, daemon=True).start()
    threading.Thread(target=_monitor, daemon=True).start()

    menu = pystray.Menu(
        pystray.MenuItem(_status_label, None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            "Run on Windows startup",
            _toggle_startup,
            checked=lambda item: _startup_enabled(),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", _quit),
    )

    _tray_icon = pystray.Icon(
        "OWWinKeyGuard",
        ICON_IDLE,
        "OW WinKey Guard  ·  Idle",
        menu=menu,
    )
    _tray_icon.run()


if __name__ == "__main__":
    main()
