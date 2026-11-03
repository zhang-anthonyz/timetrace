"""Persistent user settings."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, replace
from pathlib import Path


@dataclass
class Settings:
    idle_seconds: int = 180
    start_with_windows: bool = False
    start_minimized: bool = False
    tray_hint_shown: bool = False

    def normalized(self) -> "Settings":
        idle = int(self.idle_seconds)
        idle = max(15, min(3600, idle))
        return replace(self, idle_seconds=idle)

    def copy(self) -> "Settings":
        return replace(self)


def load_settings(path: Path) -> Settings:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return Settings()
    except (OSError, ValueError, TypeError):
        try:
            path.replace(path.with_suffix(".json.bad"))
        except OSError:
            pass
        return Settings()

    if not isinstance(raw, dict):
        return Settings()
    defaults = Settings()
    settings = Settings(
        idle_seconds=_as_int(raw.get("idle_seconds"), defaults.idle_seconds),
        start_with_windows=bool(raw.get("start_with_windows", defaults.start_with_windows)),
        start_minimized=bool(raw.get("start_minimized", defaults.start_minimized)),
        tray_hint_shown=bool(raw.get("tray_hint_shown", defaults.tray_hint_shown)),
    )
    return settings.normalized()


def save_settings(path: Path, settings: Settings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    payload = json.dumps(asdict(settings.normalized()), ensure_ascii=False, indent=2)
    tmp.write_text(payload + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _as_int(value: object, fallback: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fallback
