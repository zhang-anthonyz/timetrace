"""Filesystem locations used by 时迹 / TimeTrace.

All data stays under the current user's local application data folder.  The
``TIMETRACE_DATA_DIR`` environment variable is honoured for development and for
portable test runs.  Existing TimeFlow data is copied on first launch so the
rename does not lose history.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

APP_NAME = "TimeTrace"
APP_DIR_NAME = "TimeTrace"
LEGACY_DIR_NAME = "TimeFlow"
DB_FILENAME = "timetrace.db"
LOG_FILENAME = "timetrace.log"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _base_dir() -> Path:
    override = os.environ.get("TIMETRACE_DATA_DIR") or os.environ.get("TIMEFLOW_DATA_DIR")
    if override:
        return Path(override).expanduser()
    base = os.environ.get("LOCALAPPDATA")
    return Path(base) if base else Path.home() / "AppData" / "Local"


def data_dir() -> Path:
    base = _base_dir()
    root = base / APP_DIR_NAME
    legacy = base / LEGACY_DIR_NAME
    _migrate_legacy(root, legacy)
    root.mkdir(parents=True, exist_ok=True)
    return root


def db_path() -> Path:
    return data_dir() / DB_FILENAME


def settings_path() -> Path:
    return data_dir() / "settings.json"


def log_dir() -> Path:
    path = data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_path() -> Path:
    return log_dir() / LOG_FILENAME


def resource_path(relative: str) -> Path:
    """Resolve a bundled resource both in development and in PyInstaller."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base / relative


def _migrate_legacy(root: Path, legacy: Path) -> None:
    """Copy old TimeFlow data without touching the original directory."""
    if not legacy.is_dir():
        return
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError:
        return

    mappings = (
        ("timeflow.db", DB_FILENAME),
        ("timeflow.db-wal", DB_FILENAME + "-wal"),
        ("timeflow.db-shm", DB_FILENAME + "-shm"),
        ("settings.json", "settings.json"),
        ("ui.ini", "ui.ini"),
    )
    for source_name, target_name in mappings:
        source = legacy / source_name
        target = root / target_name
        if not source.is_file() or target.exists():
            continue
        try:
            shutil.copy2(source, target)
        except OSError:
            pass
