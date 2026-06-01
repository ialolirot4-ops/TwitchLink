from .Palette import Palette
from .ThemedIconManager import ThemedIconManager

from Core import App
from Services.Utils.OSUtils import OSUtils

from PyQt6 import QtCore, QtGui

import typing
import enum


# ── Hojas de estilo globales ───────────────────────────────────────────────

_QSS_COMMON = """
/* ── Scrollbars: delgadas y modernas ─────────────────────────────── */
QScrollBar:vertical {
    background: transparent;
    width: 7px;
    margin: 2px 1px 2px 0px;
    border: none;
}
QScrollBar::handle:vertical {
    border-radius: 3px;
    min-height: 28px;
}
QScrollBar::handle:vertical:hover  { background: rgba(145, 71, 255, 0.70); }
QScrollBar::handle:vertical:pressed{ background: rgba(145, 71, 255, 0.90); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; background: transparent; }
QScrollBar::add-page:vertical,  QScrollBar::sub-page:vertical  { background: transparent; }

QScrollBar:horizontal {
    background: transparent;
    height: 7px;
    margin: 0px 2px 1px 2px;
    border: none;
}
QScrollBar::handle:horizontal {
    border-radius: 3px;
    min-width: 28px;
}
QScrollBar::handle:horizontal:hover  { background: rgba(145, 71, 255, 0.70); }
QScrollBar::handle:horizontal:pressed{ background: rgba(145, 71, 255, 0.90); }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; background: transparent; }
QScrollBar::add-page:horizontal,  QScrollBar::sub-page:horizontal  { background: transparent; }

/* ── Tab bar ──────────────────────────────────────────────────────── */
QTabBar::tab {
    padding: 6px 16px;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:selected {
    font-weight: 600;
    border-bottom: 2px solid rgb(145, 71, 255);
}
"""

_QSS_DARK = """
/* ── Scrollbar handles en dark mode ──────────────────────────────── */
QScrollBar::handle:vertical   { background: rgba(145, 71, 255, 0.32); }
QScrollBar::handle:horizontal { background: rgba(145, 71, 255, 0.32); }

/* ── Focus ring en dark mode ─────────────────────────────────────── */
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border: 1px solid rgba(145, 71, 255, 0.80);
    outline: none;
}
QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid rgba(145, 71, 255, 0.80);
}

/* ── ToolTip en dark ─────────────────────────────────────────────── */
QToolTip {
    background-color: rgb(52, 50, 72);
    color: rgb(218, 214, 238);
    border: 1px solid rgba(145, 71, 255, 0.45);
    border-radius: 5px;
    padding: 4px 8px;
}
"""

_QSS_LIGHT = """
/* ── Scrollbar handles en light mode ─────────────────────────────── */
QScrollBar::handle:vertical   { background: rgba(145, 71, 255, 0.25); }
QScrollBar::handle:horizontal { background: rgba(145, 71, 255, 0.25); }

/* ── Focus ring en light mode ────────────────────────────────────── */
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border: 1px solid rgba(145, 71, 255, 0.75);
    outline: none;
}
QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid rgba(145, 71, 255, 0.75);
}

/* ── ToolTip en light ────────────────────────────────────────────── */
QToolTip {
    background-color: rgb(250, 248, 255);
    color: rgb(18, 14, 32);
    border: 1px solid rgba(145, 71, 255, 0.35);
    border-radius: 5px;
    padding: 4px 8px;
}
"""


class ThemeManager(QtCore.QObject):
    themeUpdated = QtCore.pyqtSignal()

    class Modes(enum.Enum):
        AUTO = ""
        LIGHT = "light"
        DARK = "dark"

        def isAuto(self) -> bool:
            return self == self.AUTO

        def isLight(self) -> bool:
            return self == self.LIGHT

        def isDark(self) -> bool:
            return self == self.DARK

        def toString(self) -> str:
            return self.value

        @classmethod
        def fromString(cls, value: str) -> typing.Self | None:
            for member in cls:
                if member.value == value:
                    return member
            return None


    def __init__(self, parent: QtCore.QObject | None = None):
        super().__init__(parent=parent)
        self._themeMode: ThemeManager.Modes = self.Modes.AUTO
        App.Instance.styleHints().colorSchemeChanged.connect(self._colorSchemeChanged)

    def getThemeMode(self) -> Modes:
        return self._themeMode

    def setThemeMode(self, themeMode: Modes) -> None:
        self._themeMode = themeMode
        self.updateTheme()

    def isDarkModeEnabled(self) -> bool:
        return self._themeMode.isDark() or (self._themeMode.isAuto() and App.Instance.styleHints().colorScheme() == QtCore.Qt.ColorScheme.Dark)

    def _colorSchemeChanged(self, colorScheme: QtCore.Qt.ColorScheme) -> None:
        self.updateTheme()

    def updateTheme(self) -> None:
        ThemedIconManager.setDarkModeEnabled(self.isDarkModeEnabled())

        # Aplicar paleta
        palette = QtGui.QPalette()
        paletteData = Palette.DARK if self.isDarkModeEnabled() else Palette.LIGHT
        for role, roleData in paletteData.items():
            for group, color in roleData.items():
                palette.setColor(group, role, QtGui.QColor(*color))
        App.Instance.setPalette(palette)

        # Aplicar estilo nativo
        App.Instance.setStyle(OSUtils.getDarkStyle() if self.isDarkModeEnabled() else OSUtils.getLightStyle())

        # Aplicar QSS global
        qss = _QSS_COMMON + (_QSS_DARK if self.isDarkModeEnabled() else _QSS_LIGHT)
        App.Instance.setStyleSheet(qss)

        self.themeUpdated.emit()
