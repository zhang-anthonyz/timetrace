from __future__ import annotations

from datetime import datetime

from timeflow.format import (
    format_clock,
    format_duration,
    format_duration_tight,
    format_percent,
)


def test_duration_formatting() -> None:
    assert format_duration(0) == "0 秒"
    assert format_duration(59) == "59 秒"
    assert format_duration(60) == "1 分 00 秒"
    assert format_duration(3661) == "1 小时 01 分"
    assert format_duration_tight(3661) == "1h01m"
    assert format_duration_tight(61) == "1m"
    assert format_duration_tight(9) == "9s"


def test_clock_formatting() -> None:
    assert format_clock(0) == "00:00:00"
    assert format_clock(3661) == "01:01:01"
    assert format_clock(-4) == "00:00:00"


def test_percent_formatting() -> None:
    assert format_percent(0) == "0%"
    assert format_percent(0.04) == "<0.1%"
    assert format_percent(12.34) == "12.3%"


def test_hour_and_time() -> None:
    assert datetime(2026, 11, 3, 14, 5).strftime("%H:%M") == "14:05"
