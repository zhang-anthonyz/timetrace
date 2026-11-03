"""Main real-time dashboard window."""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QSettings, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..config import Settings
from ..db import Database
from ..format import format_duration, format_updated
from ..models import Snapshot
from ..win32 import enable_dark_title_bar
from . import icons, theme
from .settings_dialog import SettingsDialog
from .widgets import (
    AppRanking,
    BarChart,
    Card,
    CurrentCard,
    RecentList,
    SegmentedControl,
    ShareCard,
    StatusChip,
    TotalCard,
)

RANGES = {"today": 1, "7d": 7, "30d": 30}


class MainWindow(QMainWindow):
    pause_toggled = Signal(bool)
    settings_saved = Signal(object)
    clear_requested = Signal()
    hidden_to_tray = Signal()

    def __init__(
        self,
        db: Database,
        db_path: Path,
        settings: Settings,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._db = db
        self._db_path = db_path
        self._settings = settings
        self._snapshot: Snapshot | None = None
        self._range = "today"
        self._paused = False
        self._quitting = False
        self._last_live_render = 0.0
        self._last_history_render = 0.0
        self._last_snapshot_at: datetime | None = None
        self._qsettings = QSettings(
            str(db_path.parent / "ui.ini"),
            QSettings.Format.IniFormat,
        )

        self.setWindowTitle("实时应用用时")
        self.setWindowIcon(icons.app_icon())
        self.resize(1240, 900)
        self.setMinimumSize(1040, 720)
        self._build_ui()
        self._restore_geometry()

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()

        self._settings_shortcut = QShortcut(QKeySequence("Ctrl+,"), self)
        self._settings_shortcut.activated.connect(self.open_settings)
        self._show_empty("正在启动采样…")

    # ------------------------------------------------------------------ build

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(26, 22, 26, 22)
        outer.setSpacing(16)

        outer.addLayout(self._build_header())

        hero = QHBoxLayout()
        hero.setContentsMargins(0, 0, 0, 0)
        hero.setSpacing(16)
        self._total_card = TotalCard()
        self._current_card = CurrentCard()
        hero.addWidget(self._total_card, 3)
        hero.addWidget(self._current_card, 2)
        outer.addLayout(hero)

        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(16)

        apps_card = Card()
        apps_layout = QVBoxLayout(apps_card)
        apps_layout.setContentsMargins(18, 14, 12, 8)
        apps_layout.setSpacing(8)
        apps_header = QHBoxLayout()
        apps_header.setContentsMargins(0, 0, 0, 0)
        apps_header.setSpacing(8)
        apps_title = QLabel("应用用时")
        apps_title.setObjectName("sectionTitle")
        apps_hint = QLabel("按前台活跃时长排序")
        apps_hint.setObjectName("cardHint")
        self._apps_count = QLabel("")
        self._apps_count.setObjectName("cardHint")
        self._apps_count.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        apps_header.addWidget(apps_title)
        apps_header.addWidget(apps_hint)
        apps_header.addStretch(1)
        apps_header.addWidget(self._apps_count)
        apps_layout.addLayout(apps_header)
        self._ranking = AppRanking()
        apps_layout.addWidget(self._ranking, 1)
        apps_card.setMinimumHeight(160)

        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(16)
        left.addWidget(apps_card, 1)
        self._share = ShareCard()
        left.addWidget(self._share, 0)
        content.addLayout(left, 5)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(16)

        chart_card = Card()
        chart_card.setMinimumHeight(246)
        chart_layout = QVBoxLayout(chart_card)
        chart_layout.setContentsMargins(18, 14, 18, 10)
        chart_layout.setSpacing(4)
        chart_header = QHBoxLayout()
        chart_header.setContentsMargins(0, 0, 0, 0)
        chart_header.setSpacing(8)
        self._chart_title = QLabel("今日节奏")
        self._chart_title.setObjectName("sectionTitle")
        self._chart_hint = QLabel("按小时统计")
        self._chart_hint.setObjectName("cardHint")
        chart_header.addWidget(self._chart_title)
        chart_header.addWidget(self._chart_hint)
        chart_header.addStretch(1)
        chart_layout.addLayout(chart_header)
        self._chart = BarChart()
        chart_layout.addWidget(self._chart, 1)
        right.addWidget(chart_card, 0)

        recent_card = Card()
        recent_layout = QVBoxLayout(recent_card)
        recent_layout.setContentsMargins(18, 12, 18, 10)
        recent_layout.setSpacing(3)
        recent_header = QHBoxLayout()
        recent_header.setContentsMargins(0, 0, 0, 0)
        recent_header.setSpacing(8)
        recent_title = QLabel("最近活动")
        recent_title.setObjectName("sectionTitle")
        self._recent_hint = QLabel("实时")
        self._recent_hint.setObjectName("cardHint")
        recent_header.addWidget(recent_title)
        recent_header.addWidget(self._recent_hint)
        recent_header.addStretch(1)
        recent_layout.addLayout(recent_header)
        self._recent = RecentList()
        recent_layout.addWidget(self._recent, 1)
        right.addWidget(recent_card, 1)

        content.addLayout(right, 3)
        outer.addLayout(content, 1)

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)

        logo = QLabel()
        logo.setPixmap(icons.app_pixmap(42))
        logo.setFixedSize(42, 42)
        header.addWidget(logo)

        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(0)
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(7)
        title = QLabel("时迹")
        title.setStyleSheet(f"color: {theme.TEXT}; font-size: 22px; font-weight: 700;")
        wordmark = QLabel("TimeTrace")
        wordmark.setStyleSheet(f"color: {theme.ACCENT_SOFT}; font-size: 9px; font-weight: 600;")
        wordmark.setAlignment(
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft
        )
        version = QLabel(f"v{__version__}")
        version.setStyleSheet(f"color: {theme.FAINT}; font-size: 9px;")
        version.setAlignment(
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft
        )
        title_row.addWidget(title)
        title_row.addSpacing(2)
        title_row.addWidget(wordmark)
        title_row.addWidget(version)
        title_row.addStretch(1)
        subtitle = QLabel("看见时间留下的痕迹 · 数据不上传")
        subtitle.setStyleSheet(f"color: {theme.FAINT}; font-size: 10px;")
        title_box.addLayout(title_row)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)

        header.addStretch(1)

        self._segmented = SegmentedControl()
        self._segmented.add_item("today", "今日")
        self._segmented.add_item("7d", "近 7 天")
        self._segmented.add_item("30d", "近 30 天")
        self._segmented.set_current("today")
        self._segmented.changed.connect(self._set_range)
        self._segmented.setFixedWidth(236)
        header.addWidget(self._segmented)

        self._status = StatusChip()
        header.addWidget(self._status)

        self._pause_button = QPushButton("暂停记录")
        self._pause_button.setObjectName("pauseButton")
        self._pause_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pause_button.setIcon(icons.glyph_icon("pause", theme.MUTED, 14))
        self._pause_button.setIconSize(QSize(14, 14))
        self._pause_button.setFixedHeight(36)
        self._pause_button.setMinimumWidth(108)
        self._pause_button.clicked.connect(self._toggle_pause)
        header.addWidget(self._pause_button)

        self._settings_button = QPushButton()
        self._settings_button.setObjectName("iconButton")
        self._settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_button.setIcon(icons.glyph_icon("gear", theme.MUTED, 17))
        self._settings_button.setIconSize(QSize(17, 17))
        self._settings_button.setFixedSize(36, 36)
        self._settings_button.setToolTip("设置 (Ctrl+,)")
        self._settings_button.clicked.connect(self.open_settings)
        header.addWidget(self._settings_button)

        return header

    # ------------------------------------------------------------- public api

    def update_snapshot(self, snapshot: Snapshot) -> None:
        self._snapshot = snapshot
        self._last_snapshot_at = snapshot.generated_at
        self._paused = snapshot.paused
        self._current_card.update_snapshot(snapshot)
        self._sync_status(snapshot)
        if self._range == "today":
            now = time.monotonic()
            if now - self._last_live_render >= 1.0:
                self._render_today()

    def show_window(self) -> None:
        self.showNormal()
        try:
            enable_dark_title_bar(int(self.winId()))
        except Exception:
            pass
        self.raise_()
        self.activateWindow()

    def showEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().showEvent(event)
        try:
            enable_dark_title_bar(int(self.winId()))
        except Exception:
            pass

    def prepare_quit(self) -> None:
        self._quitting = True

    def open_settings(self) -> None:
        dialog = SettingsDialog(
            settings=self._settings,
            db_path=self._db_path,
            on_export=self._export_csv,
            on_clear=self._clear_data,
            parent=self,
        )
        if dialog.exec():
            self._settings = dialog.result_settings()
            self.settings_saved.emit(self._settings)
        self._refresh_range(force=True)

    # --------------------------------------------------------------- internal

    def _on_tick(self) -> None:
        if self._snapshot is None:
            return
        now = time.monotonic()
        if self._range == "today":
            if now - self._last_live_render >= 2.0:
                self._render_today()
        elif now - self._last_history_render >= 5.0:
            self._render_history()

    def _set_range(self, key: str) -> None:
        if key not in RANGES or key == self._range:
            return
        self._range = key
        if key == "today":
            self._chart_title.setText("今日节奏")
            self._chart_hint.setText("按小时统计")
            self._recent_hint.setText("实时")
        else:
            self._chart_title.setText("每日趋势")
            self._chart_hint.setText("按天统计")
            self._recent_hint.setText("所选范围")
        self._refresh_range(force=True)

    def _refresh_range(self, force: bool = False) -> None:
        if self._range == "today":
            self._render_today(force=force)
        else:
            self._render_history(force=force)

    def _render_today(self, force: bool = False) -> None:
        if self._range != "today" or self._snapshot is None:
            return
        if not force and self._last_snapshot_at is None:
            return
        snapshot = self._snapshot
        subtitle = (
            f"{snapshot.recorded_apps} 个应用 · {format_updated(snapshot.generated_at)}"
            if snapshot.recorded_apps
            else "还没有记录 · 每 5 秒自动保存"
        )
        self._total_card.update_data(
            "今日活跃",
            snapshot.total_seconds,
            snapshot.apps,
            subtitle,
        )
        self._ranking.set_apps(snapshot.apps)
        self._share.set_apps(snapshot.apps, range_label="今日", days=1)
        self._apps_count.setText(
            f"{snapshot.recorded_apps} 个应用" if snapshot.recorded_apps else "等待记录"
        )
        labels = [f"{hour}" for hour in range(24)]
        self._chart.set_data(
            snapshot.hours,
            labels=labels,
            highlight=datetime.now().hour,
            label_step=4,
        )
        self._recent.set_sessions(snapshot.recent, is_today=True)
        self._last_live_render = time.monotonic()

    def _render_history(self, force: bool = False) -> None:
        if self._range == "today":
            return
        days = RANGES[self._range]
        end = date.today()
        start = end - timedelta(days=days - 1)
        try:
            apps = self._db.app_totals(start.isoformat(), end.isoformat())
            day_totals = self._db.day_totals(start.isoformat(), end.isoformat())
            recent = self._db.recent_sessions(start.isoformat(), end.isoformat(), 8)
        except Exception as exc:
            self._total_card.update_data(
                f"近 {days} 天活跃",
                0,
                [],
                f"读取数据失败：{exc}",
            )
            self._share.set_apps([], range_label=f"近 {days} 天", days=days)
            return

        total = sum(app.seconds for app in apps)
        subtitle = (
            f"{len(apps)} 个应用 · 平均每天 {format_duration(total / days)}"
            if total
            else "所选范围内还没有记录"
        )
        self._total_card.update_data(f"近 {days} 天活跃", total, apps, subtitle)
        self._ranking.set_apps(apps)
        self._share.set_apps(apps, range_label=f"近 {days} 天", days=days)
        self._apps_count.setText(f"{len(apps)} 个应用" if apps else "暂无记录")

        dates = [start + timedelta(days=index) for index in range(days)]
        values = [day_totals.get(day.isoformat(), 0) for day in dates]
        labels = [f"{day.month}/{day.day}" for day in dates]
        self._chart.set_data(
            values,
            labels=labels,
            highlight=days - 1,
            label_step=1 if days <= 7 else 5,
        )
        self._recent.set_sessions(recent, is_today=False)
        self._last_history_render = time.monotonic()

    def _sync_status(self, snapshot: Snapshot) -> None:
        state = "paused" if snapshot.paused else snapshot.state
        self._status.set_state(state)
        if snapshot.paused:
            self._pause_button.setText("继续记录")
            self._pause_button.setIcon(icons.glyph_icon("play", theme.AMBER, 14))
        else:
            self._pause_button.setText("暂停记录")
            self._pause_button.setIcon(icons.glyph_icon("pause", theme.MUTED, 14))

    def _toggle_pause(self) -> None:
        target = not self._paused
        self._paused = target
        if target:
            self._status.set_state("paused")
            self._pause_button.setText("继续记录")
            self._pause_button.setIcon(icons.glyph_icon("play", theme.AMBER, 14))
        else:
            self._pause_button.setText("暂停记录")
            self._pause_button.setIcon(icons.glyph_icon("pause", theme.MUTED, 14))
        self.pause_toggled.emit(target)

    def _show_empty(self, message: str) -> None:
        self._total_card.update_data("今日活跃", 0, [], message)
        self._ranking.set_apps([])
        self._share.set_apps([], range_label="今日", days=1)
        self._apps_count.setText("等待记录")
        self._chart.set_data([0] * 24, [str(hour) for hour in range(24)], -1, 4)
        self._recent.set_sessions([], is_today=True)

    def _export_csv(self, path: Path) -> int:
        return self._db.export_csv(
            path,
            "2000-01-01",
            date.today().isoformat(),
        )

    def _clear_data(self) -> None:
        self._snapshot = None
        self._show_empty("记录已清除，正在等待新的活动…")
        self.clear_requested.emit()

    def _restore_geometry(self) -> None:
        geometry = self._qsettings.value("window/geometry")
        if geometry is not None:
            try:
                self.restoreGeometry(geometry)
            except Exception:
                pass

    def _save_geometry(self) -> None:
        self._qsettings.setValue("window/geometry", self.saveGeometry())
        self._qsettings.sync()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._save_geometry()
        if self._quitting:
            event.accept()
            return
        event.ignore()
        self.hide()
        self.hidden_to_tray.emit()
