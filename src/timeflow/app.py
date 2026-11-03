"""Application bootstrap: single instance, tracker, tray and dashboard."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox

from . import __version__, autostart, paths
from .config import Settings, load_settings, save_settings
from .db import Database
from .models import Snapshot
from .tracker import TrackerThread
from .ui import icons, theme
from .ui.main_window import MainWindow
from .ui.tray import TrayController

LOG = logging.getLogger(__name__)
SINGLE_INSTANCE_KEY = "TimeTrace-Desktop-7D2B4A1C"


class TrackerBridge(QObject):
    snapshot = Signal(object)
    error = Signal(str)


class SingleInstance(QObject):
    show_requested = Signal()

    def __init__(self, key: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.primary = True
        self._server = QLocalServer(self)
        socket = QLocalSocket()
        socket.connectToServer(key)
        if socket.waitForConnected(350):
            socket.write(b"show")
            socket.waitForBytesWritten(350)
            socket.disconnectFromServer()
            self.primary = False
            return

        QLocalServer.removeServer(key)
        self._server.newConnection.connect(self._accept_connection)
        if not self._server.listen(key):
            LOG.warning("Single-instance server could not listen: %s", self._server.errorString())
            self.primary = True

    def _accept_connection(self) -> None:
        while self._server.hasPendingConnections():
            connection = self._server.nextPendingConnection()
            if connection is None:
                return
            connection.readyRead.connect(lambda c=connection: self._read(c))
            connection.disconnected.connect(connection.deleteLater)

    def _read(self, connection: QLocalSocket) -> None:
        data = bytes(connection.readAll())
        if b"show" in data:
            self.show_requested.emit()
        connection.disconnectFromServer()


class TimeTraceApplication:
    def __init__(self, app: QApplication, settings: Settings, minimized: bool) -> None:
        self.app = app
        self.settings = settings
        self._paused = False
        self._stopping = False
        self._tray_hint_shown = settings.tray_hint_shown

        self.db = Database(paths.db_path())
        self.bridge = TrackerBridge()
        self.window = MainWindow(
            db=self.db,
            db_path=paths.db_path(),
            settings=self.settings,
        )
        self.window.hide()

        self.tray: TrayController | None = None
        if TrayController.available():
            self.tray = TrayController(self.settings.start_with_windows)
            self.tray.show_requested.connect(self.show_window)
            self.tray.pause_requested.connect(self.set_paused)
            self.tray.settings_requested.connect(self.open_settings)
            self.tray.autostart_requested.connect(self.set_autostart)
            self.tray.quit_requested.connect(self.quit)

        self.window.pause_toggled.connect(self.set_paused)
        self.window.settings_saved.connect(self.apply_settings)
        self.window.clear_requested.connect(self.clear_data)
        self.window.hidden_to_tray.connect(self._on_hidden_to_tray)

        self.bridge.snapshot.connect(self._on_snapshot)
        self.bridge.error.connect(self._on_error)

        self.tracker = TrackerThread(
            paths.db_path(),
            idle_seconds=self.settings.idle_seconds,
            on_snapshot=self.bridge.snapshot.emit,
            on_error=self.bridge.error.emit,
        )

        self._apply_autostart(self.settings.start_with_windows, silent=True)
        self.tracker.start()

        self.app.aboutToQuit.connect(self.shutdown)
        if minimized or self.settings.start_minimized:
            self.window.hide()
            if self.tray:
                QTimer.singleShot(
                    900,
                    lambda: self.tray.show_message(
                        "时迹正在后台记录",
                        "双击托盘图标即可打开实时面板。",
                    )
                    if self.tray
                    else None,
                )
        else:
            self.show_window()

    # ------------------------------------------------------------- lifecycle

    def show_window(self) -> None:
        self.window.show_window()

    def open_settings(self) -> None:
        self.show_window()
        self.window.open_settings()

    def set_paused(self, paused: bool) -> None:
        self._paused = bool(paused)
        if paused:
            self.tracker.pause()
        else:
            self.tracker.resume()
        if self.tray:
            self.tray.set_paused(paused)

    def clear_data(self) -> None:
        self.tracker.clear_data()

    def apply_settings(self, settings: Settings) -> None:
        self.settings = settings
        try:
            save_settings(paths.settings_path(), settings)
        except OSError as exc:
            LOG.exception("Could not save settings")
            QMessageBox.warning(self.window, "保存失败", f"无法保存设置：\n{exc}")
        self.tracker.set_idle_seconds(settings.idle_seconds)
        self._apply_autostart(settings.start_with_windows, silent=False)

    def set_autostart(self, enabled: bool) -> None:
        self.settings.start_with_windows = enabled
        try:
            autostart.set_enabled(enabled)
        except OSError as exc:
            LOG.exception("Could not update autostart")
            QMessageBox.warning(
                self.window,
                "开机启动设置失败",
                f"无法修改 Windows 启动项：\n{exc}",
            )
            if self.tray:
                self.tray.set_start_with_windows(autostart.is_enabled())
            self.settings.start_with_windows = autostart.is_enabled()
            return
        try:
            save_settings(paths.settings_path(), self.settings)
        except OSError:
            LOG.exception("Could not save autostart setting")
        if self.tray:
            self.tray.set_start_with_windows(enabled)

    def quit(self) -> None:
        self.app.quit()

    def shutdown(self) -> None:
        if self._stopping:
            return
        self._stopping = True
        self.window.prepare_quit()
        try:
            self.tracker.stop()
        except Exception:
            LOG.exception("Tracker shutdown failed")
        try:
            save_settings(paths.settings_path(), self.settings)
        except OSError:
            LOG.exception("Could not save settings on exit")
        try:
            self.db.close()
        except Exception:
            LOG.exception("Database close failed")
        if self.tray:
            self.tray.hide()

    # --------------------------------------------------------------- signals

    def _on_snapshot(self, snapshot: Snapshot) -> None:
        self._paused = snapshot.paused
        self.window.update_snapshot(snapshot)
        if self.tray:
            self.tray.update_snapshot(snapshot)

    def _on_error(self, message: str) -> None:
        LOG.warning("Tracker error: %s", message)
        if self.tray:
            self.tray.show_message("时迹采样异常", message)

    def _on_hidden_to_tray(self) -> None:
        if not self.tray:
            return
        if self._tray_hint_shown:
            return
        self._tray_hint_shown = True
        self.settings.tray_hint_shown = True
        try:
            save_settings(paths.settings_path(), self.settings)
        except OSError:
            pass
        self.tray.show_message(
            "时迹仍在后台记录",
            "关闭窗口不会停止统计。双击托盘图标可以重新打开面板。",
        )

    def _apply_autostart(self, enabled: bool, silent: bool) -> None:
        try:
            autostart.set_enabled(enabled)
        except OSError as exc:
            LOG.exception("Could not apply autostart setting")
            if not silent:
                QMessageBox.warning(
                    self.window,
                    "开机启动设置失败",
                    f"无法修改 Windows 启动项：\n{exc}",
                )
            return
        if self.tray:
            self.tray.set_start_with_windows(enabled)


def setup_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )
    try:
        file_handler = RotatingFileHandler(
            paths.log_path(),
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        root.addHandler(file_handler)
    except OSError:
        pass
    if debug:
        stream = logging.StreamHandler()
        stream.setFormatter(formatter)
        stream.setLevel(level)
        root.addHandler(stream)


def _install_exception_hook() -> None:
    def hook(exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        LOG.critical("Unhandled exception", exc_info=(exc_type, exc, tb))

    sys.excepthook = hook


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv if argv is None else argv)
    parser = argparse.ArgumentParser(prog="TimeTrace", add_help=True)
    parser.add_argument("--minimized", action="store_true", help="start in the system tray")
    parser.add_argument("--debug", action="store_true", help="enable debug logging")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    args, qt_args = parser.parse_known_args(arguments[1:])
    if args.version:
        print(__version__)
        return 0

    setup_logging(args.debug or os.environ.get("TIMEFLOW_DEBUG") == "1")
    _install_exception_hook()

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication([arguments[0]] + qt_args)
    app.setApplicationName("TimeTrace")
    app.setApplicationDisplayName("时迹")
    app.setOrganizationName("TimeTrace")
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")
    app.setFont(theme.ui_font(10))
    app.setWindowIcon(icons.app_icon())
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(theme.stylesheet())

    single = SingleInstance(SINGLE_INSTANCE_KEY, app)
    if not single.primary:
        return 0

    settings = load_settings(paths.settings_path())
    try:
        controller = TimeTraceApplication(app, settings, minimized=args.minimized)
    except Exception as exc:
        LOG.exception("Startup failed")
        QMessageBox.critical(
            None,
            "时迹无法启动",
            f"启动时出现错误：\n{exc}\n\n日志位置：\n{paths.log_path()}",
        )
        return 1

    single.show_requested.connect(controller.show_window)
    # Keep the object alive for the lifetime of the event loop.
    app._timetrace_controller = controller  # type: ignore[attr-defined]
    app._timetrace_single = single  # type: ignore[attr-defined]
    return app.exec()
