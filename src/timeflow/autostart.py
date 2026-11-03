"""Windows "start with Windows" integration (current-user Run key)."""

from __future__ import annotations

import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "TimeTrace"
LEGACY_VALUE_NAME = "TimeFlow"


def startup_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable)}" --minimized'
    python = Path(sys.executable)
    pythonw = python.with_name("pythonw.exe")
    launcher = pythonw if pythonw.exists() else python
    project_main = Path(__file__).resolve().parents[2] / "main.py"
    return f'"{launcher}" "{project_main}" --minimized'


def is_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
            return bool(value)
    except OSError:
        return False


def set_enabled(enabled: bool) -> None:
    if sys.platform != "win32":
        return
    import winreg

    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        RUN_KEY,
        0,
        winreg.KEY_READ | winreg.KEY_WRITE,
    ) as key:
        if enabled:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, startup_command())
            _delete_value(key, LEGACY_VALUE_NAME)
        else:
            _delete_value(key, VALUE_NAME)
            _delete_value(key, LEGACY_VALUE_NAME)


def _delete_value(key: object, name: str) -> None:
    import winreg

    try:
        winreg.DeleteValue(key, name)  # type: ignore[arg-type]
    except FileNotFoundError:
        pass
