"""System tray integration."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from ..format import format_duration, format_duration_tight
from ..models import Snapshot
from . import icons


class TrayController(QObject):
    show_requested = Signal()
    pause_requested = Signal(bool)
    settings_requested = Signal()
    autostart_requested = Signal(bool)
    quit_requested = Signal()

    def __init__(self, start_with_windows: bool, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._paused = False
        self._snapshot: Snapshot | None = None
        self._tray = QSystemTrayIcon(icons.app_icon(), self)
        self._tray.setToolTip("时迹 TimeTrace · 本地应用用时统计")
        self._tray.activated.connect(self._on_activated)

        self._menu = QMenu()
        open_action = self._menu.addAction("打开实时面板")
        open_action.triggered.connect(self.show_requested.emit)

        self._summary = self._menu.addAction("今日 0 秒")
        self._summary.setEnabled(False)
        self._top_app = self._menu.addAction("等待首次采样")
        self._top_app.setEnabled(False)

        self._menu.addSeparator()
        self._pause_action = self._menu.addAction("暂停记录")
        self._pause_action.triggered.connect(self._toggle_pause)

        self._autostart_action = self._menu.addAction("开机自动启动")
        self._autostart_action.setCheckable(True)
        self._autostart_action.setChecked(start_with_windows)
        self._autostart_action.toggled.connect(self.autostart_requested.emit)

        settings_action = self._menu.addAction("设置…")
        settings_action.triggered.connect(self.settings_requested.emit)

        self._menu.addSeparator()
        quit_action = self._menu.addAction("退出时迹")
        quit_action.triggered.connect(self.quit_requested.emit)

        self._tray.setContextMenu(self._menu)
        self._tray.show()

    @staticmethod
    def available() -> bool:
        return QSystemTrayIcon.isSystemTrayAvailable()

    def show(self) -> None:
        self._tray.show()

    def hide(self) -> None:
        self._tray.hide()

    def set_paused(self, paused: bool) -> None:
        self._paused = paused
        self._tray.setIcon(icons.app_icon(paused=paused))
        self._pause_action.setText("继续记录" if paused else "暂停记录")

    def set_start_with_windows(self, enabled: bool) -> None:
        self._autostart_action.blockSignals(True)
        self._autostart_action.setChecked(enabled)
        self._autostart_action.blockSignals(False)

    def update_snapshot(self, snapshot: Snapshot) -> None:
        self._snapshot = snapshot
        total = format_duration_tight(snapshot.total_seconds)
        self._summary.setText(f"今日 {total} · {snapshot.recorded_apps} 个应用")
        if snapshot.apps:
            top = snapshot.apps[0]
            self._top_app.setText(f"最长 {top.name} · {format_duration_tight(top.seconds)}")
            tooltip = (
                f"时迹 · 今日 {format_duration(snapshot.total_seconds)}\n"
                f"最长：{top.name}"
            )
        else:
            self._top_app.setText("还没有应用记录")
            tooltip = "时迹 · 今日暂无记录"
        self._tray.setToolTip(tooltip[:127])

        state = snapshot.state
        if snapshot.paused or state == "paused":
            if not self._paused:
                self.set_paused(True)
        elif self._paused:
            self.set_paused(False)

    def show_message(self, title: str, message: str, msecs: int = 4000) -> None:
        if self._tray.supportsMessages():
            self._tray.showMessage(
                title,
                message,
                QSystemTrayIcon.MessageIcon.Information,
                msecs,
            )

    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        self.set_paused(self._paused)
        self.pause_requested.emit(self._paused)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.DoubleClick,
            QSystemTrayIcon.ActivationReason.Trigger,
        ):
            self.show_requested.emit()
