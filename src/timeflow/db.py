"""SQLite persistence for usage sessions."""

from __future__ import annotations

import csv
import sqlite3
from datetime import date, datetime
from pathlib import Path

from .format import format_duration
from .models import AppUsage, RecentSession

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_key TEXT NOT NULL,
    app_name TEXT NOT NULL,
    exe_path TEXT,
    started_at TEXT NOT NULL,
    ended_at TEXT NOT NULL,
    seconds INTEGER NOT NULL DEFAULT 0,
    date TEXT NOT NULL,
    hour INTEGER NOT NULL,
    last_title TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_date ON sessions(date);
CREATE INDEX IF NOT EXISTS idx_sessions_date_app ON sessions(date, app_key);
CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_at);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self._memory = self.path == ":memory:"
        self.conn = sqlite3.connect(self.path, timeout=5.0)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA busy_timeout=5000")
        if not self._memory:
            self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.executescript(SCHEMA)
        self.conn.commit()
        self.conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

    def close(self) -> None:
        try:
            self.conn.close()
        except sqlite3.Error:
            pass

    # ---------------------------------------------------------------- writes

    def start_session(
        self,
        app_key: str,
        app_name: str,
        exe_path: str,
        started_at: datetime,
        title: str,
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO sessions
                (app_key, app_name, exe_path, started_at, ended_at,
                 seconds, date, hour, last_title)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)
            """,
            (
                app_key,
                app_name,
                exe_path,
                started_at.isoformat(timespec="seconds"),
                started_at.isoformat(timespec="seconds"),
                started_at.date().isoformat(),
                started_at.hour,
                title,
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def update_session(
        self,
        session_id: int,
        ended_at: datetime,
        seconds: int,
        title: str,
    ) -> None:
        self.conn.execute(
            """
            UPDATE sessions
               SET ended_at = ?, seconds = ?, last_title = ?
             WHERE id = ?
            """,
            (ended_at.isoformat(timespec="seconds"), max(0, int(seconds)), title, session_id),
        )
        self.conn.commit()

    def delete_session(self, session_id: int) -> None:
        self.conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        self.conn.commit()

    # ---------------------------------------------------------------- reads

    def app_totals(self, start_date: str, end_date: str) -> list[AppUsage]:
        rows = self.conn.execute(
            """
            SELECT s.app_key, s.app_name, s.exe_path, t.seconds
              FROM (
                    SELECT app_key, SUM(seconds) AS seconds, MAX(id) AS max_id
                      FROM sessions
                     WHERE date BETWEEN ? AND ? AND seconds > 0
                     GROUP BY app_key
              ) t
              JOIN sessions s ON s.id = t.max_id
             ORDER BY t.seconds DESC, s.app_name COLLATE NOCASE ASC
            """,
            (start_date, end_date),
        ).fetchall()
        return [
            AppUsage(
                key=str(r["app_key"]),
                name=str(r["app_name"]),
                exe_path=str(r["exe_path"] or ""),
                seconds=int(r["seconds"] or 0),
            )
            for r in rows
        ]

    def hour_totals(self, day: str) -> tuple[int, ...]:
        rows = self.conn.execute(
            """
            SELECT hour, SUM(seconds) AS seconds
              FROM sessions
             WHERE date = ? AND seconds > 0
             GROUP BY hour
            """,
            (day,),
        ).fetchall()
        hours = [0] * 24
        for row in rows:
            index = int(row["hour"] or 0)
            if 0 <= index < 24:
                hours[index] = int(row["seconds"] or 0)
        return tuple(hours)

    def day_totals(self, start_date: str, end_date: str) -> dict[str, int]:
        rows = self.conn.execute(
            """
            SELECT date, SUM(seconds) AS seconds
              FROM sessions
             WHERE date BETWEEN ? AND ? AND seconds > 0
             GROUP BY date
            """,
            (start_date, end_date),
        ).fetchall()
        return {str(r["date"]): int(r["seconds"] or 0) for r in rows}

    def recent_sessions(
        self,
        start_date: str,
        end_date: str,
        limit: int = 8,
    ) -> list[RecentSession]:
        rows = self.conn.execute(
            """
            SELECT app_key, app_name, exe_path, started_at, ended_at,
                   seconds, last_title
              FROM sessions
             WHERE date BETWEEN ? AND ? AND seconds > 0
             ORDER BY started_at DESC, id DESC
             LIMIT ?
            """,
            (start_date, end_date, max(1, int(limit))),
        ).fetchall()
        return [
            RecentSession(
                key=str(r["app_key"]),
                name=str(r["app_name"]),
                exe_path=str(r["exe_path"] or ""),
                started_at=str(r["started_at"]),
                ended_at=str(r["ended_at"]),
                seconds=int(r["seconds"] or 0),
                title=str(r["last_title"] or ""),
            )
            for r in rows
        ]

    def total_seconds(self, start_date: str, end_date: str) -> int:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(seconds), 0) AS total FROM sessions "
            "WHERE date BETWEEN ? AND ? AND seconds > 0",
            (start_date, end_date),
        ).fetchone()
        return int(row["total"] or 0)

    def session_count(self, start_date: str, end_date: str) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM sessions "
            "WHERE date BETWEEN ? AND ? AND seconds > 0",
            (start_date, end_date),
        ).fetchone()
        return int(row["n"] or 0)

    def dates_with_data(self, limit: int = 400) -> list[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT date FROM sessions WHERE seconds > 0 "
            "ORDER BY date DESC LIMIT ?",
            (max(1, int(limit)),),
        ).fetchall()
        return [str(r["date"]) for r in rows]

    # ---------------------------------------------------------------- ops

    def clear_all(self) -> None:
        self.conn.execute("DELETE FROM sessions")
        self.conn.commit()

    def prune(self, before_date: str) -> int:
        cur = self.conn.execute(
            "DELETE FROM sessions WHERE date < ?",
            (before_date,),
        )
        self.conn.commit()
        return int(cur.rowcount or 0)

    def export_csv(self, path: str | Path, start_date: str, end_date: str) -> int:
        rows = self.conn.execute(
            """
            SELECT date, started_at, ended_at, app_name, app_key,
                   exe_path, last_title, seconds
              FROM sessions
             WHERE date BETWEEN ? AND ? AND seconds > 0
             ORDER BY started_at ASC, id ASC
            """,
            (start_date, end_date),
        ).fetchall()
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(
                [
                    "日期",
                    "开始时间",
                    "结束时间",
                    "应用",
                    "进程",
                    "可执行文件",
                    "窗口标题",
                    "时长(秒)",
                    "时长",
                ]
            )
            for row in rows:
                seconds = int(row["seconds"] or 0)
                writer.writerow(
                    [
                        row["date"],
                        row["started_at"],
                        row["ended_at"],
                        row["app_name"],
                        row["app_key"],
                        row["exe_path"] or "",
                        row["last_title"] or "",
                        seconds,
                        format_duration(seconds),
                    ]
                )
        return len(rows)


def cleanup_old_data(db: Database, days: int = 365) -> int:
    cutoff = date.fromordinal(date.today().toordinal() - max(1, days))
    return db.prune(cutoff.isoformat())
