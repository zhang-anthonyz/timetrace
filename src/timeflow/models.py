"""Immutable data objects shared by the tracker, database and UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class AppUsage:
    key: str
    name: str
    exe_path: str
    seconds: int


@dataclass(frozen=True)
class RecentSession:
    key: str
    name: str
    exe_path: str
    started_at: str
    ended_at: str
    seconds: int
    title: str = ""
    is_current: bool = False


@dataclass(frozen=True)
class Snapshot:
    """A consistent, immutable view of the tracker at one instant."""

    today: str
    state: str
    paused: bool
    current_key: str = ""
    current_name: str = ""
    current_title: str = ""
    current_exe: str = ""
    current_started: str = ""
    current_seconds: int = 0
    total_seconds: int = 0
    apps: tuple[AppUsage, ...] = field(default_factory=tuple)
    hours: tuple[int, ...] = field(default_factory=lambda: (0,) * 24)
    recent: tuple[RecentSession, ...] = field(default_factory=tuple)
    idle_seconds: int = 0
    generated_at: datetime | None = None

    @property
    def recorded_apps(self) -> int:
        return len(self.apps)

    @property
    def active(self) -> bool:
        return self.state == "active" and not self.paused
