"""Human-friendly duration and time formatting (Chinese UI)."""

from __future__ import annotations

from datetime import datetime


def format_duration(seconds: int | float, *, compact: bool = False) -> str:
    total = max(0, int(round(seconds)))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)

    if compact:
        if hours:
            return f"{hours}h {minutes:02d}m"
        if minutes:
            return f"{minutes}m {secs:02d}s"
        return f"{secs}s"

    if hours:
        return f"{hours} 小时 {minutes:02d} 分"
    if minutes:
        return f"{minutes} 分 {secs:02d} 秒"
    return f"{secs} 秒"


def format_duration_tight(seconds: int | float) -> str:
    """Very short duration used in dense rows: 1h24m / 24m / 38s."""
    total = max(0, int(round(seconds)))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m"
    return f"{secs}s"


def format_clock(seconds: int | float) -> str:
    """HH:MM:SS for the live timer."""
    total = max(0, int(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_time(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def format_time_range(start: datetime, end: datetime) -> str:
    if start.date() == end.date():
        return f"{start:%H:%M}–{end:%H:%M}"
    return f"{start:%m/%d %H:%M}–{end:%m/%d %H:%M}"


def format_updated(dt: datetime | None) -> str:
    if dt is None:
        return "等待首次采样"
    return f"最近更新 {dt:%H:%M:%S}"


def format_percent(value: float) -> str:
    if value <= 0:
        return "0%"
    if value < 0.1:
        return "<0.1%"
    return f"{value:.1f}%"


def format_date_cn(date_str: str) -> str:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return date_str
    today = datetime.now().date()
    delta = (today - d.date()).days
    if delta == 0:
        return "今天"
    if delta == 1:
        return "昨天"
    if 1 < delta < 7:
        return f"{delta} 天前"
    return f"{d.month} 月 {d.day} 日"
