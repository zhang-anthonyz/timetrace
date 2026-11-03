"""Pure usage-accounting engine.

The engine is deliberately independent of Qt and of the Win32 polling loop so
that session splitting, idle handling and aggregation can be unit-tested with a
fake foreground provider.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Iterable

from .db import Database
from .display import friendly_name
from .models import AppUsage, RecentSession, Snapshot
from .win32 import ForegroundApp

LOG = logging.getLogger(__name__)
FLUSH_INTERVAL = timedelta(seconds=5)
DEFAULT_EXCLUDED = {"lockapp.exe", "logonui.exe", "screensaver.scr"}


@dataclass
class CurrentSession:
    session_id: int | None
    key: str
    name: str
    exe_path: str
    title: str
    started_at: datetime
    date: str
    hour: int
    seconds: int = 0


class UsageEngine:
    def __init__(
        self,
        db: Database,
        self_pid: int,
        idle_seconds: int = 180,
        excluded: Iterable[str] | None = None,
        now: datetime | None = None,
    ) -> None:
        self.db = db
        self.self_pid = int(self_pid)
        self.idle_seconds = max(1, int(idle_seconds))
        self.excluded = {name.lower() for name in (excluded or DEFAULT_EXCLUDED)}
        self.today = (now or datetime.now()).date().isoformat()
        self.totals: dict[str, AppUsage] = {}
        self.hours: list[int] = [0] * 24
        self.recent: deque[RecentSession] = deque(maxlen=20)
        self.current: CurrentSession | None = None
        self.state = "unavailable"
        self.paused = False
        self.last_idle = 0
        self._last_flush = now or datetime.now()
        self._load_today()

    # ------------------------------------------------------------------ API

    def tick(
        self,
        now: datetime,
        foreground: ForegroundApp | None,
        idle_seconds: int,
        paused: bool = False,
    ) -> None:
        self.last_idle = max(0, int(idle_seconds))
        self.paused = bool(paused)
        self._roll_day_if_needed(now)

        if paused:
            self._transition(None, now, "paused")
            self.state = "paused"
            return

        if self.last_idle >= self.idle_seconds:
            self._transition(None, now, "idle")
            self.state = "idle"
            return

        if foreground is None:
            self._transition(None, now, "unavailable")
            self.state = "unavailable"
            return

        if self.self_pid and foreground.pid == self.self_pid:
            self._transition(None, now, "self")
            self.state = "self"
            return

        if foreground.app_key in self.excluded:
            self._transition(None, now, "excluded")
            self.state = "excluded"
            return

        self._transition(foreground, now, "active")
        self.state = "active"
        if self.current is None:
            return

        self.current.seconds += 1
        if foreground.title:
            self.current.title = foreground.title

        if now - self._last_flush >= FLUSH_INTERVAL:
            self._persist_current(now)

    def break_segment(self, at: datetime | None = None) -> None:
        """Close the current segment, e.g. after system sleep or a clock jump."""
        self._end_current(at or datetime.now())
        if self.state == "active":
            self.state = "unavailable"

    def clear(self, now: datetime | None = None) -> None:
        at = now or datetime.now()
        self._end_current(at)
        try:
            self.db.clear_all()
        except Exception:
            LOG.exception("Failed to clear usage data")
        self.totals.clear()
        self.hours = [0] * 24
        self.recent.clear()
        self.state = "active" if not self.paused else "paused"
        self._load_today()

    def close(self, now: datetime | None = None) -> None:
        self._end_current(now or datetime.now())

    def snapshot(self, now: datetime | None = None) -> Snapshot:
        instant = now or datetime.now()
        apps: dict[str, AppUsage] = {key: value for key, value in self.totals.items()}
        hours = list(self.hours)

        if self.current and self.current.seconds > 0:
            current = self.current
            previous = apps.get(current.key)
            apps[current.key] = AppUsage(
                key=current.key,
                name=current.name,
                exe_path=current.exe_path,
                seconds=(previous.seconds if previous else 0) + current.seconds,
            )
            if current.date == self.today and 0 <= current.hour < 24:
                hours[current.hour] += current.seconds

        recent: list[RecentSession] = []
        if self.current and self.current.seconds > 0:
            current = self.current
            recent.append(
                RecentSession(
                    key=current.key,
                    name=current.name,
                    exe_path=current.exe_path,
                    started_at=current.started_at.isoformat(timespec="seconds"),
                    ended_at=instant.isoformat(timespec="seconds"),
                    seconds=current.seconds,
                    title=current.title,
                    is_current=True,
                )
            )
        recent.extend(self.recent)
        recent = recent[:8]

        ordered = sorted(apps.values(), key=lambda a: (-a.seconds, a.name.lower()))
        return Snapshot(
            today=self.today,
            state=self.state,
            paused=self.paused,
            current_key=self.current.key if self.current else "",
            current_name=self.current.name if self.current else "",
            current_title=self.current.title if self.current else "",
            current_exe=self.current.exe_path if self.current else "",
            current_started=(
                self.current.started_at.isoformat(timespec="seconds") if self.current else ""
            ),
            current_seconds=self.current.seconds if self.current else 0,
            total_seconds=sum(app.seconds for app in ordered),
            apps=tuple(ordered),
            hours=tuple(hours),
            recent=tuple(recent),
            idle_seconds=self.last_idle,
            generated_at=instant,
        )

    # --------------------------------------------------------------- internals

    def _load_today(self) -> None:
        try:
            for app in self.db.app_totals(self.today, self.today):
                self.totals[app.key] = app
            self.hours = list(self.db.hour_totals(self.today))
            self.recent = deque(self.db.recent_sessions(self.today, self.today, 20), maxlen=20)
        except Exception:
            LOG.exception("Failed to load today's usage")

    def _roll_day_if_needed(self, now: datetime) -> None:
        today = now.date().isoformat()
        if today == self.today:
            return
        self._end_current(now)
        self.today = today
        self.totals.clear()
        self.hours = [0] * 24
        self.recent.clear()
        self._load_today()

    def _transition(
        self,
        foreground: ForegroundApp | None,
        now: datetime,
        state: str,
    ) -> None:
        if state != "active" or foreground is None:
            self._end_current(now)
            return

        if self.current is not None:
            same_app = self.current.key == foreground.app_key
            same_hour = self.current.hour == now.hour
            same_date = self.current.date == now.date().isoformat()
            if not (same_app and same_hour and same_date):
                self._end_current(now)

        if self.current is None:
            self._begin(foreground, now)

    def _begin(self, foreground: ForegroundApp, now: datetime) -> None:
        started = now.replace(microsecond=0)
        key = foreground.app_key
        name = friendly_name(foreground.process_name, foreground.exe_path)
        title = foreground.title or ""
        session_id: int | None = None
        try:
            session_id = self.db.start_session(
                app_key=key,
                app_name=name,
                exe_path=foreground.exe_path,
                started_at=started,
                title=title,
            )
        except Exception:
            LOG.exception("Failed to persist session start for %s", key)
        self.current = CurrentSession(
            session_id=session_id,
            key=key,
            name=name,
            exe_path=foreground.exe_path,
            title=title,
            started_at=started,
            date=started.date().isoformat(),
            hour=started.hour,
        )
        self._last_flush = now

    def _persist_current(self, at: datetime, final: bool = False) -> None:
        current = self.current
        if current is None:
            return
        try:
            if current.session_id is None:
                current.session_id = self.db.start_session(
                    app_key=current.key,
                    app_name=current.name,
                    exe_path=current.exe_path,
                    started_at=current.started_at,
                    title=current.title,
                )
            if final and current.seconds <= 0:
                if current.session_id is not None:
                    self.db.delete_session(current.session_id)
            else:
                self.db.update_session(
                    current.session_id,
                    ended_at=at,
                    seconds=current.seconds,
                    title=current.title,
                )
        except Exception:
            LOG.exception("Failed to persist usage for %s", current.key)
        finally:
            self._last_flush = at

    def _end_current(self, at: datetime) -> None:
        current = self.current
        if current is None:
            return
        self._persist_current(at, final=True)
        if current.seconds > 0 and current.date == self.today:
            previous = self.totals.get(current.key)
            self.totals[current.key] = AppUsage(
                key=current.key,
                name=current.name,
                exe_path=current.exe_path,
                seconds=(previous.seconds if previous else 0) + current.seconds,
            )
            if 0 <= current.hour < 24:
                self.hours[current.hour] += current.seconds
            self.recent.appendleft(
                RecentSession(
                    key=current.key,
                    name=current.name,
                    exe_path=current.exe_path,
                    started_at=current.started_at.isoformat(timespec="seconds"),
                    ended_at=at.isoformat(timespec="seconds"),
                    seconds=current.seconds,
                    title=current.title,
                    is_current=False,
                )
            )
        self.current = None
