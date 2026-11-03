"""Reusable, custom-painted dashboard widgets."""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import datetime
from html import escape
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from ..format import format_clock, format_duration, format_duration_tight, format_percent
from ..models import AppUsage, RecentSession, Snapshot
from ..share import ShareSlice, build_share_slices
from . import icons, theme

OTHER_COLOR = "#3F4B60"


class Card(QFrame):
    def __init__(self, parent: QWidget | None = None, alt: bool = False) -> None:
        super().__init__(parent)
        self.setObjectName("cardAlt" if alt else "card")


class ElidedLabel(QLabel):
    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        self._full_text = ""
        super().__init__("", parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setText(text)

    def setText(self, text: str) -> None:  # type: ignore[override]
        self._full_text = text or ""
        self.setToolTip(self._full_text if self._full_text else "")
        self._apply_elide()

    def full_text(self) -> str:
        return self._full_text

    def resizeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().resizeEvent(event)
        self._apply_elide()

    def _apply_elide(self) -> None:
        width = max(0, self.width())
        if not self._full_text:
            super().setText("")
            return
        if width <= 0:
            super().setText(self._full_text)
            return
        metrics = QFontMetrics(self.font())
        super().setText(
            metrics.elidedText(self._full_text, Qt.TextElideMode.ElideRight, width)
        )


class StatusChip(QWidget):
    COLORS = {
        "active": theme.MINT,
        "idle": theme.FAINT,
        "paused": theme.AMBER,
        "self": theme.ACCENT,
        "unavailable": theme.MUTED,
        "excluded": theme.FAINT,
    }
    LABELS = {
        "active": "实时记录中",
        "idle": "空闲中",
        "paused": "已暂停",
        "self": "查看面板中",
        "unavailable": "等待窗口",
        "excluded": "未记录",
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = "unavailable"
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(70)
        self._timer.timeout.connect(self._tick)
        self.setFixedHeight(30)
        self.set_state("unavailable")

    def set_state(self, state: str) -> None:
        state = state if state in self.COLORS else "unavailable"
        if state == self._state and self._timer.isActive():
            return
        self._state = state
        if state == "active":
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()
            self._phase = 0.0
        self._update_width()
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(self.width(), 30)

    def _update_width(self) -> None:
        metrics = QFontMetrics(theme.ui_font(9))
        width = metrics.horizontalAdvance(self.LABELS[self._state]) + 38
        self.setFixedWidth(max(92, width))

    def _tick(self) -> None:
        self._phase += 0.22
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = QColor(self.COLORS[self._state])
        bg = QColor(color)
        bg.setAlpha(20)
        border = QColor(color)
        border.setAlpha(48)
        painter.setPen(QPen(border, 1))
        painter.setBrush(bg)
        painter.drawRoundedRect(QRectF(0.5, 3.5, self.width() - 1, 23), 11.5, 11.5)

        alpha = 255
        if self._state == "active":
            alpha = 150 + int(85 * (0.5 + 0.5 * math.sin(self._phase)))
        dot_color = QColor(color)
        dot_color.setAlpha(alpha)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(dot_color)
        painter.drawEllipse(QPointF(14, 15), 3.4, 3.4)

        painter.setPen(QColor(color))
        font = theme.ui_font(9, 600)
        painter.setFont(font)
        painter.drawText(
            QRectF(23, 4, self.width() - 28, 22),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self.LABELS[self._state],
        )


class SegmentedControl(QFrame):
    changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("inset")
        self._buttons: dict[str, QPushButton] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(3, 3, 3, 3)
        self._layout.setSpacing(2)
        self.setFixedHeight(36)

    def add_item(self, key: str, label: str) -> None:
        button = QPushButton(label)
        button.setObjectName("segment")
        button.setCheckable(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedHeight(28)
        button.clicked.connect(lambda _checked=False, k=key: self._select(k))
        self._group.addButton(button)
        self._layout.addWidget(button)
        self._buttons[key] = button

    def set_current(self, key: str, emit: bool = False) -> None:
        button = self._buttons.get(key)
        if button is None:
            return
        button.setChecked(True)
        if emit:
            self.changed.emit(key)

    def _select(self, key: str) -> None:
        if self._buttons[key].isChecked():
            self.changed.emit(key)


class RingChart(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._apps: list[AppUsage] = []
        self._app_count = 0
        self._total = 0
        self.setMinimumSize(120, 120)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedSize(132, 132)

    def set_data(self, apps: Sequence[AppUsage], total: int | None = None) -> None:
        self._apps = list(apps[:5])
        self._app_count = len(apps)
        self._total = int(total if total is not None else sum(a.seconds for a in apps))
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        side = min(self.width(), self.height())
        thickness = max(8.0, side * 0.10)
        rect = QRectF(
            (self.width() - side) / 2 + thickness / 2 + 2,
            (self.height() - side) / 2 + thickness / 2 + 2,
            side - thickness - 4,
            side - thickness - 4,
        )

        track = QPen(QColor(theme.BORDER), thickness)
        track.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(rect)

        if self._total > 0:
            start = 90 * 16
            segments: list[tuple[int, str]] = []
            for app in self._apps:
                segments.append((app.seconds, icons.app_color(app.key)))
            rest = self._total - sum(seconds for seconds, _ in segments)
            if rest > 0:
                segments.append((rest, "#3A4355"))
            for seconds, color in segments:
                span = -int(round(360 * 16 * seconds / self._total))
                if span == 0:
                    continue
                pen = QPen(QColor(color), thickness)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                painter.drawArc(rect, start, span)
                start += span

        painter.setPen(QColor(theme.TEXT))
        font = theme.number_font(17, 700)
        painter.setFont(font)
        count = self._app_count if self._total > 0 else 0
        painter.drawText(
            QRectF(0, self.height() / 2 - 19, self.width(), 24),
            Qt.AlignmentFlag.AlignCenter,
            str(count) if count else "—",
        )
        painter.setPen(QColor(theme.FAINT))
        painter.setFont(theme.ui_font(8))
        painter.drawText(
            QRectF(0, self.height() / 2 + 4, self.width(), 18),
            Qt.AlignmentFlag.AlignCenter,
            "个应用" if count else "暂无数据",
        )


class BarChart(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._values: list[int] = []
        self._labels: list[str] = []
        self._highlight = -1
        self._label_step = 4
        self._hover = -1
        self.setMouseTracking(True)
        self.setMinimumHeight(135)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_data(
        self,
        values: Sequence[int],
        labels: Sequence[str] | None = None,
        highlight: int = -1,
        label_step: int | None = None,
    ) -> None:
        self._values = [max(0, int(v)) for v in values]
        self._labels = list(labels or [str(i) for i in range(len(self._values))])
        self._highlight = highlight
        if label_step is not None:
            self._label_step = max(1, int(label_step))
        elif len(self._values) <= 8:
            self._label_step = 1
        elif len(self._values) <= 12:
            self._label_step = 2
        elif len(self._values) <= 24:
            self._label_step = 4
        else:
            self._label_step = 5
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(4, 10, max(1, self.width() - 8), max(1, self.height() - 32))
        grid_pen = QPen(QColor(theme.BORDER_SOFT), 1)
        grid_pen.setStyle(Qt.PenStyle.DashLine)
        for i in range(4):
            y = rect.top() + rect.height() * i / 3
            painter.setPen(grid_pen)
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))

        if not self._values:
            painter.setPen(QColor(theme.FAINT))
            painter.setFont(theme.ui_font(9))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "暂无活动数据")
            return

        max_value = max(self._values)
        if max_value <= 0:
            painter.setPen(QColor(theme.FAINT))
            painter.setFont(theme.ui_font(9))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "暂无活动数据")
            painter.setFont(theme.ui_font(8))
            self._draw_labels(painter, rect)
            return

        count = len(self._values)
        slot = rect.width() / count
        bar_width = min(20.0, max(4.0, slot * 0.54))
        if count <= 8:
            bar_width = min(44.0, max(12.0, slot * 0.55))

        painter.setFont(theme.ui_font(8))
        painter.setPen(QColor(theme.FAINT))
        painter.drawText(
            QRectF(rect.right() - 78, 0, 78, 14),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            format_duration_tight(max_value),
        )

        for index, value in enumerate(self._values):
            cx = rect.left() + slot * (index + 0.5)
            height = rect.height() * value / max_value
            if value > 0:
                height = max(3.0, height)
            bar_rect = QRectF(cx - bar_width / 2, rect.bottom() - height, bar_width, height)
            if value <= 0:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(theme.BORDER_SOFT))
                painter.drawRoundedRect(
                    QRectF(cx - bar_width / 2, rect.bottom() - 2, bar_width, 2), 1, 1
                )
                continue

            if index == self._hover:
                color = QColor(theme.ACCENT_SOFT)
                alpha = 245
            elif index == self._highlight:
                color = QColor(theme.ACCENT)
                alpha = 245
            else:
                color = QColor(theme.ACCENT)
                alpha = 115

            gradient = QLinearGradient(0, bar_rect.top(), 0, bar_rect.bottom())
            top = QColor(color)
            top.setAlpha(alpha)
            bottom = QColor(color)
            bottom.setAlpha(max(32, alpha - 38))
            gradient.setColorAt(0, top)
            gradient.setColorAt(1, bottom)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(gradient)
            painter.drawRoundedRect(bar_rect, 4, 4)

            if index == self._highlight:
                painter.setBrush(QColor(theme.ACCENT))
                painter.drawEllipse(QPointF(cx, rect.bottom() + 12), 2.3, 2.3)

        self._draw_labels(painter, rect)

    def _draw_labels(self, painter: QPainter, rect: QRectF) -> None:
        count = len(self._labels)
        if not count:
            return
        slot = rect.width() / max(1, len(self._values))
        font = theme.ui_font(8)
        painter.setFont(font)
        painter.setPen(QColor(theme.FAINT))
        for index, label in enumerate(self._labels):
            if index % self._label_step != 0 and index != count - 1:
                continue
            cx = rect.left() + slot * (index + 0.5)
            painter.drawText(
                QRectF(cx - 24, rect.bottom() + 7, 48, 16),
                Qt.AlignmentFlag.AlignCenter,
                label,
            )

    def mouseMoveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if not self._values:
            return
        x = event.position().x()
        rect = QRectF(4, 10, max(1, self.width() - 8), max(1, self.height() - 32))
        slot = rect.width() / len(self._values)
        index = int((x - rect.left()) // slot) if slot else -1
        if 0 <= index < len(self._values) and index != self._hover:
            self._hover = index
            self.update()
            label = self._labels[index] if index < len(self._labels) else str(index)
            QToolTip.showText(
                event.globalPosition().toPoint(),
                f"{label} · {format_duration(self._values[index])}",
                self,
            )
        elif not (0 <= index < len(self._values)) and self._hover != -1:
            self._hover = -1
            self.update()

    def leaveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._hover = -1
        self.update()
        super().leaveEvent(event)


def share_color(item: ShareSlice) -> str:
    return OTHER_COLOR if item.is_other else icons.app_color(item.key)


class SharePie(QWidget):
    """Donut chart of per-app time share.

    Hovering a wedge lifts it out of the ring, swaps the centre label to that
    wedge's percentage and shows a tooltip with the full duration breakdown.
    """

    hovered = Signal(int)

    RING_SIZE = 156

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._slices: list[ShareSlice] = []
        self._total = 0
        self._days = 1
        self._range_label = "今日"
        self._hover = -1
        self._tooltip_at: QPoint | None = None
        self.setMouseTracking(True)
        self.setFixedSize(self.RING_SIZE, self.RING_SIZE)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    # ----------------------------------------------------------- data + state

    def set_slices(
        self,
        slices: Sequence[ShareSlice],
        total: int,
        days: int = 1,
        range_label: str = "今日",
    ) -> None:
        hovered_key = (
            self._slices[self._hover].key if 0 <= self._hover < len(self._slices) else None
        )
        self._slices = list(slices)
        self._total = max(0, int(total))
        self._days = max(1, int(days))
        self._range_label = range_label
        self._hover = next(
            (index for index, item in enumerate(self._slices) if item.key == hovered_key),
            -1,
        )
        self.update()

    def set_hover(self, index: int) -> None:
        index = index if 0 <= index < len(self._slices) else -1
        if index != self._hover:
            self._hover = index
            self.update()

    # ---------------------------------------------------------------- painting

    def _geometry(self) -> tuple[QPointF, float, float, QRectF]:
        side = float(min(self.width(), self.height()))
        center = QPointF(self.width() / 2.0, self.height() / 2.0)
        radius = max(24.0, side / 2.0 - 8.0)
        thickness = max(14.0, min(34.0, radius * 0.33))
        ring = QRectF(
            center.x() - radius + thickness / 2.0,
            center.y() - radius + thickness / 2.0,
            2.0 * (radius - thickness / 2.0),
            2.0 * (radius - thickness / 2.0),
        )
        return center, radius, thickness, ring

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        _center, _radius, thickness, ring = self._geometry()

        track = QPen(QColor(theme.BORDER_SOFT), thickness)
        track.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(track)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(ring)

        if self._total <= 0 or not self._slices:
            self._draw_center(painter, "—", "暂无记录")
            return

        start = 90 * 16
        for index, item in enumerate(self._slices):
            span = -int(round(360 * 16 * item.seconds / self._total))
            if span == 0:
                continue
            hovered = index == self._hover
            color = QColor(share_color(item))
            arc_rect = QRectF(ring)
            if hovered:
                mid = math.radians((start + span / 2) / 16.0)
                arc_rect.translate(math.cos(mid) * 4.0, -math.sin(mid) * 4.0)
            elif self._hover != -1:
                color.setAlpha(140)
            pen = QPen(color, thickness + (2.0 if hovered else 0.0))
            pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            inset = 0 if abs(span) < 16 * 8 else int(16 * 0.8)
            painter.drawArc(arc_rect, start + inset // 2, span + inset)
            start += span

        if 0 <= self._hover < len(self._slices):
            percent = self._slices[self._hover].seconds / self._total * 100.0
            self._draw_center(painter, format_percent(percent), "占比")
        else:
            self._draw_center(painter, format_duration_tight(self._total), "合计")

    def _draw_center(self, painter: QPainter, value: str, caption: str) -> None:
        _center, _radius, thickness, ring = self._geometry()
        room = max(28.0, ring.width() - thickness - 10.0)
        size = 15
        font = theme.number_font(size, 700)
        while size > 11 and QFontMetrics(font).horizontalAdvance(value) > room:
            size -= 1
            font = theme.number_font(size, 700)
        painter.setPen(QColor(theme.TEXT))
        painter.setFont(font)
        painter.drawText(
            QRectF(0, self.height() / 2 - 19, self.width(), 23),
            Qt.AlignmentFlag.AlignCenter,
            value,
        )
        painter.setPen(QColor(theme.FAINT))
        painter.setFont(theme.ui_font(8))
        painter.drawText(
            QRectF(0, self.height() / 2 + 3, self.width(), 16),
            Qt.AlignmentFlag.AlignCenter,
            caption,
        )

    # ------------------------------------------------------------------ hover

    def _index_at(self, point: QPointF) -> int:
        center, radius, thickness, _ring = self._geometry()
        dx = point.x() - center.x()
        dy = point.y() - center.y()
        distance = math.hypot(dx, dy)
        if distance < radius - thickness - 8 or distance > radius + 10:
            return -1
        if self._total <= 0:
            return -1
        clockwise = (90.0 - math.degrees(math.atan2(-dy, dx))) % 360.0
        walked = 0.0
        for index, item in enumerate(self._slices):
            share = 360.0 * item.seconds / self._total
            if clockwise < walked + share:
                return index
            walked += share
        return -1

    def tooltip_html(self, index: int) -> str:
        item = self._slices[index]
        percent = item.seconds / self._total * 100.0 if self._total else 0.0
        rows = [
            f"<span style='color:{theme.TEXT};font-weight:600'>{escape(item.name)}</span>",
            f"<span style='color:{theme.MUTED}'>{self._range_label} "
            f"{format_duration(item.seconds)}</span>"
            f" · <span style='color:{share_color(item)}'>{format_percent(percent)}</span>",
        ]
        if item.is_other:
            rows.append(
                f"<span style='color:{theme.FAINT}'>{item.apps} 个应用合并计算</span>"
            )
        if self._days > 1 and item.seconds > 0:
            rows.append(
                f"<span style='color:{theme.FAINT}'>平均每天 "
                f"{format_duration(item.seconds / self._days)}</span>"
            )
        return (
            "<div style='white-space:nowrap'>" + "<br/>".join(rows) + "</div>"
        )

    def _show_tooltip(self, index: int, point: QPoint) -> None:
        self._tooltip_at = point
        QToolTip.showText(point + QPoint(14, 18), self.tooltip_html(index), self)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        index = self._index_at(event.position())
        point = event.globalPosition().toPoint()
        if index != self._hover:
            self._hover = index
            self.update()
            self.hovered.emit(index)
            if index < 0:
                QToolTip.hideText()
            else:
                self._show_tooltip(index, point)
        elif index >= 0 and self._tooltip_at is not None:
            if (point - self._tooltip_at).manhattanLength() > 10:
                self._show_tooltip(index, point)

    def leaveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._tooltip_at = None
        if self._hover != -1:
            self._hover = -1
            self.update()
            self.hovered.emit(-1)
        QToolTip.hideText()
        super().leaveEvent(event)


class ShareLegend(QWidget):
    """Ranked legend beside the share pie; hovering a row lifts its wedge."""

    hovered = Signal(int)

    ROW = 27

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._slices: list[ShareSlice] = []
        self._total = 0
        self._hover = -1
        self.setMouseTracking(True)
        self.setMinimumHeight(self.ROW * 5)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_slices(self, slices: Sequence[ShareSlice], total: int) -> None:
        hovered_key = (
            self._slices[self._hover].key if 0 <= self._hover < len(self._slices) else None
        )
        self._slices = list(slices)
        self._total = max(0, int(total))
        self._hover = next(
            (index for index, item in enumerate(self._slices) if item.key == hovered_key),
            -1,
        )
        self.update()

    def set_hover(self, index: int) -> None:
        index = index if 0 <= index < len(self._slices) else -1
        if index != self._hover:
            self._hover = index
            self.update()

    def _offset(self) -> float:
        rows = max(1, len(self._slices))
        return max(0.0, (self.height() - rows * self.ROW) / 2.0)

    def _index_at(self, point: QPointF) -> int:
        if not self._slices:
            return -1
        index = int((point.y() - self._offset()) // self.ROW)
        if 0 <= index < len(self._slices) and 0 <= point.y() <= self.height():
            return index
        return -1

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if not self._slices:
            painter.setPen(QColor(theme.FAINT))
            painter.setFont(theme.ui_font(9))
            painter.drawText(
                QRectF(0, 0, self.width(), self.height()),
                Qt.AlignmentFlag.AlignCenter,
                "还没有应用记录",
            )
            return

        width = float(self.width())
        offset = self._offset()
        name_left = 20.0
        percent_width = 46.0
        duration_width = 62.0
        percent_left = width - percent_width - 2.0
        duration_left = percent_left - duration_width
        name_width = max(20.0, duration_left - name_left - 8.0)

        name_font = theme.ui_font(10, 600)
        number_font = theme.number_font(9, 600)
        tiny_font = theme.ui_font(8)
        name_metrics = QFontMetrics(name_font)

        for index, item in enumerate(self._slices):
            top = offset + index * self.ROW
            row = QRectF(0, top + 1, width, self.ROW - 2)
            hovered = index == self._hover
            dimmed = self._hover != -1 and not hovered
            if hovered:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(theme.CARD_HOVER))
                painter.drawRoundedRect(row, 8, 8)

            color = QColor(share_color(item))
            if dimmed:
                color.setAlpha(110)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QPointF(9.0, top + self.ROW / 2.0), 4.0, 4.0)

            painter.setFont(name_font)
            painter.setPen(QColor(theme.TEXT if hovered else theme.MUTED))
            painter.drawText(
                QRectF(name_left, top, name_width, self.ROW),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                name_metrics.elidedText(
                    item.name, Qt.TextElideMode.ElideRight, int(name_width)
                ),
            )

            percent = item.seconds / self._total * 100.0 if self._total else 0.0
            painter.setFont(number_font)
            painter.setPen(QColor(theme.TEXT if hovered else theme.MUTED))
            painter.drawText(
                QRectF(duration_left, top, duration_width - 6.0, self.ROW),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                format_duration_tight(item.seconds),
            )
            painter.setFont(tiny_font)
            painter.setPen(QColor(theme.FAINT))
            painter.drawText(
                QRectF(percent_left, top, percent_width, self.ROW),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                format_percent(percent),
            )

    def mouseMoveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        index = self._index_at(event.position())
        if index != self._hover:
            self._hover = index
            self.update()
            self.hovered.emit(index)

    def leaveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self._hover != -1:
            self._hover = -1
            self.update()
            self.hovered.emit(-1)
        super().leaveEvent(event)


class ShareCard(Card):
    """Dashboard module: share of foreground time per app for the active range."""

    MAX_SLICES = 5

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(210)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 13, 16, 12)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        title = QLabel("应用占比")
        title.setObjectName("sectionTitle")
        self._hint = QLabel("今日 · 悬浮查看详情")
        self._hint.setObjectName("cardHint")
        header.addWidget(title)
        header.addWidget(self._hint)
        header.addStretch(1)
        layout.addLayout(header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(18)
        self._pie = SharePie(self)
        self._legend = ShareLegend(self)
        body.addWidget(self._pie, 0, Qt.AlignmentFlag.AlignTop)
        body.addWidget(self._legend, 1)
        layout.addLayout(body, 1)

        self._pie.hovered.connect(self._legend.set_hover)
        self._legend.hovered.connect(self._pie.set_hover)

    def set_apps(
        self,
        apps: Sequence[AppUsage],
        *,
        range_label: str = "今日",
        days: int = 1,
    ) -> None:
        slices = build_share_slices(apps, self.MAX_SLICES)
        total = sum(int(app.seconds) for app in apps if app.seconds > 0)
        self._hint.setText(f"{range_label} · 悬浮查看详情")
        self._pie.set_slices(slices, total, days, range_label)
        self._legend.set_slices(slices, total)


class AppRow(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(62)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self._fraction = 0.0
        self._bar_color = QColor(theme.ACCENT)
        self._hover = False
        self._key = ""

        self._rank = QLabel("01")
        self._rank.setFixedWidth(23)
        self._rank.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._rank.setStyleSheet(f"color: {theme.FAINT}; font-size: 10px; font-weight: 600;")

        self._icon = QLabel()
        self._icon.setFixedSize(32, 32)
        self._icon.setScaledContents(True)

        self._name = ElidedLabel()
        self._name.setObjectName("appName")
        self._meta = ElidedLabel()
        self._meta.setObjectName("appMeta")

        text_box = QVBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(1)
        text_box.addWidget(self._name)
        text_box.addWidget(self._meta)

        self._duration = QLabel("—")
        self._duration.setObjectName("rowDuration")
        self._duration.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._percent = QLabel("—")
        self._percent.setObjectName("rowPercent")
        self._percent.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(1)
        right.addWidget(self._duration)
        right.addWidget(self._percent)
        right.setAlignment(Qt.AlignmentFlag.AlignRight)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 7, 12, 9)
        layout.setSpacing(9)
        layout.addWidget(self._rank)
        layout.addWidget(self._icon)
        layout.addLayout(text_box, 1)
        layout.addSpacing(4)
        layout.addLayout(right)

        self._icon_provider = icons.IconProvider()

    @property
    def key(self) -> str:
        return self._key

    def set_icon_provider(self, provider: icons.IconProvider) -> None:
        self._icon_provider = provider

    def update_data(self, app: AppUsage, total: int, index: int) -> None:
        self._key = app.key
        self._rank.setText(f"{index + 1:02d}")
        self._rank.setStyleSheet(
            f"color: {theme.ACCENT_SOFT if index < 3 else theme.FAINT}; "
            "font-size: 10px; font-weight: 600;"
        )
        self._icon.setPixmap(
            self._icon_provider.pixmap(app.key, app.name, app.exe_path, 32)
        )
        self._name.setText(app.name)
        self._name.setToolTip(app.name)
        meta = Path(app.exe_path).name if app.exe_path else "本地应用"
        self._meta.setText(meta)
        self._meta.setToolTip(app.exe_path or app.name)
        self._duration.setText(format_duration_tight(app.seconds))
        percent = (app.seconds / total * 100.0) if total > 0 else 0.0
        self._percent.setText(format_percent(percent))
        self._fraction = min(1.0, app.seconds / total) if total > 0 else 0.0
        self._bar_color = QColor(icons.app_color(app.key))
        self.update()

    def enterEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self._hover:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(theme.CARD_HOVER))
            painter.drawRoundedRect(QRectF(2, 1, self.width() - 4, self.height() - 3), 10, 10)

        left = 10 + 23 + 9 + 32 + 9
        right = self.width() - 12
        track = QRectF(left, self.height() - 10, max(1, right - left), 4)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.BORDER_SOFT))
        painter.drawRoundedRect(track, 2, 2)
        if self._fraction > 0:
            fill = QRectF(track.left(), track.top(), max(2.0, track.width() * self._fraction), 4)
            painter.setBrush(self._bar_color)
            painter.drawRoundedRect(fill, 2, 2)


class AppRanking(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: dict[str, AppRow] = {}
        self._provider = icons.IconProvider()
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(1)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        self._rows_layout = QVBoxLayout(container)
        self._rows_layout.setContentsMargins(4, 2, 4, 2)
        self._rows_layout.setSpacing(1)
        self._rows_layout.addStretch(1)
        self._scroll.setWidget(container)
        self._layout.addWidget(self._scroll)

        self._empty = QWidget()
        empty_layout = QVBoxLayout(self._empty)
        empty_layout.setContentsMargins(0, 20, 0, 20)
        empty_layout.setSpacing(10)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label = QLabel()
        icon_label.setPixmap(icons.glyph_pixmap("chart", theme.FAINT, 34, 1.4))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel("还没有应用记录")
        title.setStyleSheet(f"color: {theme.MUTED}; font-size: 13px; font-weight: 600;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint = QLabel("切换到任意应用，几秒后即可看到实时用时")
        hint.setStyleSheet(f"color: {theme.FAINT}; font-size: 11px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(icon_label)
        empty_layout.addWidget(title)
        empty_layout.addWidget(hint)
        self._empty.hide()
        self._rows_layout.insertWidget(0, self._empty, 0)

    def set_apps(self, apps: Sequence[AppUsage]) -> None:
        total = sum(a.seconds for a in apps)
        keys = {a.key for a in apps}

        for key, row in list(self._rows.items()):
            if key not in keys:
                self._rows_layout.removeWidget(row)
                row.deleteLater()
                del self._rows[key]

        if not apps:
            self._empty.show()
            return
        self._empty.hide()

        for index, app in enumerate(apps):
            row = self._rows.get(app.key)
            if row is None:
                row = AppRow()
                row.set_icon_provider(self._provider)
                self._rows[app.key] = row
            row.update_data(app, total, index)
            self._rows_layout.insertWidget(index, row)
            row.show()


class RecentRow(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(40)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self._hover = False
        self._key = ""
        self._provider = icons.IconProvider()

        self._time = QLabel("—")
        self._time.setFixedWidth(43)
        self._time.setStyleSheet(f"color: {theme.FAINT}; font-size: 10px;")
        self._time.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._icon = QLabel()
        self._icon.setFixedSize(22, 22)
        self._icon.setScaledContents(True)

        self._name = ElidedLabel()
        self._name.setStyleSheet(f"color: {theme.TEXT}; font-size: 12px;")

        self._duration = QLabel("—")
        self._duration.setFixedWidth(56)
        self._duration.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._duration.setStyleSheet(f"color: {theme.MUTED}; font-size: 10px;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(8)
        layout.addWidget(self._time)
        layout.addWidget(self._icon)
        layout.addWidget(self._name, 1)
        layout.addWidget(self._duration)

    def set_icon_provider(self, provider: icons.IconProvider) -> None:
        self._provider = provider

    def update_data(self, session: RecentSession, is_today: bool) -> None:
        self._key = f"{session.started_at}|{session.key}"
        try:
            started = datetime.fromisoformat(session.started_at)
        except ValueError:
            started = None
        time_text = started.strftime("%H:%M") if started else "—"
        if not is_today and started is not None:
            time_text = started.strftime("%m/%d")
        self._time.setText(time_text)
        self._icon.setPixmap(
            self._provider.pixmap(session.key, session.name, session.exe_path, 22)
        )
        self._name.setText(session.name)
        self._name.setToolTip(session.title or session.name)
        if session.is_current:
            self._duration.setText("进行中")
            self._duration.setStyleSheet(f"color: {theme.MINT}; font-size: 10px;")
        else:
            self._duration.setText(format_duration_tight(session.seconds))
            self._duration.setStyleSheet(f"color: {theme.MUTED}; font-size: 10px;")
        self.setToolTip(
            f"{session.title or session.name}\n{time_text} · {format_duration(session.seconds)}"
        )

    def enterEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        del event
        if not self._hover:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.CARD_HOVER))
        painter.drawRoundedRect(QRectF(0, 1, self.width(), self.height() - 2), 8, 8)


class RecentList(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: dict[str, RecentRow] = {}
        self._provider = icons.IconProvider()
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(1)
        self._layout.addStretch(1)

        self._empty = QLabel("还没有活动记录")
        self._empty.setStyleSheet(f"color: {theme.FAINT}; font-size: 11px;")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setMinimumHeight(48)
        self._empty.hide()
        self._layout.insertWidget(0, self._empty)

    def set_sessions(self, sessions: Sequence[RecentSession], is_today: bool) -> None:
        visible = list(sessions[:6])
        keys = [f"{s.started_at}|{s.key}" for s in visible]

        for key, row in list(self._rows.items()):
            if key not in keys:
                self._layout.removeWidget(row)
                row.deleteLater()
                del self._rows[key]

        if not visible:
            self._empty.show()
            return
        self._empty.hide()

        for index, session in enumerate(visible):
            key = keys[index]
            row = self._rows.get(key)
            if row is None:
                row = RecentRow()
                row.set_icon_provider(self._provider)
                self._rows[key] = row
            row.update_data(session, is_today)
            self._layout.insertWidget(index, row)
            row.show()


class PulseDot(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(10, 10)
        self.color = QColor(theme.MUTED)
        self.phase = 0.0
        self.animated = False

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = QColor(self.color)
        alpha = 230
        if self.animated:
            alpha = 145 + int(90 * (0.5 + 0.5 * math.sin(self.phase)))
        color.setAlpha(alpha)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(QRectF(1, 1, 8, 8))


class CurrentCard(Card):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(188)
        self._provider = icons.IconProvider()
        self._phase = 0.0
        self._status_color = QColor(theme.MUTED)
        self._pulse = QTimer(self)
        self._pulse.setInterval(60)
        self._pulse.timeout.connect(self._tick_pulse)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(10)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        eyebrow = QLabel("正在使用")
        eyebrow.setObjectName("eyebrow")
        self._state_hint = QLabel("实时采样")
        self._state_hint.setObjectName("cardHint")
        self._state_hint.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(eyebrow)
        top.addStretch(1)
        top.addWidget(self._state_hint)
        outer.addLayout(top)

        main = QHBoxLayout()
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(13)
        self._icon = QLabel()
        self._icon.setFixedSize(54, 54)
        self._icon.setScaledContents(True)
        main.addWidget(self._icon, 0, Qt.AlignmentFlag.AlignVCenter)

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(2)
        self._name = ElidedLabel("等待采样")
        self._name.setStyleSheet(f"color: {theme.TEXT}; font-size: 18px; font-weight: 700;")
        self._title = ElidedLabel("切换到任意应用后开始记录")
        self._title.setStyleSheet(f"color: {theme.MUTED}; font-size: 11px;")
        text.addWidget(self._name)
        text.addWidget(self._title)
        main.addLayout(text, 1)

        timer_box = QVBoxLayout()
        timer_box.setContentsMargins(0, 0, 0, 0)
        timer_box.setSpacing(0)
        self._timer = QLabel("—")
        self._timer.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._timer.setStyleSheet(f"color: {theme.TEXT}; font-size: 24px; font-weight: 700;")
        self._timer_caption = QLabel("本次前台")
        self._timer_caption.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._timer_caption.setStyleSheet(f"color: {theme.FAINT}; font-size: 9px;")
        timer_box.addWidget(self._timer)
        timer_box.addWidget(self._timer_caption)
        main.addLayout(timer_box)
        outer.addLayout(main)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(7)
        self._dot = PulseDot()
        self._status = QLabel("等待窗口")
        self._status.setStyleSheet(f"color: {theme.MUTED}; font-size: 10px;")
        self._since = QLabel("")
        self._since.setStyleSheet(f"color: {theme.FAINT}; font-size: 10px;")
        self._since.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        bottom.addWidget(self._dot)
        bottom.addWidget(self._status)
        bottom.addStretch(1)
        bottom.addWidget(self._since)
        outer.addLayout(bottom)

    def _tick_pulse(self) -> None:
        self._phase += 0.18
        self._dot.phase = self._phase
        self._dot.update()

    def _set_state(self, color: str, text: str, hint: str, pulse: bool = False) -> None:
        self._status_color = QColor(color)
        self._dot.color = QColor(color)
        self._dot.animated = pulse
        self._status.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: 500;")
        self._status.setText(text)
        self._state_hint.setText(hint)
        if pulse and not self._pulse.isActive():
            self._pulse.start()
        elif not pulse:
            self._pulse.stop()
        self._dot.update()

    def update_snapshot(self, snapshot: Snapshot) -> None:
        state = snapshot.state
        if state == "active" and snapshot.current_name:
            self._icon.setPixmap(
                self._provider.pixmap(
                    snapshot.current_key,
                    snapshot.current_name,
                    snapshot.current_exe,
                    54,
                )
            )
            self._name.setText(snapshot.current_name)
            self._title.setText(snapshot.current_title or "窗口标题不可用")
            self._timer.setText(format_clock(snapshot.current_seconds))
            self._timer_caption.setText("本次前台")
            self._set_state(theme.MINT, "前台活跃 · 正在计时", "实时采样", pulse=True)
            self._since.setText(
                f"自 {datetime.fromisoformat(snapshot.current_started):%H:%M} 起"
                if snapshot.current_started
                else ""
            )
            return

        self._timer.setText("—")
        self._timer_caption.setText("本次前台")
        self._since.setText("")
        if snapshot.paused or state == "paused":
            self._icon.setPixmap(icons.badge_pixmap("play", theme.AMBER, 54))
            self._name.setText("已暂停记录")
            self._title.setText("点击右上角「继续记录」恢复统计")
            self._set_state(theme.AMBER, "暂停中 · 不计时", "已暂停")
        elif state == "idle":
            self._icon.setPixmap(icons.badge_pixmap("moon", theme.MUTED, 54))
            self._name.setText("当前空闲")
            self._title.setText(f"已 {format_duration(snapshot.idle_seconds)} 无输入，暂停计时")
            self._set_state(theme.MUTED, "空闲中 · 不计时", "空闲检测")
        elif state == "self":
            self._icon.setPixmap(icons.app_pixmap(54))
            self._name.setText("时迹")
            self._title.setText("你正在查看统计面板")
            self._set_state(theme.ACCENT, "此窗口不计入统计", "查看面板")
        elif state == "excluded":
            self._icon.setPixmap(icons.badge_pixmap("moon", theme.FAINT, 54))
            self._name.setText("系统界面")
            self._title.setText("锁屏、登录界面不会被计入")
            self._set_state(theme.FAINT, "未记录", "系统界面")
        else:
            self._icon.setPixmap(icons.badge_pixmap("clock", theme.MUTED, 54))
            self._name.setText("等待前台窗口")
            self._title.setText("切换到任意应用后开始记录")
            self._set_state(theme.MUTED, "等待窗口", "采样中")


class TotalCard(Card):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(188)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 16, 18, 16)
        layout.setSpacing(12)

        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(3)
        self._label = QLabel("今日活跃")
        self._label.setObjectName("eyebrow")
        self._value = QLabel("0 秒")
        self._value.setObjectName("heroValue")
        self._value.setMinimumWidth(230)
        self._sub = QLabel("还没有记录")
        self._sub.setObjectName("muted")
        left.addWidget(self._label)
        left.addWidget(self._value)
        left.addWidget(self._sub)
        left.addStretch(1)
        layout.addLayout(left, 1)

        self._ring = RingChart()
        layout.addWidget(self._ring, 0, Qt.AlignmentFlag.AlignVCenter)

    def update_data(
        self,
        label: str,
        total: int,
        apps: Sequence[AppUsage],
        subtitle: str,
    ) -> None:
        self._label.setText(label)
        self._value.setText(format_duration(total) if total > 0 else "0 秒")
        self._sub.setText(subtitle)
        self._ring.set_data(apps, total)


class Switch(QAbstractButton):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(40, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self) -> QSize:
        return QSize(40, 22)

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        track = QRectF(0.5, 1.5, 39, 19)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.ACCENT if self.isChecked() else "#2B3446"))
        painter.drawRoundedRect(track, 9.5, 9.5)
        x = 22 if self.isChecked() else 3
        painter.setBrush(QColor("#FFFFFF" if self.isChecked() else "#9AA4B8"))
        painter.drawEllipse(QRectF(x, 4, 14, 14))


class EmptyState(QWidget):
    def __init__(self, title: str, hint: str, glyph: str = "chart", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 14, 0, 14)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon = QLabel()
        icon.setPixmap(icons.glyph_pixmap(glyph, theme.FAINT, 30, 1.4))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label = QLabel(title)
        label.setStyleSheet(f"color: {theme.MUTED}; font-size: 12px; font-weight: 600;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub = QLabel(hint)
        sub.setStyleSheet(f"color: {theme.FAINT}; font-size: 10px;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)
        layout.addWidget(label)
        layout.addWidget(sub)
