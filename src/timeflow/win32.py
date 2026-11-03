"""Small, dependency-light Win32 helpers for foreground-window tracking.

The module is intentionally defensive: Windows APIs can fail for protected or
elevated processes, and tracking must continue with a best-effort name rather
than crash.
"""

from __future__ import annotations

import ctypes
import os
import struct
import sys
from ctypes import wintypes
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

if IS_WINDOWS:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    version = ctypes.WinDLL("version", use_last_error=True)

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.UINT),
            ("dwTime", wintypes.DWORD),
        ]

    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    ]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetLastInputInfo.argtypes = [ctypes.POINTER(LASTINPUTINFO)]
    user32.GetLastInputInfo.restype = wintypes.BOOL
    user32.EnumChildWindows.argtypes = [wintypes.HWND, WNDENUMPROC, wintypes.LPARAM]
    user32.EnumChildWindows.restype = wintypes.BOOL
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.restype = ctypes.c_int
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL

    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.GetTickCount64.argtypes = []
    kernel32.GetTickCount64.restype = ctypes.c_ulonglong

    version.GetFileVersionInfoSizeW.argtypes = [
        wintypes.LPCWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    version.GetFileVersionInfoSizeW.restype = wintypes.DWORD
    version.GetFileVersionInfoW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
    ]
    version.GetFileVersionInfoW.restype = wintypes.BOOL
    version.VerQueryValueW.argtypes = [
        ctypes.c_void_p,
        wintypes.LPCWSTR,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(wintypes.UINT),
    ]
    version.VerQueryValueW.restype = wintypes.BOOL


@dataclass(frozen=True)
class ForegroundApp:
    hwnd: int
    pid: int
    process_name: str
    exe_path: str
    title: str

    @property
    def app_key(self) -> str:
        return (self.process_name or f"pid-{self.pid}").lower()


def enable_dark_title_bar(hwnd: int) -> None:
    """Ask DWM to paint the native caption dark (Windows 10/11)."""
    if not IS_WINDOWS or not hwnd:
        return
    try:
        dwmapi = ctypes.WinDLL("dwmapi")
        enabled = ctypes.c_int(1)
        # 20 is the modern attribute; 19 is the fallback on older Win10 builds.
        for attribute in (20, 19):
            result = dwmapi.DwmSetWindowAttribute(
                wintypes.HWND(hwnd),
                wintypes.DWORD(attribute),
                ctypes.byref(enabled),
                ctypes.sizeof(enabled),
            )
            if result == 0:
                return
    except Exception:
        return


def get_foreground_app() -> ForegroundApp | None:
    if not IS_WINDOWS:
        return None
    try:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return None

        exe_path = process_path(pid.value)
        process_name = Path(exe_path).name if exe_path else _fallback_process_name(pid.value)

        # UWP/Store apps are hosted by ApplicationFrameHost; the real app is a
        # child CoreWindow owned by another process.
        if process_name.lower() == "applicationframehost.exe":
            child_pid = _find_hosted_child_pid(hwnd, pid.value)
            if child_pid:
                child_path = process_path(child_pid)
                if child_path:
                    exe_path = child_path
                    process_name = Path(child_path).name
                    pid = wintypes.DWORD(child_pid)
                else:
                    fallback = _fallback_process_name(child_pid)
                    if fallback:
                        process_name = fallback
                        pid = wintypes.DWORD(child_pid)

        if not process_name:
            process_name = f"pid-{pid.value}"

        return ForegroundApp(
            hwnd=int(hwnd),
            pid=int(pid.value),
            process_name=process_name,
            exe_path=exe_path or "",
            title=window_title(hwnd),
        )
    except Exception:
        return None


def get_idle_seconds() -> int:
    if not IS_WINDOWS:
        return 0
    try:
        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        if not user32.GetLastInputInfo(ctypes.byref(info)):
            return 0
        now = int(kernel32.GetTickCount64())
        last = int(info.dwTime)
        elapsed_ms = (now - last) & 0xFFFFFFFF
        seconds = elapsed_ms // 1000
        if seconds < 0 or seconds > 60 * 60 * 24 * 30:
            return 0
        return seconds
    except Exception:
        return 0


def window_title(hwnd: int) -> str:
    if not IS_WINDOWS:
        return ""
    try:
        length = int(user32.GetWindowTextLengthW(hwnd))
        if length <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        return " ".join(buf.value.split())
    except Exception:
        return ""


def process_path(pid: int) -> str:
    if not IS_WINDOWS:
        return ""
    handle = None
    try:
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return ""
        size = wintypes.DWORD(32768)
        buf = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return buf.value
    except Exception:
        pass
    finally:
        if handle:
            kernel32.CloseHandle(handle)

    try:
        import psutil

        return psutil.Process(pid).exe() or ""
    except Exception:
        return ""


@lru_cache(maxsize=512)
def file_description(path: str) -> str:
    """Read FileDescription from an executable's version resource."""
    if not IS_WINDOWS or not path:
        return ""
    try:
        if not os.path.isfile(path):
            return ""
        dummy = wintypes.DWORD()
        size = int(version.GetFileVersionInfoSizeW(path, ctypes.byref(dummy)))
        if size <= 0:
            return ""
        data = ctypes.create_string_buffer(size)
        if not version.GetFileVersionInfoW(path, 0, size, ctypes.cast(data, ctypes.c_void_p)):
            return ""

        translations: list[tuple[int, int]] = []
        ptr = ctypes.c_void_p()
        length = wintypes.UINT()
        if version.VerQueryValueW(
            ctypes.cast(data, ctypes.c_void_p),
            r"\VarFileInfo\Translation",
            ctypes.byref(ptr),
            ctypes.byref(length),
        ):
            if ptr.value and length.value >= 4:
                raw = ctypes.string_at(ptr.value, length.value)
                for i in range(0, len(raw) - 3, 4):
                    translations.append(struct.unpack("<HH", raw[i : i + 4]))

        if not translations:
            translations = [(0x0409, 0x04B0), (0x0409, 0x04E4), (0x0804, 0x04B0)]

        for lang, codepage in translations:
            block = f"\\StringFileInfo\\{lang:04x}{codepage:04x}\\FileDescription"
            value_ptr = ctypes.c_void_p()
            value_len = wintypes.UINT()
            if version.VerQueryValueW(
                ctypes.cast(data, ctypes.c_void_p),
                block,
                ctypes.byref(value_ptr),
                ctypes.byref(value_len),
            ):
                if value_ptr.value and value_len.value:
                    text = ctypes.wstring_at(value_ptr.value, value_len.value)
                    text = text.split("\x00", 1)[0].strip()
                    if text:
                        return text
    except Exception:
        return ""
    return ""


def _fallback_process_name(pid: int) -> str:
    try:
        import psutil

        return psutil.Process(pid).name()
    except Exception:
        return ""


def _find_hosted_child_pid(parent_hwnd: int, parent_pid: int) -> int:
    """Find a visible child window owned by a different process (UWP apps)."""
    candidates: list[tuple[int, str]] = []

    @WNDENUMPROC
    def callback(hwnd: int, _lparam: int) -> bool:
        try:
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if not pid.value or pid.value == parent_pid:
                return True
            class_buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_buf, 256)
            if not user32.IsWindowVisible(hwnd):
                return True
            candidates.append((int(pid.value), class_buf.value))
            return True
        except Exception:
            return True

    try:
        user32.EnumChildWindows(parent_hwnd, callback, 0)
    except Exception:
        return 0

    for pid, class_name in candidates:
        if class_name == "Windows.UI.Core.CoreWindow":
            return pid
    return candidates[0][0] if candidates else 0
