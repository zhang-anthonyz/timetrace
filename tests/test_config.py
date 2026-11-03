from __future__ import annotations

from pathlib import Path

from timeflow.config import Settings, load_settings, save_settings
from timeflow.display import friendly_name


def test_settings_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    settings = Settings(
        idle_seconds=300,
        start_with_windows=True,
        start_minimized=True,
        tray_hint_shown=True,
    )
    save_settings(path, settings)
    loaded = load_settings(path)
    assert loaded == settings


def test_settings_clamp_and_corrupt_fallback(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"idle_seconds": 1}', encoding="utf-8")
    assert load_settings(path).idle_seconds == 15

    path.write_text("not json", encoding="utf-8")
    assert load_settings(path).idle_seconds == 180
    assert path.with_suffix(".json.bad").exists()


def test_friendly_names() -> None:
    assert friendly_name("notepad.exe", r"C:\Windows\System32\notepad.exe") == "记事本"
    assert friendly_name("chrome.exe", r"C:\Program Files\Google\Chrome\Application\chrome.exe") == "Google Chrome"
    assert friendly_name("something.exe", "") == "Something"
