from Services.Image.Presets import Icons

from PyQt6 import QtCore, QtGui, QtWidgets

import typing


class Notification(QtCore.QObject):
    class Icons:
        Information = QtWidgets.QSystemTrayIcon.MessageIcon.Information
        Warning = QtWidgets.QSystemTrayIcon.MessageIcon.Warning
        Critical = QtWidgets.QSystemTrayIcon.MessageIcon.Critical

    def __init__(self, systemTrayIcon: QtWidgets.QSystemTrayIcon, parent: QtCore.QObject | None = None):
        super().__init__(parent=parent)
        self.systemTrayIcon = systemTrayIcon
        # Action to execute when the user clicks a toast notification.
        # Stored here because QSystemTrayIcon.messageClicked carries no payload.
        self._pendingAction: typing.Callable | None = None
        self.systemTrayIcon.messageClicked.connect(self._onMessageClicked)

    def toastMessage(
        self,
        title: str,
        message: str,
        icon: QtWidgets.QSystemTrayIcon.MessageIcon | QtGui.QIcon | None = None,
        action: typing.Callable | None = None,
    ) -> None:
        """Show a Windows toast notification.

        Args:
            title:   Bold heading of the notification bubble.
            message: Body text.
            icon:    Optional icon override.
            action:  Zero-argument callable executed when the user clicks the
                     notification. If None, clicking only brings the main
                     window to the front (existing behaviour).
        """
        self._pendingAction = action
        self.systemTrayIcon.showMessage(title, message, icon or Icons.APP_LOGO.icon)

    def _onMessageClicked(self) -> None:
        """Called when the user clicks a toast notification bubble."""
        if self._pendingAction is not None:
            try:
                self._pendingAction()
            except Exception:
                pass
            finally:
                self._pendingAction = None