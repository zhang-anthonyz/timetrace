from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from timeflow.db import Database


def make_db() -> Database:
    return Database(":memory:")


def add_session(db: Database, key: str, name: str, start: datetime, seconds: int) -> None:
    sid = db.start_session(key, name, f"C:\\Apps\\{key}.exe", start, f"{name} window")
    db.update_session(sid, start.replace(second=min(59, start.second + seconds)), seconds, f"{name} window")


def test_aggregates_and_latest_name() -> None:
    db = make_db()
    add_session(db, "chrome.exe", "Google Chrome", datetime(2026, 11, 3, 9, 0), 30)
    add_session(db, "chrome.exe", "Chrome Beta", datetime(2026, 11, 3, 10, 0), 20)
    add_session(db, "code.exe", "Visual Studio Code", datetime(2026, 11, 3, 11, 0), 50)

    apps = db.app_totals("2026-11-03", "2026-11-03")
    assert [(a.key, a.seconds, a.name) for a in apps] == [
        ("chrome.exe", 50, "Chrome Beta"),
        ("code.exe", 50, "Visual Studio Code"),
    ]
    assert db.total_seconds("2026-11-03", "2026-11-03") == 100
    assert db.hour_totals("2026-11-03")[9] == 30
    assert db.hour_totals("2026-11-03")[11] == 50
    db.close()


def test_recent_and_day_totals() -> None:
    db = make_db()
    add_session(db, "a.exe", "A", datetime(2026, 11, 1, 9, 0), 10)
    add_session(db, "b.exe", "B", datetime(2026, 11, 2, 9, 0), 20)
    add_session(db, "c.exe", "C", datetime(2026, 11, 3, 9, 0), 30)

    recent = db.recent_sessions("2026-11-01", "2026-11-03", 2)
    assert [r.key for r in recent] == ["c.exe", "b.exe"]
    assert db.day_totals("2026-11-01", "2026-11-03") == {
        "2026-11-01": 10,
        "2026-11-02": 20,
        "2026-11-03": 30,
    }
    assert db.session_count("2026-11-01", "2026-11-03") == 3
    db.close()


def test_export_csv(tmp_path: Path) -> None:
    db = make_db()
    add_session(db, "notepad.exe", "记事本", datetime(2026, 11, 3, 9, 0), 12)
    target = tmp_path / "usage.csv"
    assert db.export_csv(target, "2026-11-03", "2026-11-03") == 1
    text = target.read_text(encoding="utf-8-sig")
    assert "记事本" in text
    assert "12" in text
    with target.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh))
    assert rows[0][0] == "日期"
    assert rows[1][3] == "记事本"
    db.close()


def test_clear_and_prune() -> None:
    db = make_db()
    add_session(db, "old.exe", "Old", datetime(2024, 1, 1, 9, 0), 10)
    add_session(db, "new.exe", "New", datetime(2026, 11, 3, 9, 0), 10)
    assert db.prune("2026-01-01") == 1
    assert db.total_seconds("2000-01-01", "2030-01-01") == 10
    db.clear_all()
    assert db.total_seconds("2000-01-01", "2030-01-01") == 0
    db.close()
