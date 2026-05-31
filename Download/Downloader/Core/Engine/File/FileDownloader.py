from ..Config import Config
from .BandwidthLimiter import BandwidthLimiter

from Core.GlobalExceptions import Exceptions

from PyQt6 import QtCore, QtNetwork


class FileDownloader(QtCore.QObject):
    progressChanged = QtCore.pyqtSignal(object, object)
    errorOccurred = QtCore.pyqtSignal(object)
    finished = QtCore.pyqtSignal(object)
    _startRequested = QtCore.pyqtSignal()
    _abortRequested = QtCore.pyqtSignal(object)
    _retryRequired = QtCore.pyqtSignal(object)
    _retryRequested = QtCore.pyqtSignal(object)

    # Shared limiter — set by FileDownloadManager on startup.
    # None means no limiting (unlimited bandwidth).
    _bandwidthLimiter: BandwidthLimiter | None = None

    def __init__(self, networkAccessManager: QtNetwork.QNetworkAccessManager, url: QtCore.QUrl, filePath: str, priority: int = 0, parent: QtCore.QObject | None = None):
        super().__init__(parent=parent)
        self.url = url
        self.filePath = filePath
        self._priority = priority
        self.file = QtCore.QFile(self.filePath, self)
        self.bytesReceived = 0
        self.bytesTotal = 0
        self._networkAccessManager = networkAccessManager
        self._request = QtNetwork.QNetworkRequest(self.url)
        self._request.setTransferTimeout(Config.FILE_REQUEST_TIMEOUT)
        self._reply: QtNetwork.QNetworkReply | None = None
        self._error: Exceptions.AbortRequested | Exceptions.FileSystemError | Exceptions.NetworkError | None = None
        self._retryScheduled: bool = False
        self._retryCount = 0
        self._finished = False
        self._throttleConnected: bool = False
        self._paused: bool = False   # True while waiting for refilled signal
        self._retryTimer = QtCore.QTimer(parent=self)
        self._retryTimer.setSingleShot(True)
        self._retryTimer.timeout.connect(self._retryTimerTimeout)
        self._startRequested.connect(self._startHandler)
        self._abortRequested.connect(self._abortHandler)

    def getPriority(self) -> int:
        return self._priority * (Config.FILE_REQUEST_MAX_RETRY_COUNT + 1) + self._retryCount

    def start(self) -> None:
        self._startRequested.emit()

    def _startHandler(self) -> None:
        if self._reply == None:
            self._setDownloadProgress(0, 0)
            if not self.file.open(QtCore.QIODevice.OpenModeFlag.WriteOnly):
                self._raiseException(Exceptions.FileSystemError(self.file))
                return
            self._reply = self._networkAccessManager.get(self._request)
            self._reply.readyRead.connect(self._onReadyRead)
            self._reply.downloadProgress.connect(self._setDownloadProgress)
            self._reply.errorOccurred.connect(self._onNetworkError)
            self._reply.finished.connect(self._onFinished)

    def abort(self, reason: str | None = None) -> None:
        self._abortRequested.emit(reason)

    def _abortHandler(self, reason: str | None = None) -> None:
        self._raiseException(Exceptions.AbortRequested(reason))

    def getError(self) -> Exceptions.AbortRequested | Exceptions.FileSystemError | Exceptions.NetworkError | None:
        return self._error

    def _setDownloadProgress(self, bytesReceived: int, bytesTotal: int) -> None:
        self.bytesReceived = bytesReceived
        self.bytesTotal = bytesTotal
        self.progressChanged.emit(self.bytesReceived, self.bytesTotal)

    def pause(self) -> None:
        """Soft-pause: stop consuming bytes from Qt's network buffer.
        TCP back-pressure will naturally slow the sender."""
        self._paused = True

    def resume(self) -> None:
        """Resume consuming buffered data and re-enable readyRead processing."""
        self._paused = False
        if self._reply is not None and self._reply.bytesAvailable() > 0:
            self._onReadyRead()

    def _onReadyRead(self) -> None:
        if self._paused:
            return  # Leave data in Qt's buffer; TCP window will throttle sender
        if self._reply.attribute(QtNetwork.QNetworkRequest.Attribute.HttpStatusCodeAttribute) == 200:
            available = self._reply.bytesAvailable()
            if available <= 0:
                return
            limiter = FileDownloader._bandwidthLimiter
            allowed = limiter.acquire(available) if limiter else available
            if allowed > 0:
                data = self._reply.read(allowed)
                if self.file.write(data) == -1:
                    self._raiseException(Exceptions.FileSystemError(self.file))
            elif not self._throttleConnected and limiter:
                limiter.refilled.connect(self._onThrottleRefill)
                self._throttleConnected = True

    def _onThrottleRefill(self) -> None:
        """Called when the BandwidthLimiter bucket has been refilled."""
        limiter = FileDownloader._bandwidthLimiter
        if limiter and self._throttleConnected:
            limiter.refilled.disconnect(self._onThrottleRefill)
            self._throttleConnected = False
        if self._reply is not None and not self._finished and self._error is None:
            self._onReadyRead()

    def _onFinished(self) -> None:
        # Disconnect throttle listener if still pending
        limiter = FileDownloader._bandwidthLimiter
        if self._throttleConnected and limiter:
            try:
                limiter.refilled.disconnect(self._onThrottleRefill)
            except RuntimeError:
                pass
            self._throttleConnected = False
        self.file.close()
        self._reply = None
        if self._retryScheduled:
            self.file.remove()
        elif self._error == None:
            self._setFinished()

    def _onNetworkError(self, error: QtNetwork.QNetworkReply.NetworkError) -> None:
        self._raiseException(Exceptions.NetworkError(self._reply))

    def _raiseException(self, exception: Exceptions.AbortRequested | Exceptions.FileSystemError | Exceptions.NetworkError) -> None:
        if self._error != None:
            return
        self._error = exception
        if self._reply != None:
            self._reply.abort()
        if self._retryTimer.isActive():
            self._retryTimer.stop()
        if isinstance(exception, Exceptions.NetworkError) and self._retryCount < Config.FILE_REQUEST_MAX_RETRY_COUNT:
            self._retryCount += 1
            self._retryScheduled = True
            self._error = None
            self._retryRequired.emit(self)
            self._retryTimer.start(self._retryCount * Config.FILE_REQUEST_RETRY_INTERVAL)
        else:
            self.errorOccurred.emit(self)
            self._setFinished()

    def _retryTimerTimeout(self) -> None:
        if self._error == None:
            self._retryScheduled = False
            self._retryRequested.emit(self)

    def _setFinished(self) -> None:
        if not self._finished:
            self._finished = True
            self.finished.emit(self)

    def isFinished(self) -> bool:
        return self._finished