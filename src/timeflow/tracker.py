"""Background polling thread around :class:`UsageEngine`."""

from __future__ import annotations

import logging
import os
import queue
import threading
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from .db import Database, cleanup_old_data
from .engine import UsageEngine
from .models import Snapshot
from .win32 import ForegroundApp, get_foreground_app, get_idle_seconds

LOG = logging.getLogger(__name__)


class TrackerThread(threading.Thread):
    def __init__(
        self,
        db_path: str | Path,
        *,
        idle_seconds: int = 180,
        self_pid: int | None = None,
        on_snapshot: Callable[[Snapshot], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        foreground_provider: Callable[[], ForegroundApp | None] = get_foreground_app,
        idle_provider: Callable[[], int] = get_idle_seconds,
        tick_seconds: float = 1.0,
    ) -> None:
        super().__init__(name="TimeTraceTracker", daemon=True)
        self.db_path = Path(db_path)
        self.idle_seconds = max(1, int(idle_seconds))
        self.self_pid = int(self_pid if self_pid is not None else os.getpid())
        self.on_snapshot = on_snapshot or (lambda _snapshot: None)
        self.on_error = on_error or (lambda _message: None)
        self.foreground_provider = foreground_provider
        self.idle_provider = idle_provider
        self.tick_seconds = max(0.2, float(tick_seconds))
        self._stop = threading.Event()
        self._commands: queue.Queue[tuple[str, object]] = queue.Queue()
        self._paused = False
        self._engine: UsageEngine | None = None
        self._last_error = 0.0

    # ------------------------------------------------------------ public api

    def pause(self) -> None:
        self._commands.put(("pause", True))

    def resume(self) -> None:
        self._commands.put(("pause", False))

    def set_idle_seconds(self, seconds: int) -> None:
        self._commands.put(("idle", max(15, int(seconds))))

    def clear_data(self) -> None:
        self._commands.put(("clear", None))

    def stop(self, timeout: float = 3.0) -> None:
        self._stop.set()
        if self.is_alive():
            self.join(timeout=timeout)

    # ----------------------------------------------------------------- thread

    def run(self) -> None:
        try:
            db = Database(self.db_path)
        except Exception as exc:
            LOG.exception("Could not open the usage database")
            self._report_error(f"无法打开本地数据库：{exc}")
            return

        try:
            cleanup_old_data(db, days=365)
        except Exception:
            LOG.exception("Could not prune old usage data")

        engine = UsageEngine(
            db,
            self_pid=self.self_pid,
            idle_seconds=self.idle_seconds,
        )
        self._engine = engine
        last_now = datetime.now()
        self._emit(engine, last_now)

        try:
            while not self._stop.is_set():
                cycle_started = time.monotonic()
                self._drain_commands(engine)
                now = datetime.now()

                # A sleep/hibernate or a stalled process must not be counted as
                # foreground activity.
                if (now - last_now).total_seconds() > 5.0:
                    engine.break_segment(last_now)

                try:
                    foreground = self.foreground_provider()
                    idle_seconds = 0 if self._paused else self.idle_provider()
                    engine.tick(
                        now,
                        foreground,
                        idle_seconds,
                        paused=self._paused,
                    )
                except Exception:
                    LOG.exception("Foreground sampling failed")
                    self._report_error("读取前台窗口时出现异常，已跳过本次采样")

                self._emit(engine, now)
                last_now = now
                elapsed = time.monotonic() - cycle_started
                self._stop.wait(max(0.2, self.tick_seconds - elapsed))
        finally:
            try:
                engine.close(datetime.now())
            except Exception:
                LOG.exception("Failed to finalize current session")
            try:
                db.close()
            except Exception:
                LOG.exception("Failed to close the database")
            self._engine = None

    # --------------------------------------------------------------- helpers

    def _drain_commands(self, engine: UsageEngine) -> None:
        while True:
            try:
                command, value = self._commands.get_nowait()
            except queue.Empty:
                return
            if command == "pause":
                self._paused = bool(value)
                if self._paused:
                    engine.break_segment(datetime.now())
                else:
                    engine.paused = False
            elif command == "idle":
                engine.idle_seconds = max(15, int(value))
                self.idle_seconds = engine.idle_seconds
            elif command == "clear":
                engine.clear(datetime.now())

    def _emit(self, engine: UsageEngine, now: datetime) -> None:
        try:
            self.on_snapshot(engine.snapshot(now))
        except Exception:
            LOG.exception("Snapshot callback failed")

    def _report_error(self, message: str) -> None:
        now = time.monotonic()
        if now - self._last_error < 30.0:
            return
        self._last_error = now
        try:
            self.on_error(message)
        except Exception:
            LOG.exception("Error callback failed")
