"""Generated iconography — no external image assets required."""

from __future__ import annotations

import hashlib
from pathlib import Path

from PySide6.QtCore import QFileInfo, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QFileIconProvider

from . import theme


def app_pixmap(size: int = 64, paused: bool = False) -> QPixmap:
    scale = max(1, int(size))
    pm = QPixmap(scale, scale)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    rect = QRectF(1, 1, scale - 2, scale - 2)
    path = QPainterPath()
    path.addRoundedRect(rect, scale * 0.27, scale * 0.27)
    gradient = QLinearGradient(0, 0, scale, scale)
    if paused:
        gradient.setColorAt(0, QColor("#5C667B"))
        gradient.setColorAt(1, QColor("#343C4C"))
    else:
        gradient.setColorAt(0, QColor("#7D96FF"))
        gradient.setColorAt(0.55, QColor("#6D8BFF"))
        gradient.setColorAt(1, QColor("#8E6DFF"))
    painter.fillPath(path, gradient)

    # soft top-left highlight
    hi = QPainterPath()
    hi.addEllipse(QRectF(-scale * 0.25, -scale * 0.55, scale * 0.95, scale * 0.8))
    painter.fillPath(hi, QColor(255, 255, 255, 20))

    pen = QPen(QColor(255, 255, 255, 235), max(1.6, scale * 0.075))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    margin = scale * 0.235
    painter.drawEllipse(rect.adjusted(margin, margin, -margin, -margin))

    center = QPointF(scale / 2, scale / 2)
    painter.drawLine(center, QPointF(scale / 2, scale * 0.31))
    painter.drawLine(center, QPointF(scale * 0.665, scale * 0.59))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 255, 255, 245))
    dot = max(1.4, scale * 0.045)
    painter.drawEllipse(center, dot, dot)

    if paused:
        bar_w = max(2.0, scale * 0.07)
        painter.setBrush(QColor(255, 255, 255, 225))
        painter.drawRoundedRect(
            QRectF(scale * 0.38, scale * 0.68, bar_w, scale * 0.16), 1, 1
        )
        painter.drawRoundedRect(
            QRectF(scale * 0.55, scale * 0.68, bar_w, scale * 0.16), 1, 1
        )

    painter.end()
    return pm


def app_icon(paused: bool = False) -> QIcon:
    icon = QIcon()
    for size in (16, 20, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(app_pixmap(size, paused=paused))
    return icon


def glyph_pixmap(name: str, color: str = theme.MUTED, size: int = 18, stroke: float = 1.7) -> QPixmap:
    scale = max(1, int(size))
    pm = QPixmap(scale, scale)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor(color), max(1.2, stroke))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    s = scale
    c = s / 2.0
    if name == "gear":
        painter.drawEllipse(QPointF(c, c), s * 0.14, s * 0.14)
        for i in range(8):
            import math

            angle = math.radians(i * 45)
            x1 = c + math.cos(angle) * s * 0.24
            y1 = c + math.sin(angle) * s * 0.24
            x2 = c + math.cos(angle) * s * 0.34
            y2 = c + math.sin(angle) * s * 0.34
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        painter.drawEllipse(QPointF(c, c), s * 0.30, s * 0.30)
    elif name == "pause":
        painter.setBrush(QColor(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(s * 0.31, s * 0.24, s * 0.11, s * 0.52), 1, 1)
        painter.drawRoundedRect(QRectF(s * 0.58, s * 0.24, s * 0.11, s * 0.52), 1, 1)
    elif name == "play":
        painter.setBrush(QColor(color))
        painter.setPen(Qt.PenStyle.NoPen)
        path = QPainterPath()
        path.moveTo(s * 0.34, s * 0.22)
        path.lineTo(s * 0.78, s * 0.50)
        path.lineTo(s * 0.34, s * 0.78)
        path.closeSubpath()
        painter.drawPath(path)
    elif name == "folder":
        path = QPainterPath()
        path.moveTo(s * 0.16, s * 0.32)
        path.lineTo(s * 0.40, s * 0.32)
        path.lineTo(s * 0.47, s * 0.40)
        path.lineTo(s * 0.84, s * 0.40)
        path.lineTo(s * 0.84, s * 0.76)
        path.lineTo(s * 0.16, s * 0.76)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(QPointF(s * 0.16, s * 0.46), QPointF(s * 0.84, s * 0.46))
    elif name == "export":
        painter.drawLine(QPointF(c, s * 0.62), QPointF(c, s * 0.18))
        painter.drawLine(QPointF(c, s * 0.18), QPointF(s * 0.34, s * 0.36))
        painter.drawLine(QPointF(c, s * 0.18), QPointF(s * 0.66, s * 0.36))
        path = QPainterPath()
        path.moveTo(s * 0.16, s * 0.56)
        path.lineTo(s * 0.16, s * 0.82)
        path.lineTo(s * 0.84, s * 0.82)
        path.lineTo(s * 0.84, s * 0.56)
        painter.drawPath(path)
    elif name == "clock":
        painter.drawEllipse(QPointF(c, c), s * 0.34, s * 0.34)
        painter.drawLine(QPointF(c, c), QPointF(c, s * 0.26))
        painter.drawLine(QPointF(c, c), QPointF(s * 0.67, s * 0.59))
    elif name == "chart":
        painter.drawLine(QPointF(s * 0.18, s * 0.82), QPointF(s * 0.18, s * 0.18))
        painter.drawLine(QPointF(s * 0.18, s * 0.82), QPointF(s * 0.84, s * 0.82))
        painter.setBrush(QColor(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(s * 0.30, s * 0.55, s * 0.11, s * 0.20), 1, 1)
        painter.drawRoundedRect(QRectF(s * 0.48, s * 0.40, s * 0.11, s * 0.35), 1, 1)
        painter.drawRoundedRect(QRectF(s * 0.66, s * 0.26, s * 0.11, s * 0.49), 1, 1)
    elif name == "moon":
        path = QPainterPath()
        path.addEllipse(QRectF(s * 0.18, s * 0.18, s * 0.64, s * 0.64))
        cut = QPainterPath()
        cut.addEllipse(QRectF(s * 0.34, s * 0.06, s * 0.64, s * 0.64))
        painter.drawPath(path.subtracted(cut))
    elif name == "spark":
        path = QPainterPath()
        path.moveTo(c, s * 0.12)
        path.lineTo(s * 0.58, s * 0.42)
        path.lineTo(s * 0.88, c)
        path.lineTo(s * 0.58, s * 0.58)
        path.lineTo(c, s * 0.88)
        path.lineTo(s * 0.42, s * 0.58)
        path.lineTo(s * 0.12, c)
        path.lineTo(s * 0.42, s * 0.42)
        path.closeSubpath()
        painter.drawPath(path)
    elif name == "chevron":
        painter.drawLine(QPointF(s * 0.36, s * 0.30), QPointF(s * 0.62, c))
        painter.drawLine(QPointF(s * 0.62, c), QPointF(s * 0.36, s * 0.70))
    elif name == "check":
        painter.drawLine(QPointF(s * 0.22, s * 0.52), QPointF(s * 0.43, s * 0.72))
        painter.drawLine(QPointF(s * 0.43, s * 0.72), QPointF(s * 0.79, s * 0.30))
    elif name == "close":
        painter.drawLine(QPointF(s * 0.28, s * 0.28), QPointF(s * 0.72, s * 0.72))
        painter.drawLine(QPointF(s * 0.72, s * 0.28), QPointF(s * 0.28, s * 0.72))
    else:
        painter.drawEllipse(QPointF(c, c), s * 0.28, s * 0.28)

    painter.end()
    return pm


def badge_pixmap(name: str, color: str = theme.MUTED, size: int = 54) -> QPixmap:
    """A translucent circular badge containing a line glyph."""
    scale = max(1, int(size))
    pm = QPixmap(scale, scale)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    base = QColor(color)
    fill = QColor(base)
    fill.setAlpha(24)
    border = QColor(base)
    border.setAlpha(58)
    painter.setPen(QPen(border, 1))
    painter.setBrush(fill)
    painter.drawEllipse(QRectF(1, 1, scale - 2, scale - 2))
    glyph_size = max(12, int(scale * 0.50))
    glyph = glyph_pixmap(name, color, glyph_size, stroke=max(1.4, glyph_size * 0.09))
    painter.drawPixmap(
        QPointF((scale - glyph_size) / 2, (scale - glyph_size) / 2),
        glyph,
    )
    painter.end()
    return pm


def glyph_icon(name: str, color: str = theme.MUTED, size: int = 18) -> QIcon:
    icon = QIcon()
    for factor in (1, 2):
        icon.addPixmap(glyph_pixmap(name, color, size * factor, stroke=1.6 * factor))
    return icon


def letter_pixmap(text: str, color: str, size: int = 34) -> QPixmap:
    scale = max(1, int(size))
    pm = QPixmap(scale, scale)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    base = QColor(color)
    bg = QColor(base)
    bg.setAlpha(38)
    border = QColor(base)
    border.setAlpha(75)
    painter.setPen(QPen(border, 1))
    painter.setBrush(bg)
    painter.drawRoundedRect(QRectF(0.5, 0.5, scale - 1, scale - 1), scale * 0.28, scale * 0.28)
    initial = next((ch for ch in (text or "?") if not ch.isspace()), "?")
    font = QFont(theme.font_family())
    font.setPixelSize(max(10, int(scale * 0.44)))
    font.setWeight(QFont.Weight.DemiBold)
    painter.setFont(font)
    painter.setPen(base)
    painter.drawText(QRectF(0, 0, scale, scale), Qt.AlignmentFlag.AlignCenter, initial.upper())
    painter.end()
    return pm


def app_color(key: str) -> str:
    digest = hashlib.md5((key or "unknown").encode("utf-8", "ignore")).digest()
    return theme.APP_PALETTE[digest[0] % len(theme.APP_PALETTE)]


class IconProvider:
    """Cache shell/file icons and letter fallbacks."""

    def __init__(self) -> None:
        self._provider = QFileIconProvider()
        self._cache: dict[tuple[str, int], QPixmap] = {}

    def pixmap(self, key: str, name: str, exe_path: str, size: int = 34) -> QPixmap:
        cache_key = (key, int(size))
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        pixmap: QPixmap | None = None
        if exe_path:
            try:
                path = Path(exe_path)
                if path.is_file():
                    icon = self._provider.icon(QFileInfo(str(path)))
                    if not icon.isNull():
                        pixmap = icon.pixmap(size, size)
                        if pixmap.isNull():
                            pixmap = None
            except Exception:
                pixmap = None

        if pixmap is None:
            pixmap = letter_pixmap(name, app_color(key), size)

        self._cache[cache_key] = pixmap
        return pixmap
