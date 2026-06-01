from Core import App
from Services.Theme.ThemedIcon import ThemedIcon
from Services.Utils.Utils import Utils

from PyQt6 import QtCore, QtGui, QtWidgets


# ── Constantes de estilo ───────────────────────────────────────────────────
_PURPLE       = "rgba(145, 71, 255, 255)"
_PURPLE_HOVER = "rgba(165, 100, 255, 255)"

# Sidebar dark: fondo muy oscuro con tinte purple
_SIDEBAR_DARK  = "rgba(28, 26, 44, 248)"
# Sidebar light: Twitch purple sólido
_SIDEBAR_LIGHT = "rgba(125, 55, 235, 255)"

# Botones dark: sobre fondo oscuro, checked = purple
_BTN_DARK_NORMAL  = "QToolButton {background: transparent; border: none; border-radius: 8px;}"
_BTN_DARK_HOVER   = "QToolButton:hover {background: rgba(145, 71, 255, 0.20);}"
_BTN_DARK_CHECKED = "QToolButton:checked {background: rgba(145, 71, 255, 255);}"
_BTN_DARK         = _BTN_DARK_NORMAL + _BTN_DARK_HOVER + _BTN_DARK_CHECKED

# Botones light: sobre fondo purple, checked = blanco semiopaco
_BTN_LIGHT_NORMAL  = "QToolButton {background: transparent; border: none; border-radius: 8px;}"
_BTN_LIGHT_HOVER   = "QToolButton:hover {background: rgba(255, 255, 255, 0.22);}"
_BTN_LIGHT_CHECKED = "QToolButton:checked {background: rgba(255, 255, 255, 0.95);}"
_BTN_LIGHT         = _BTN_LIGHT_NORMAL + _BTN_LIGHT_HOVER + _BTN_LIGHT_CHECKED


class PageObject(QtCore.QObject):
    showRequested = QtCore.pyqtSignal(object)
    buttonVisibilityChanged = QtCore.pyqtSignal(object, bool)
    blockChanged = QtCore.pyqtSignal(object, bool)
    focusChanged = QtCore.pyqtSignal(object, bool)

    def __init__(self, button: QtWidgets.QToolButton, widget: QtWidgets.QWidget, icon: QtGui.QIcon | ThemedIcon | None = None, parent: QtCore.QObject | None = None):
        super().__init__(parent=parent)
        self.button = button
        self.buttonIconViewer = Utils.setIconViewer(self.button, icon)
        self.widget = widget
        self.hidden = False
        self.blocked = False
        self.focused = False
        self.button.clicked.connect(self.show)
        App.ThemeManager.themeUpdated.connect(self._setupThemeStyle)
        self._setupThemeStyle()

    def _setupThemeStyle(self) -> None:
        if App.ThemeManager.isDarkModeEnabled():
            self.button.setStyleSheet(_BTN_DARK)
        else:
            self.button.setStyleSheet(_BTN_LIGHT)

    def setPageIcon(self, icon: QtGui.QIcon | ThemedIcon | None, size: QtCore.QSize | None = None) -> None:
        self.buttonIconViewer.setIcon(icon)
        self.button.setIconSize(size or QtCore.QSize(24, 24))

    def setPageName(self, name: str) -> None:
        self.button.setText(name)
        if name == "":
            self.button.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
        else:
            self.button.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon)

    def show(self) -> None:
        self.showRequested.emit(self)

    def showButton(self) -> None:
        self.buttonVisibilityChanged.emit(self, True)

    def hideButton(self) -> None:
        self.buttonVisibilityChanged.emit(self, False)

    def block(self) -> None:
        self.blockChanged.emit(self, True)

    def unblock(self) -> None:
        self.blockChanged.emit(self, False)

    def focus(self) -> None:
        self.focusChanged.emit(self, True)

    def unfocus(self) -> None:
        self.focusChanged.emit(self, False)


class NavigationBar(QtCore.QObject):
    focusChanged = QtCore.pyqtSignal(bool)

    def __init__(self, buttonArea: QtWidgets.QWidget, stackedWidget: QtWidgets.QStackedWidget, parent: QtCore.QObject | None = None):
        super().__init__(parent=parent)
        self.buttonArea = buttonArea
        self.stackedWidget = stackedWidget
        self.pages: list[PageObject] = []
        self.currentPage = None
        App.ThemeManager.themeUpdated.connect(self._setupThemeStyle)
        self._setupThemeStyle()

    def _setupThemeStyle(self) -> None:
        if App.ThemeManager.isDarkModeEnabled():
            self.buttonArea.setStyleSheet(
                f"#navigationBar {{ background: {_SIDEBAR_DARK}; }}"
            )
        else:
            self.buttonArea.setStyleSheet(
                f"#navigationBar {{ background: {_SIDEBAR_LIGHT}; }}"
            )

    def setPageButtonVisible(self, pageObject: PageObject, visible: bool) -> None:
        if visible:
            self.showPageButton(pageObject)
        else:
            self.hidePageButton(pageObject)

    def showPageButton(self, pageObject: PageObject) -> None:
        if pageObject.hidden:
            pageObject.hidden = False
            pageObject.button.show()

    def hidePageButton(self, pageObject: PageObject) -> None:
        if not pageObject.hidden:
            pageObject.hidden = True
            pageObject.button.hide()

    def setPageBlockEnabled(self, pageObject: PageObject, enabled: bool) -> None:
        if enabled:
            self.blockPage(pageObject)
        else:
            self.unblockPage(pageObject)

    def blockPage(self, pageObject: PageObject) -> None:
        if not pageObject.blocked:
            pageObject.blocked = True
            self._reload()

    def unblockPage(self, pageObject: PageObject) -> None:
        if pageObject.blocked:
            pageObject.blocked = False
            self._reload()

    def setPageFocusEnabled(self, pageObject: PageObject, enabled: bool) -> None:
        if enabled:
            self.focusPage(pageObject)
        else:
            self.unfocusPage(pageObject)

    def focusPage(self, pageObject: PageObject) -> None:
        if not pageObject.focused:
            hadFocus = self.hasFocus()
            pageObject.focused = True
            self._reload()
            if hadFocus == False:
                self.focusChanged.emit(True)

    def unfocusPage(self, pageObject: PageObject) -> None:
        if pageObject.focused:
            pageObject.focused = False
            self._reload()
            if self.hasFocus() == False:
                self.focusChanged.emit(False)

    def setCurrentPage(self, pageObject: PageObject) -> bool:
        if pageObject in self.getAvailablePages():
            pageObject.button.setChecked(True)
            self.stackedWidget.setCurrentWidget(pageObject.widget)
            self.currentPage = pageObject
            return True
        else:
            return False

    def getCurrentPage(self) -> PageObject:
        return self.currentPage

    def isCurrentPage(self, pageObject: PageObject) -> bool:
        return pageObject == self.getCurrentPage()

    def getBlockedPages(self) -> list[PageObject]:
        return [pageObject for pageObject in self.pages if pageObject.blocked]

    def getFocusedPages(self) -> list[PageObject]:
        return [pageObject for pageObject in self.pages if pageObject.focused]

    def hasFocus(self) -> bool:
        return len(self.getFocusedPages()) != 0

    def getAvailablePages(self) -> list[PageObject]:
        unblockedPages = [pageObject for pageObject in self.pages if not pageObject.blocked]
        return [pageObject for pageObject in unblockedPages if pageObject.focused] or unblockedPages

    def addPage(self, button: QtWidgets.QToolButton, widget: QtWidgets.QWidget, icon: QtGui.QIcon | ThemedIcon | None = None) -> PageObject:
        pageObject = PageObject(button, widget, icon=icon, parent=self)
        pageObject.showRequested.connect(self.setCurrentPage)
        pageObject.buttonVisibilityChanged.connect(self.setPageButtonVisible)
        pageObject.blockChanged.connect(self.setPageBlockEnabled)
        pageObject.focusChanged.connect(self.setPageFocusEnabled)
        self.pages.append(pageObject)
        if self.getCurrentPage() == None:
            self.setCurrentPage(pageObject)
        self._reload()
        return pageObject

    def _reload(self) -> None:
        availablePages = self.getAvailablePages()
        for pageObject in self.pages:
            pageObject.button.setEnabled(pageObject in availablePages)
        if self.getCurrentPage() not in availablePages:
            if len(availablePages) == 0:
                self.currentPage = None
            else:
                self.setCurrentPage(availablePages[0])
