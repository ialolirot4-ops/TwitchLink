from Core import Qt
from Core.Config import Config
from Services.Utils.OSUtils import OSUtils
from Services.Logging.Logger import Logger
from Services.Logging.LogRotator import LogRotator

from PyQt6 import QtCore, QtWidgets, QtNetwork

import traceback as _traceback
import types
import sys
import uuid


class ExitCode:
    UNEXPECTED_ERROR = 2
    UNEXPECTED_ERROR_RESTART = 1
    EXIT = 0
    RESTART = -1


class SingleApplicationLauncher(QtWidgets.QApplication):
    EXIT_CODE = ExitCode

    newInstanceStarted = QtCore.pyqtSignal()

    def __init__(self, appId: str, argv: list[str]):
        # ── Windows: identificar proceso como TwitchLink (no "Python") ────────
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    f"DevHotteok.{appId}"
                )
            except Exception:
                pass
        super().__init__(argv)
        self.setApplicationName(Config.APP_NAME)
        self.setApplicationVersion(Config.APP_VERSION)
        self.setApplicationDisplayName("")

        # ── Prepare persistent log directories ────────────────────────────────
        for logDir in (Config.LOG_PATH, Config.ERROR_LOG_PATH):
            try:
                OSUtils.createDirectory(logDir)
            except Exception:
                pass

        # Rotate session logs: keep only the last MAX_SESSION_LOGS files
        LogRotator.rotate(
            directory=Config.LOG_PATH,
            pattern="session_*.log",
            maxCount=Config.MAX_SESSION_LOGS,
        )

        # ── Create the session log in AppData/logs (survives TEMP cleanups) ──
        sessionFileName = f"session_{Logger.getFormattedTime()}.log"
        self.logger = Logger(
            directory=Config.LOG_PATH,
            fileName=sessionFileName,
        )
        self.logger.info(f"\n\n{Config.getProjectInfo()}\n")
        self.logger.info(OSUtils.getOSInfo())

        self.shared = QtCore.QSharedMemory(appId, parent=self)
        if self.shared.create(512, QtCore.QSharedMemory.AccessMode.ReadWrite):
            self.logger.info("Application started successfully.")
            self._server = QtNetwork.QLocalServer(parent=self)
            self._server.newConnection.connect(self.newInstanceStarted)
            self._server.removeServer(appId)
            if not self._server.listen(appId):
                self.logger.warning("Failed to open Local Server.")
        else:
            self.logger.warning("Another instance of this application is already running.")
            self._socket = QtNetwork.QLocalSocket(parent=self)
            self._socket.connectToServer(appId)
            if self._socket.waitForConnected():
                self._socket.close()
            else:
                self.logger.warning("Unable to connect to Local Server.")
            sys.exit(self.EXIT_CODE.EXIT)
        self._started: QtCore.QDateTime | None = None
        self._crashed = False

    def _excepthook(self, exceptionType: type[BaseException], exception: BaseException, tracebackType: types.TracebackType | None) -> None:
        self.logger.critical("Unexpected Error", exc_info=(exceptionType, exception, tracebackType))
        if not self._crashed:
            self._crashed = True
            try:
                # ── Write the actual traceback to a dedicated error log ────
                LogRotator.rotate(
                    directory=Config.ERROR_LOG_PATH,
                    pattern="error_*.log",
                    maxCount=Config.MAX_ERROR_LOGS,
                )
                errorFileName = f"error_{Logger.getFormattedTime()}.log"
                errorFilePath = OSUtils.joinPath(Config.ERROR_LOG_PATH, errorFileName)
                with open(errorFilePath, "w", encoding="utf-8") as f:
                    f.write(f"TwitchLink {Config.APP_VERSION}\n")
                    f.write(f"Session log : {self.logger.getPath()}\n")
                    f.write(f"Error log   : {errorFilePath}\n")
                    f.write("=" * 72 + "\n\n")
                    _traceback.print_exception(exceptionType, exception, tracebackType, file=f)

                # ── TRACEBACK_FILE now holds the path to the error log ─────
                # (kept for backward compat with any external tooling)
                file = QtCore.QFile(Config.TRACEBACK_FILE, self)
                file.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
                file.write(errorFilePath.encode("utf-8"))
                file.close()
                file.deleteLater()
            except Exception:
                pass
            self.exit(
                self.EXIT_CODE.UNEXPECTED_ERROR
                if self._started.addSecs(Config.CRASH_AUTOMATIC_RESTART_COOLDOWN) > QtCore.QDateTime.currentDateTimeUtc()
                else self.EXIT_CODE.UNEXPECTED_ERROR_RESTART
            )

    def exec(self) -> int:
        self._started = QtCore.QDateTime.currentDateTimeUtc()
        sys.excepthook = self._excepthook
        self.logger.info("Launching...")
        returnCode = super().exec()
        self.logger.info(f"Application exited with exit code {returnCode}.")
        self.logger.info(f"Session log: '{self.logger.getPath()}'.")
        self._server.close()
        self.shared.detach()
        return returnCode