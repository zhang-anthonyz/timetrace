from __future__ import annotations

from datetime import datetime, timedelta

from timeflow.db import Database
from timeflow.engine import UsageEngine
from timeflow.win32 import ForegroundApp


def fg(name: str, pid: int = 100, title: str = "") -> ForegroundApp:
    return ForegroundApp(
        hwnd=pid,
        pid=pid,
        process_name=name,
        exe_path=f"C:\\Apps\\{name}",
        title=title or f"{name} window",
    )


def make_engine(db: Database, start: datetime) -> UsageEngine:
    return UsageEngine(db, self_pid=999, idle_seconds=180, now=start)


def test_counts_foreground_seconds_and_switches() -> None:
    db = Database(":memory:")
    start = datetime(2026, 11, 3, 9, 0, 0)
    engine = make_engine(db, start)

    for index in range(4):
        engine.tick(start + timedelta(seconds=index), fg("chrome.exe"), 0)
    engine.tick(start + timedelta(seconds=4), fg("code.exe"), 0)
    engine.tick(start + timedelta(seconds=5), fg("code.exe"), 0)

    snapshot = engine.snapshot(start + timedelta(seconds=5))
    assert snapshot.total_seconds == 6
    assert [(app.key, app.seconds) for app in snapshot.apps] == [
        ("chrome.exe", 4),
        ("code.exe", 2),
    ]
    assert snapshot.hours[9] == 6
    assert snapshot.state == "active"
    assert snapshot.current_key == "code.exe"

    engine.close(start + timedelta(seconds=6))
    apps = db.app_totals("2026-11-03", "2026-11-03")
    assert sum(app.seconds for app in apps) == 6
    db.close()


def test_idle_and_resume_do_not_count_idle() -> None:
    db = Database(":memory:")
    start = datetime(2026, 11, 3, 9, 0, 0)
    engine = make_engine(db, start)
    for index in range(3):
        engine.tick(start + timedelta(seconds=index), fg("notepad.exe"), 0)

    engine.tick(start + timedelta(seconds=3), fg("notepad.exe"), 180)
    snapshot = engine.snapshot(start + timedelta(seconds=3))
    assert snapshot.state == "idle"
    assert snapshot.total_seconds == 3
    assert snapshot.current_key == ""

    engine.tick(start + timedelta(seconds=4), fg("notepad.exe"), 0)
    assert engine.snapshot(start + timedelta(seconds=4)).total_seconds == 4
    db.close()


def test_self_and_lock_screen_are_excluded() -> None:
    db = Database(":memory:")
    start = datetime(2026, 11, 3, 9, 0, 0)
    engine = make_engine(db, start)
    engine.tick(start, fg("timeflow.exe", pid=999), 0)
    assert engine.snapshot(start).total_seconds == 0
    assert engine.snapshot(start).state == "self"

    engine.tick(start + timedelta(seconds=1), fg("lockapp.exe", pid=101), 0)
    assert engine.snapshot(start + timedelta(seconds=1)).total_seconds == 0
    assert engine.snapshot(start + timedelta(seconds=1)).state == "excluded"
    db.close()


def test_pause_finalizes_and_preserves_time() -> None:
    db = Database(":memory:")
    start = datetime(2026, 11, 3, 9, 0, 0)
    engine = make_engine(db, start)
    for index in range(3):
        engine.tick(start + timedelta(seconds=index), fg("chrome.exe"), 0)
    engine.tick(start + timedelta(seconds=3), fg("chrome.exe"), 0, paused=True)
    snapshot = engine.snapshot(start + timedelta(seconds=3))
    assert snapshot.paused
    assert snapshot.state == "paused"
    assert snapshot.current_key == ""
    assert snapshot.total_seconds == 3
    db.close()


def test_hour_boundary_splits_sessions() -> None:
    db = Database(":memory:")
    start = datetime(2026, 11, 3, 9, 59, 58)
    engine = make_engine(db, start)
    engine.tick(start, fg("chrome.exe"), 0)
    engine.tick(start + timedelta(seconds=1), fg("chrome.exe"), 0)
    engine.tick(start + timedelta(seconds=2), fg("chrome.exe"), 0)
    engine.tick(start + timedelta(seconds=3), fg("chrome.exe"), 0)

    snapshot = engine.snapshot(start + timedelta(seconds=3))
    assert snapshot.total_seconds == 4
    assert snapshot.hours[9] == 2
    assert snapshot.hours[10] == 2
    db.close()


def test_clear_resets_everything() -> None:
    db = Database(":memory:")
    start = datetime(2026, 11, 3, 9, 0, 0)
    engine = make_engine(db, start)
    for index in range(4):
        engine.tick(start + timedelta(seconds=index), fg("chrome.exe"), 0)
    engine.clear(start + timedelta(seconds=4))
    snapshot = engine.snapshot(start + timedelta(seconds=4))
    assert snapshot.total_seconds == 0
    assert snapshot.apps == ()
    assert snapshot.recent == ()
    db.close()
