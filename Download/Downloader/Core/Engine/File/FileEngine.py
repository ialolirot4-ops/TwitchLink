from ..BaseEngine import BaseEngine
from ..File.FileDownloader import FileDownloader
from ..FFmpeg.Metadata import MetadataBuilder
from ..FFmpeg.MetadataInjector import MetadataInjector

from Core import App
from Core.GlobalExceptions import Exceptions
from Services.Logging.Logger import Logger
from Download.DownloadInfo import DownloadInfo
from Download.Downloader.Core.Engine import Modules

from PyQt6 import QtCore


class FileEngine(BaseEngine):
    def __init__(self, downloadInfo: DownloadInfo, status: Modules.Status, progress: Modules.Progress, logger: Logger, parent: QtCore.QObject | None = None):
        super().__init__(downloadInfo, status, progress, logger, parent=parent)
        self._fileDownloader: FileDownloader | None = None
        self._metadataInjector: MetadataInjector | None = None

    def start(self) -> None:
        super().start()
        self._fileDownloader = FileDownloader(
            self._networkAccessManager,
            self.downloadInfo.getUrl(),
            self.downloadInfo.getAbsoluteFileName(),
            priority=self.downloadInfo.getPriority(),
            parent=self
        )
        self._fileDownloader.progressChanged.connect(self._updateProgress)
        self._fileDownloader.errorOccurred.connect(self._fileDownloadFailed)
        self._fileDownloader.finished.connect(self._fileDownloadFinished)
        App.FileDownloadManager.startDownload(self._fileDownloader)

    def _updateProgress(self, bytesReceived: int, bytesTotal: int) -> None:
        self.progress.totalByteSize = bytesReceived
        self.progress.byteSize = bytesTotal
        self._syncProgress()

    def _fileDownloadFailed(self, fileDownloader: FileDownloader) -> None:
        super()._raiseException(fileDownloader.getError())

    def _fileDownloadFinished(self, fileDownloader: FileDownloader) -> None:
        # Clean up the downloader before any post-processing
        self._fileDownloader.setParent(None)
        self._fileDownloader = None

        # Only inject metadata on successful (non-aborted) downloads
        if self.status.terminateState.isFalse():
            self._injectMetadata()
        else:
            super()._finish()

    def pause(self) -> None:
        """Pause the active file download without aborting it."""
        if self._fileDownloader is not None:
            self._fileDownloader.pause()
        self.status.pauseState.setTrue()
        self._syncStatus()

    def resume(self) -> None:
        """Resume a paused file download."""
        self.status.pauseState.setFalse()
        self._syncStatus()
        if self._fileDownloader is not None:
            self._fileDownloader.resume()

    def _injectMetadata(self) -> None:
        """Start a quick FFmpeg copy pass to embed Twitch metadata into the file."""
        metadata = MetadataBuilder.build(self.downloadInfo)
        if metadata:
            self._metadataInjector = MetadataInjector(
                self.downloadInfo.getAbsoluteFileName(),
                metadata,
                self.logger,
                parent=self,
            )
            self._metadataInjector.finished.connect(self._onMetadataInjectionFinished)
            self._metadataInjector.start()
        else:
            super()._finish()

    def _onMetadataInjectionFinished(self) -> None:
        self._metadataInjector.setParent(None)
        self._metadataInjector = None
        super()._finish()

    def _finish(self) -> None:
        # May be called from the error / abort path; guard against None
        if self._fileDownloader is not None:
            self._fileDownloader.setParent(None)
            self._fileDownloader = None
        if self._metadataInjector is not None:
            self._metadataInjector.setParent(None)
            self._metadataInjector = None
        super()._finish()

    def _raiseException(self, exception: Exceptions.AbortRequested | Exceptions.FileSystemError | Exceptions.NetworkError) -> None:
        super()._raiseException(exception)
        if self._fileDownloader is not None:
            App.FileDownloadManager.cancelDownload(self._fileDownloader)