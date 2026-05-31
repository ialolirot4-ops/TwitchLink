from Core import App
from Services.Twitch.Authentication.OAuth.OAuthToken import OAuthToken
from Services.Twitch.GQL import TwitchGQLModels
from AppData.EncoderDecoder import Serializable

from PyQt6 import QtCore

import typing


class TwitchAccount(QtCore.QObject, Serializable):
    SERIALIZABLE_INIT_MODEL = False
    SERIALIZABLE_STRICT_MODE = False

    # Warn when the token will expire within this many days
    EXPIRY_WARNING_DAYS = 7
    # Re-check every hour (ms)
    _EXPIRY_CHECK_INTERVAL_MS = 3_600_000

    accountUpdated = QtCore.pyqtSignal()
    authorizationExpired = QtCore.pyqtSignal()
    expiryWarning = QtCore.pyqtSignal(int)  # days remaining until expiry

    def __init__(self, parent: QtCore.QObject | None = None):
        super().__init__(parent=parent)
        self.clearData()
        self._lastWarnDate: QtCore.QDate | None = None
        # Periodic proactive expiry check
        self._expiryTimer = QtCore.QTimer(self)
        self._expiryTimer.setInterval(self._EXPIRY_CHECK_INTERVAL_MS)
        self._expiryTimer.timeout.connect(self._checkExpiry)
        self._expiryTimer.start()
        # Also run once shortly after startup (account may already be loaded)
        QtCore.QTimer.singleShot(15_000, self._checkExpiry)

    def signIn(self, user: TwitchGQLModels.User, token: str, expiration: int | None = None) -> None:
        if self.isSignedIn():
            self.signOut()
        self.user = user
        self.oAuthToken = OAuthToken(token, expiration)
        self.updateIntegrityToken()
        self._lastWarnDate = None   # reset so we warn again on new sign-in
        self.accountUpdated.emit()
        # Proactive check right after sign-in so the user knows immediately
        QtCore.QTimer.singleShot(1_000, self._checkExpiry)

    def signOut(self) -> None:
        self.clearData()
        self.updateIntegrityToken()
        self.accountUpdated.emit()

    def invalidate(self) -> None:
        self.signOut()
        self.authorizationExpired.emit()

    def setData(self, user: TwitchGQLModels.User | None, oAuthToken: OAuthToken | None) -> None:
        self.user = user
        self.oAuthToken = oAuthToken

    def getData(self) -> tuple[TwitchGQLModels.User, OAuthToken]:
        return self.user, self.oAuthToken

    def clearData(self) -> None:
        self.user = None
        self.oAuthToken = None

    def isSignedIn(self) -> bool:
        return self.user != None

    def validateOAuthToken(self) -> None:
        if self.isSignedIn():
            try:
                self.oAuthToken.validate()
            except:
                self.invalidate()

    def getOAuthToken(self) -> str:
        self.validateOAuthToken()
        if self.oAuthToken == None:
            return ""
        else:
            return self.oAuthToken.value

    def updateIntegrityToken(self) -> None:
        App.TwitchIntegrityGenerator.updateIntegrity(forceUpdate=True)

    def getIntegrityToken(self, callback: typing.Callable) -> None:
        App.TwitchIntegrityGenerator.getIntegrity(callback)

    # ------------------------------------------------------------------
    # Proactive expiry check
    # ------------------------------------------------------------------

    def _checkExpiry(self) -> None:
        """Emit expiryWarning once per day when token is near expiration."""
        if not self.isSignedIn() or self.oAuthToken is None:
            return
        if self.oAuthToken.expiration is None:
            return   # No expiry information stored for this token
        if self.oAuthToken.isExpired():
            return   # Already expired — reactive path (validateOAuthToken) handles this

        secsLeft = QtCore.QDateTime.currentDateTimeUtc().secsTo(self.oAuthToken.expiration)
        daysLeft  = max(0, int(secsLeft // 86400))

        if daysLeft > self.EXPIRY_WARNING_DAYS:
            return

        # Warn at most once per calendar day to avoid notification spam
        today = QtCore.QDate.currentDate()
        if self._lastWarnDate == today:
            return

        self._lastWarnDate = today
        self.expiryWarning.emit(daysLeft)