from .Engine import Modules
from .Engine.BaseEngine import BaseEngine

from Core.Config import Config
from Core.GlobalExceptions import Exceptions
from Download.DownloadInfo import DownloadInfo
from Services.Logging.Logger import Logger
from Services.FileNameLocker import FileNameLocker

from PyQt6 import QtCore

import uuid


class BaseDownloader(QtCore.QThread):
    started = QtCore.pyqtSignal(object)
    finished = QtCore.pyqtSignal(object)
    _abortRequested = QtCore.pyqtSignal(Exception)
    _pauseRequested = QtCore.pyqtSignal()
    _resumeRequested = QtCore.pyqtSignal()

    def __init__(self, downloadInfo: DownloadInfo, parent: QtCore.QObject | None = None):
        super().__init__(parent=parent)
        self.uuid = uuid.uuid4()
        self.downloadInfo = downloadInfo
        self.status = Modules.Status(parent=self)
        self.progress = Modules.Progress(parent=self)
        self.logger = Logger(
            name=f"Downloader_{self.getId()}",
            fileName=f"{Config.APP_NAME}_Download_{Logger.getFormattedTime()}#{self.getId()}.log"
        )
        self._fileNameLocker = FileNameLocker(self.downloadInfo.getAbsoluteFileName())
        self._fileNameLocker.lock()
        super().started.connect(self._threadStarted)
        super().finished.connect(self._threadFinished)

    def getId(self) -> uuid.UUID:
        return self.uuid

    def _threadStarted(self) -> None:
        self.started.emit(self)

    def _threadFinished(self) -> None:
        self._fileNameLocker.unlock()
        self.finished.emit(self)

    def _createEngine(self) -> BaseEngine:
        engine = BaseEngine(
            downloadInfo=self.downloadInfo,
            status=self.status,
            progress=self.progress,
            logger=self.logger,
            parent=None
        )
        self._abortRequested.connect(engine.abort)
        self._pauseRequested.connect(engine.pause)
        self._resumeRequested.connect(engine.resume)
        return engine

    def run(self) -> None:
        engine = self._createEngine()
        engine.finished.connect(self.exit)
        engine.start()
        self.exec()
        engine.deleteLater()

    def cancel(self) -> None:
        self.logger.warning("[ACTION] Cancel")
        self.abort(Exceptions.AbortRequested())

    def abort(self, exception: Exception) -> None:
        if self.status.terminateState.isFalse() and not self.status.isDone():
            self.status.terminateState.setPreparing()
            self.status.sync()
            self._abortRequested.emit(exception)

    def pause(self) -> None:
        """Request pause. pauseState transitions: False → Processing → True."""
        if (self.status.pauseState.isFalse()
                and self.status.isDownloading()
                and self.status.terminateState.isFalse()):
            self.status.pauseState.setProcessing()
            self.status.sync()
            self._pauseRequested.emit()

    def resume(self) -> None:
        """Resume from a paused state. Engine sets pauseState back to False."""
        if (not self.status.pauseState.isFalse()
                and self.status.isDownloading()
                and self.status.terminateState.isFalse()):
            self._resumeRequested.emit()