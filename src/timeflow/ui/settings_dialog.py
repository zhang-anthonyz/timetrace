"""Settings dialog."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..config import Settings
from ..win32 import enable_dark_title_bar
from . import icons, theme
from .widgets import Card, Switch


class ToggleRow(QWidget):
    def __init__(
        self,
        title: str,
        subtitle: str,
        checked: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 7, 0, 7)
        layout.setSpacing(14)

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(2)
        title_label = QLabel(title)
        title_label.setStyleSheet(f"color: {theme.TEXT}; font-size: 13px; font-weight: 500;")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setStyleSheet(f"color: {theme.FAINT}; font-size: 11px;")
        subtitle_label.setWordWrap(True)
        text.addWidget(title_label)
        text.addWidget(subtitle_label)
        layout.addLayout(text, 1)

        self.switch = Switch()
        self.switch.setChecked(checked)
        layout.addWidget(self.switch, 0, Qt.AlignmentFlag.AlignVCenter)


class SettingsDialog(QDialog):
    def __init__(
        self,
        settings: Settings,
        db_path: Path,
        on_export: Callable[[Path], int],
        on_clear: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setModal(True)
        self.setFixedWidth(570)
        self._settings = settings.copy()
        self._db_path = db_path
        self._on_export = on_export
        self._on_clear = on_clear

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(16)

        header = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(icons.app_pixmap(42))
        logo.setFixedSize(42, 42)
        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(1)
        title = QLabel("设置")
        title.setStyleSheet(f"color: {theme.TEXT}; font-size: 20px; font-weight: 700;")
        subtitle = QLabel(f"时迹 TimeTrace {__version__} · 本地应用用时统计")
        subtitle.setStyleSheet(f"color: {theme.FAINT}; font-size: 11px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addWidget(logo)
        header.addSpacing(10)
        header.addLayout(title_box, 1)
        root.addLayout(header)

        # ---------------------------------------------------------- tracking
        tracking = Card()
        tracking_layout = QVBoxLayout(tracking)
        tracking_layout.setContentsMargins(18, 15, 18, 15)
        tracking_layout.setSpacing(8)
        tracking_layout.addWidget(self._section_title("记录规则", "空闲时不累计应用用时"))
        row = QHBoxLayout()
        row.setContentsMargins(0, 2, 0, 2)
        row.setSpacing(12)
        label_box = QVBoxLayout()
        label_box.setContentsMargins(0, 0, 0, 0)
        label_box.setSpacing(2)
        idle_label = QLabel("空闲判定")
        idle_label.setStyleSheet(f"color: {theme.TEXT}; font-size: 13px; font-weight: 500;")
        idle_hint = QLabel("超过该时长没有键盘或鼠标输入，就暂停计时")
        idle_hint.setStyleSheet(f"color: {theme.FAINT}; font-size: 11px;")
        label_box.addWidget(idle_label)
        label_box.addWidget(idle_hint)
        row.addLayout(label_box, 1)

        self._idle_combo = QComboBox()
        for label, seconds in (
            ("1 分钟", 60),
            ("3 分钟", 180),
            ("5 分钟", 300),
            ("10 分钟", 600),
            ("15 分钟", 900),
        ):
            self._idle_combo.addItem(label, seconds)
        self._select_idle(settings.idle_seconds)
        row.addWidget(self._idle_combo, 0, Qt.AlignmentFlag.AlignVCenter)
        tracking_layout.addLayout(row)
        root.addWidget(tracking)

        # ------------------------------------------------------------- startup
        startup = Card()
        startup_layout = QVBoxLayout(startup)
        startup_layout.setContentsMargins(18, 12, 18, 12)
        startup_layout.setSpacing(0)
        startup_layout.addWidget(self._section_title("启动", "让统计在后台自动运行"))
        self._startup_row = ToggleRow(
            "开机自动启动",
            "登录 Windows 后自动开始记录，不弹出面板",
            settings.start_with_windows,
        )
        self._minimized_row = ToggleRow(
            "启动时最小化到托盘",
            "手动打开时也直接进入后台，不打扰当前工作",
            settings.start_minimized,
        )
        startup_layout.addWidget(self._startup_row)
        startup_layout.addWidget(self._divider())
        startup_layout.addWidget(self._minimized_row)
        root.addWidget(startup)

        # ---------------------------------------------------------------- data
        data_card = Card()
        data_layout = QVBoxLayout(data_card)
        data_layout.setContentsMargins(18, 14, 18, 14)
        data_layout.setSpacing(10)
        data_layout.addWidget(self._section_title("数据", "仅保存在这台电脑上，不上传网络"))

        path_label = QLabel(str(db_path))
        path_label.setStyleSheet(f"color: {theme.FAINT}; font-size: 10px;")
        path_label.setWordWrap(True)
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        data_layout.addWidget(path_label)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)
        open_button = QPushButton("打开数据文件夹")
        open_button.setObjectName("ghost")
        open_button.setIcon(icons.glyph_icon("folder", theme.MUTED, 16))
        open_button.clicked.connect(self._open_folder)
        export_button = QPushButton("导出 CSV")
        export_button.setObjectName("ghost")
        export_button.setIcon(icons.glyph_icon("export", theme.MUTED, 16))
        export_button.clicked.connect(self._export)
        clear_button = QPushButton("清除全部记录")
        clear_button.setObjectName("danger")
        clear_button.clicked.connect(self._clear)
        actions.addWidget(open_button)
        actions.addWidget(export_button)
        actions.addStretch(1)
        actions.addWidget(clear_button)
        data_layout.addLayout(actions)
        root.addWidget(data_card)

        note = QLabel("提示：统计的是前台窗口活跃时间；空闲、锁屏和时迹自身不计入。")
        note.setStyleSheet(f"color: {theme.FAINT}; font-size: 10px;")
        note.setWordWrap(True)
        root.addWidget(note)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 2, 0, 0)
        buttons.setSpacing(8)
        buttons.addStretch(1)
        cancel = QPushButton("取消")
        cancel.setObjectName("ghost")
        cancel.clicked.connect(self.reject)
        save = QPushButton("保存设置")
        save.setObjectName("primary")
        save.clicked.connect(self._save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        root.addLayout(buttons)

    def showEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().showEvent(event)
        try:
            enable_dark_title_bar(int(self.winId()))
        except Exception:
            pass

    def result_settings(self) -> Settings:
        idle = int(self._idle_combo.currentData())
        self._settings.idle_seconds = idle
        self._settings.start_with_windows = self._startup_row.switch.isChecked()
        self._settings.start_minimized = self._minimized_row.switch.isChecked()
        return self._settings.normalized()

    def _section_title(self, title: str, hint: str) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 4)
        layout.setSpacing(8)
        label = QLabel(title)
        label.setStyleSheet(f"color: {theme.TEXT}; font-size: 13px; font-weight: 700;")
        hint_label = QLabel(hint)
        hint_label.setStyleSheet(f"color: {theme.FAINT}; font-size: 10px;")
        layout.addWidget(label)
        layout.addWidget(hint_label)
        layout.addStretch(1)
        return widget

    def _divider(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"background: {theme.BORDER_SOFT}; border: none; max-height: 1px;")
        return line

    def _select_idle(self, seconds: int) -> None:
        index = self._idle_combo.findData(seconds)
        if index >= 0:
            self._idle_combo.setCurrentIndex(index)
            return
        self._idle_combo.addItem(f"{seconds // 60} 分钟", seconds)
        self._idle_combo.setCurrentIndex(self._idle_combo.count() - 1)

    def _open_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._db_path.parent)))

    def _export(self) -> None:
        today = date.today()
        default = self._db_path.parent / f"时迹_{today.isoformat()}.csv"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出用时记录",
            str(default),
            "CSV 文件 (*.csv)",
        )
        if not path:
            return
        try:
            count = self._on_export(Path(path))
        except Exception as exc:
            QMessageBox.warning(self, "导出失败", f"无法写入 CSV：\n{exc}")
            return
        QMessageBox.information(
            self,
            "导出完成",
            f"已导出 {count} 条记录到：\n{path}",
        )

    def _clear(self) -> None:
        answer = QMessageBox.question(
            self,
            "清除全部记录",
            "确定要删除所有历史用时记录吗？\n此操作无法撤销，建议先导出 CSV。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._on_clear()
        except Exception as exc:
            QMessageBox.warning(self, "清除失败", f"无法清除数据：\n{exc}")
            return
        QMessageBox.information(self, "已清除", "所有用时记录已删除。")

    def _save(self) -> None:
        self.accept()
