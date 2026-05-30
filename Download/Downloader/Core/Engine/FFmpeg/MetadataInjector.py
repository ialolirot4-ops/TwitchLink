from .Config import Config

from Services.Logging.Logger import Logger

from PyQt6 import QtCore


class MetadataInjector(QtCore.QObject):
    """
    Runs a single FFmpeg copy pass to embed metadata into an already-
    downloaded file (used for clips, which are not muxed by FFmpeg).

    The injector writes to a temp file alongside the original, then
    atomically replaces it on success.  On failure the original is left
    untouched so the download is not lost.

    Usage:
        injector = MetadataInjector(filePath, metadata, logger, parent=self)
        injector.finished.connect(self._onInjectionDone)
        injector.start()
    """

    finished = QtCore.pyqtSignal()

    # Suffix appended to the original path while FFmpeg writes
    _TMP_SUFFIX = ".tl_meta_tmp"

    def __init__(
        self,
        filePath: str,
        metadata: dict[str, str],
        logger: Logger,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent=parent)
        self._filePath   = filePath
        self._metadata   = metadata
        self._logger     = logger
        self._tempPath   = filePath + self._TMP_SUFFIX

        self._process = QtCore.QProcess(parent=self)
        self._process.finished.connect(self._onProcessFinished)
        self._process.errorOccurred.connect(self._onProcessError)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._logger.info("MetadataInjector: starting post-process pass.")
        args = [
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-i", self._filePath,
        ]
        for key, value in self._metadata.items():
            if value:
                args.extend(["-metadata", f"{key}={value}"])
        args.extend(["-c", "copy", self._tempPath])

        self._logger.info(f"MetadataInjector: {' '.join(args)}")
        self._process.start(Config.PATH, args)

    # ------------------------------------------------------------------
    # Private slots
    # ------------------------------------------------------------------

    def _onProcessFinished(self, exitCode: int, exitStatus: QtCore.QProcess.ExitStatus) -> None:
        tempFile     = QtCore.QFile(self._tempPath)
        originalFile = QtCore.QFile(self._filePath)

        if exitCode == 0 and tempFile.exists() and tempFile.size() > 0:
            # Atomic replace: remove original, rename temp
            if originalFile.exists():
                originalFile.remove()
            if tempFile.rename(self._filePath):
                self._logger.info("MetadataInjector: metadata embedded successfully.")
            else:
                self._logger.warning("MetadataInjector: rename failed; temp file left at " + self._tempPath)
        else:
            self._logger.warning(
                f"MetadataInjector: FFmpeg exited with code {exitCode}. "
                "Original file is intact (no metadata embedded)."
            )
            if tempFile.exists():
                tempFile.remove()

        self.finished.emit()

    def _onProcessError(self, error: QtCore.QProcess.ProcessError) -> None:
        self._logger.warning(f"MetadataInjector: process error — {error.name}:{error.value}. Skipping metadata.")
        QtCore.QFile(self._tempPath).remove()
        # finished will fire from _onProcessFinished; do not double-emit
