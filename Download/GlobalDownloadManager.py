"""
Download/GlobalDownloadManager.py

Aggregates DownloadManager (manual downloads) and ScheduledDownloadManager
(automated recordings) into a single façade used by the rest of the app.

Responsibilities
----------------
* Provide a unified ``isDownloaderRunning()`` that covers both managers.
* Forward a combined ``runningCountChangedSignal`` so the UI only needs one
  connection point.
* Coordinate graceful shutdown via ``cancelAll()`` / ``allCompletedSignal``.
* Delegate downloader-creation gating to ``TwitchDownloader.setCreationEnabled``.
* Record per-file stats and emit ``statsUpdated`` after milestones.
"""

from Core import App
from Download.Downloader.TwitchDownloader import TwitchDownloader

from PyQt6 import QtCore

# Emit statsUpdated after this many successful completions, then double each
# time (10, 20, 40, 80, …).
_FIRST_MILESTONE = 10


class GlobalDownloadManager(QtCore.QObject):
    # Total running downloaders (manual + scheduled) changed.
    runningCountChangedSignal = QtCore.pyqtSignal(int)

    # Emitted after download-count milestones to invite the user to contribute.
    # Args: totalFiles (int), totalByteSize (int)
    statsUpdated = QtCore.pyqtSignal(int, int)

    # Emitted when the last running download finishes while shutting down.
    allCompletedSignal = QtCore.pyqtSignal()

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent=parent)
        self._shuttingDown: bool = False
        self._nextMilestone: int = _FIRST_MILESTONE

        # Wire up the two underlying managers.
        App.DownloadManager.runningCountChangedSignal.connect(
            self._onRunningCountChanged
        )
        App.DownloadManager.completedSignal.connect(self._onDownloadCompleted)

        App.ScheduledDownloadManager.downloaderCountChangedSignal.connect(
            self._onRunningCountChanged
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def isDownloaderRunning(self) -> bool:
        return self._getTotalRunningCount() > 0

    def isShuttingDown(self) -> bool:
        return self._shuttingDown

    def setDownloaderCreationEnabled(self, enabled: bool) -> None:
        """Enable or disable creation of new manual downloaders."""
        TwitchDownloader.setCreationEnabled(enabled)

    def cancelAll(self) -> None:
        """Cancel every running downloader and enter shutdown mode."""
        self._shuttingDown = True
        App.DownloadManager.cancelAll()
        App.ScheduledDownloadManager.cancelAll()
        # If nothing was running, fire immediately.
        if not self.isDownloaderRunning():
            self._shuttingDown = False
            self.allCompletedSignal.emit()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _getTotalRunningCount(self) -> int:
        return (
            len(App.DownloadManager.getRunningDownloaders())
            + len(App.ScheduledDownloadManager.getRunningDownloaders())
        )

    def _onRunningCountChanged(self, _count: int) -> None:
        total = self._getTotalRunningCount()
        self.runningCountChangedSignal.emit(total)
        if self._shuttingDown and total == 0:
            self._shuttingDown = False
            self.allCompletedSignal.emit()

    def _onDownloadCompleted(self, downloaderId) -> None:
        """Called when a manual download finishes (success or failure)."""
        try:
            downloader = App.DownloadManager.get(downloaderId)
        except Exception:
            return

        # Only count successful downloads toward stats.
        if downloader.status.getError() is not None:
            return

        fileSize: int = downloader.progress.byteSize
        App.Preferences.updateDownloadStats(fileSize)

        stats = App.Preferences.getDownloadStats()
        totalFiles: int = stats["totalFiles"]
        totalByteSize: int = stats["totalByteSize"]

        # Emit at milestones so the contribute dialog is not shown every run.
        if totalFiles >= self._nextMilestone:
            self._nextMilestone *= 2
            self.statsUpdated.emit(totalFiles, totalByteSize)