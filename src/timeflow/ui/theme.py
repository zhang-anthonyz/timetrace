"""Visual language for 时迹 / TimeTrace."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QFontDatabase

BG = "#0A0D13"
BG_SOFT = "#0E121A"
PANEL = "#121722"
CARD = "#151A25"
CARD_HOVER = "#1B2230"
BORDER = "#242B39"
BORDER_SOFT = "#1E2531"
TEXT = "#EDF1F8"
MUTED = "#8B95A9"
FAINT = "#5E687C"
ACCENT = "#6D8BFF"
ACCENT_SOFT = "#94A9FF"
MINT = "#3DD9A0"
AMBER = "#F5B971"
RED = "#FF7188"

APP_PALETTE = [
    "#6D8BFF",
    "#3DD9A0",
    "#F5B971",
    "#FF7E9D",
    "#9B8CFF",
    "#45C8DC",
    "#E6C45A",
    "#9DDF72",
    "#C58BFF",
    "#FF9F6E",
]


def qcolor(hex_value: str, alpha: int = 255) -> QColor:
    color = QColor(hex_value)
    color.setAlpha(alpha)
    return color


def font_family() -> str:
    families = set(QFontDatabase.families())
    for name in (
        "Microsoft YaHei UI",
        "Microsoft YaHei",
        "Segoe UI Variable Text",
        "Segoe UI",
    ):
        if name in families:
            return name
    return QFont().family()


def ui_font(size: int = 10, weight: int = 400) -> QFont:
    font = QFont(font_family())
    font.setPointSize(size)
    font.setWeight(QFont.Weight(weight))
    return font


def number_font(size: int = 24, weight: int = 700) -> QFont:
    families = set(QFontDatabase.families())
    family = "Segoe UI Variable Display" if "Segoe UI Variable Display" in families else "Segoe UI"
    font = QFont(family)
    font.setPointSize(size)
    font.setWeight(QFont.Weight(weight))
    return font


def stylesheet() -> str:
    return f"""
    QWidget {{
        color: {TEXT};
        font-family: "{font_family()}";
        font-size: 13px;
    }}
    QMainWindow, QDialog, QWidget#root {{
        background: {BG};
    }}
    QFrame#card {{
        background: {CARD};
        border: 1px solid {BORDER};
        border-radius: 18px;
    }}
    QFrame#cardAlt {{
        background: {CARD};
        border: 1px solid {BORDER_SOFT};
        border-radius: 16px;
    }}
    QFrame#inset {{
        background: {PANEL};
        border: 1px solid {BORDER_SOFT};
        border-radius: 12px;
    }}
    QLabel {{
        background: transparent;
        border: none;
    }}
    QLabel#eyebrow {{
        color: {MUTED};
        font-size: 12px;
        font-weight: 500;
    }}
    QLabel#sectionTitle {{
        color: {TEXT};
        font-size: 16px;
        font-weight: 600;
    }}
    QLabel#cardHint {{
        color: {FAINT};
        font-size: 11px;
    }}
    QLabel#muted {{
        color: {MUTED};
        font-size: 12px;
    }}
    QLabel#faint {{
        color: {FAINT};
        font-size: 11px;
    }}
    QLabel#heroValue {{
        color: {TEXT};
        font-size: 38px;
        font-weight: 700;
    }}
    QLabel#appName {{
        color: {TEXT};
        font-size: 13px;
        font-weight: 600;
    }}
    QLabel#appMeta {{
        color: {FAINT};
        font-size: 11px;
    }}
    QLabel#rowDuration {{
        color: {TEXT};
        font-size: 12px;
        font-weight: 600;
    }}
    QLabel#rowPercent {{
        color: {FAINT};
        font-size: 11px;
    }}
    QPushButton {{
        background: transparent;
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 10px;
        padding: 7px 12px;
    }}
    QPushButton:hover {{
        background: {CARD_HOVER};
        border-color: #333C4F;
    }}
    QPushButton:pressed {{
        background: #111722;
    }}
    QPushButton#primary {{
        background: {ACCENT};
        color: #0B1020;
        border: none;
        font-weight: 700;
    }}
    QPushButton#primary:hover {{
        background: {ACCENT_SOFT};
    }}
    QPushButton#ghost {{
        background: transparent;
        border: 1px solid {BORDER};
        color: {MUTED};
    }}
    QPushButton#ghost:hover {{
        color: {TEXT};
        background: {CARD_HOVER};
    }}
    QPushButton#danger {{
        background: rgba(255, 113, 136, 0.10);
        border: 1px solid rgba(255, 113, 136, 0.35);
        color: {RED};
    }}
    QPushButton#danger:hover {{
        background: rgba(255, 113, 136, 0.18);
    }}
    QPushButton#pauseButton {{
        background: {CARD};
        border: 1px solid {BORDER};
        border-radius: 11px;
        padding: 8px 14px;
        color: {MUTED};
        font-weight: 500;
    }}
    QPushButton#pauseButton:hover {{
        color: {TEXT};
        border-color: #3A455B;
    }}
    QPushButton#iconButton {{
        background: {CARD};
        border: 1px solid {BORDER};
        border-radius: 11px;
        padding: 0;
    }}
    QPushButton#iconButton:hover {{
        background: {CARD_HOVER};
        border-color: #3A455B;
    }}
    QPushButton#segment {{
        background: transparent;
        border: none;
        border-radius: 8px;
        padding: 6px 14px;
        color: {MUTED};
        font-size: 12px;
    }}
    QPushButton#segment:hover {{
        color: {TEXT};
    }}
    QPushButton#segment:checked {{
        background: #26304A;
        color: {TEXT};
        font-weight: 600;
    }}
    QScrollArea {{
        border: none;
        background: transparent;
    }}
    QScrollArea > QWidget > QWidget {{
        background: transparent;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 2px 0;
    }}
    QScrollBar::handle:vertical {{
        background: #2B3446;
        border-radius: 4px;
        min-height: 28px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: #3B465C;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
    }}
    QToolTip {{
        background: #1B2230;
        color: {TEXT};
        border: 1px solid #33405A;
        border-radius: 7px;
        padding: 6px 8px;
        font-size: 12px;
    }}
    QComboBox {{
        background: {PANEL};
        border: 1px solid {BORDER};
        border-radius: 9px;
        padding: 7px 11px;
        min-width: 160px;
        color: {TEXT};
    }}
    QComboBox:hover {{
        border-color: #3A455B;
    }}
    QComboBox QAbstractItemView {{
        background: {CARD};
        border: 1px solid {BORDER};
        selection-background-color: #26304A;
        outline: none;
        padding: 4px;
    }}
    QCheckBox {{
        color: {TEXT};
        spacing: 9px;
        font-size: 13px;
    }}
    QCheckBox::indicator {{
        width: 17px;
        height: 17px;
        border-radius: 5px;
        border: 1px solid #3A455B;
        background: {PANEL};
    }}
    QCheckBox::indicator:checked {{
        background: {ACCENT};
        border-color: {ACCENT};
    }}
    QLineEdit {{
        background: {PANEL};
        border: 1px solid {BORDER};
        border-radius: 9px;
        padding: 7px 10px;
        color: {MUTED};
        selection-background-color: #334061;
    }}
    QMenu {{
        background: {CARD};
        border: 1px solid {BORDER};
        border-radius: 10px;
        padding: 6px;
    }}
    QMenu::item {{
        padding: 8px 26px 8px 12px;
        border-radius: 7px;
        color: {TEXT};
    }}
    QMenu::item:selected {{
        background: #26304A;
    }}
    QMenu::separator {{
        height: 1px;
        background: {BORDER};
        margin: 5px 8px;
    }}
    QMenu::item:disabled {{
        color: {FAINT};
    }}
    QMessageBox {{
        background: {BG};
    }}
    QMessageBox QLabel {{
        color: {TEXT};
    }}
    """
