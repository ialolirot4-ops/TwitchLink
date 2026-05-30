"""
Download/Downloader/Core/Engine/File/BandwidthLimiter.py

Shared token-bucket rate limiter for all concurrent FileDownloader instances.

The bucket refills every 100 ms at 1/10th of the per-second limit.
When tokens run out, FileDownloader connects to `refilled` and retries
reading from the Qt network buffer as soon as new tokens are available.

Usage:
    limiter = BandwidthLimiter(parent=self)
    limiter.setLimit(512 * 1024)   # 512 KB/s
    limiter.setLimit(0)             # unlimited

    # Inside FileDownloader._onReadyRead():
    allowed = limiter.acquire(bytesAvailable)
"""

from PyQt6 import QtCore


class BandwidthLimiter(QtCore.QObject):
    """
    Token-bucket bandwidth limiter.

    Signals:
        refilled: emitted every 100 ms when a limit is active and new
                  tokens become available.  FileDownloader instances
                  that were throttled reconnect and retry their reads.
    """

    refilled = QtCore.pyqtSignal()

    _INTERVAL_MS = 100  # refill period

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent=parent)
        self._limit: int = 0          # bytes/sec; 0 = unlimited
        self._tokens: float = 0.0

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(self._INTERVAL_MS)
        self._timer.setSingleShot(False)
        self._timer.timeout.connect(self._refill)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def setLimit(self, bytesPerSecond: int) -> None:
        """Set the bandwidth cap.  0 means unlimited (timer stops)."""
        self._limit = max(0, bytesPerSecond)
        if self._limit > 0:
            # Seed the bucket with one full interval worth of tokens so
            # downloads don't stall immediately after enabling the limit.
            self._tokens = self._limit / (1000 / self._INTERVAL_MS)
            self._timer.start()
        else:
            self._timer.stop()
            self._tokens = 0.0

    def getLimit(self) -> int:
        """Return current cap in bytes/sec (0 = unlimited)."""
        return self._limit

    def acquire(self, requested: int) -> int:
        """
        Consume up to *requested* bytes from the token bucket.

        Returns the number of bytes the caller is allowed to read right
        now.  When no limit is active the full *requested* amount is
        returned without touching the bucket.
        """
        if self._limit == 0:
            return requested
        allowed = min(requested, max(0, int(self._tokens)))
        self._tokens -= allowed
        return allowed

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _refill(self) -> None:
        """Add 1/10th of the per-second quota and signal waiters."""
        add = self._limit / (1000 / self._INTERVAL_MS)
        self._tokens = min(float(self._limit), self._tokens + add)
        if self._tokens > 0:
            self.refilled.emit()
