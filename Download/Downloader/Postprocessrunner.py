"""
Download/PostProcessRunner.py

Runs a user-configured shell command after a successful download.

Template variables (Python-style {name}):
  {file}       – absolute path to the downloaded file
  {directory}  – output directory (no trailing separator)
  {filename}   – file name including extension (no directory)
  {title}      – content title
  {channel}    – broadcaster / channel display name
  {type}       – "stream", "video", or "clip"

Example commands:
  echo "Done: {file}"
  python C:\\scripts\\encode.py --input "{file}"
  ffmpeg -i "{file}" -c copy "{directory}\\{filename}_copy.mp4"

The command is launched detached via QProcess so it does not block the UI.
stdout / stderr are forwarded to the app logger.
"""

from Services.Logging.Logger import Logger

from PyQt6 import QtCore

import shlex
import sys


class PostProcessRunner(QtCore.QObject):
    """
    Resolves the template, starts the process, and logs its output.

    The class keeps a strong Python reference to every active instance in
    _active so callers never need to store the runner themselves — just call
    PostProcessRunner(...).start() or use the module-level launch() helper.
    """

    finished = QtCore.pyqtSignal(bool)   # True = exit code 0

    _active: "set[PostProcessRunner]" = set()  # keeps Python refs alive

    def __init__(
        self,
        command: str,
        context: dict[str, str],
        logger: Logger,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent=parent)
        self._command  = command.strip()
        self._context  = context
        self._logger   = logger
        self._process  = QtCore.QProcess(parent=self)
        self._process.setProcessChannelMode(
            QtCore.QProcess.ProcessChannelMode.MergedChannels
        )
        self._process.readyRead.connect(self._onReadyRead)
        self._process.finished.connect(self._onFinished)
        self._process.errorOccurred.connect(self._onError)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def start(self) -> None:
        PostProcessRunner._active.add(self)
        resolved = self._resolve(self._command)
        if not resolved:
            self._logger.warning("PostProcessRunner: command is empty, skipping.")
            PostProcessRunner._active.discard(self)
            self.finished.emit(True)
            return

        self._logger.info(f"PostProcessRunner: {resolved}")

        # Split into program + args; on Windows use the shell so that
        # built-ins (echo, del, …) and .bat/.cmd files work.
        if sys.platform == "win32":
            self._startWindows(resolved)
        else:
            parts = shlex.split(resolved)
            self._process.start(parts[0], parts[1:])

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _resolve(self, template: str) -> str:
        """Substitute {variable} placeholders; unknown keys are left as-is."""
        class _SafeDict(dict):
            def __missing__(self, key: str) -> str:
                return f"{{{key}}}"

        try:
            return template.format_map(_SafeDict(self._context))
        except Exception as e:
            self._logger.warning(f"PostProcessRunner: template error — {e}")
            return template

    def _startWindows(self, resolved: str) -> None:
        """
        On Windows, cmd.exe /c wraps the resolved string in an extra layer of
        quotes, which corrupts the inner double-quotes of powershell -Command "..."
        and strips PowerShell variable names ($n, $d, …).
        When the command is a PowerShell invocation we run powershell.exe directly
        and pass the script block as a properly-separated argument so that
        QProcess (CreateProcess) handles quoting without collision.
        For all other commands we fall back to cmd.exe /c.
        """
        import re
        stripped = resolved.strip()
        m = re.match(
            r'^(powershell(?:\.exe)?|pwsh(?:\.exe)?)\s+.*?-[Cc]ommand\s+"(.+)"$',
            stripped,
            re.IGNORECASE | re.DOTALL,
        )
        if m:
            prog, script = m.group(1), m.group(2)
            self._process.start(prog, ["-NoProfile", "-NonInteractive", "-Command", script])
        else:
            self._process.start("cmd.exe", ["/c", resolved])

    def _onReadyRead(self) -> None:
        data = self._process.readAll().data()
        try:
            text = data.decode("utf-8", errors="replace").rstrip()
        except Exception:
            text = repr(data)
        if text:
            self._logger.info(f"[hook] {text}")

    def _onFinished(self, exitCode: int, exitStatus: QtCore.QProcess.ExitStatus) -> None:
        if exitCode == 0:
            self._logger.info(f"PostProcessRunner: finished (exit 0).")
        else:
            self._logger.warning(f"PostProcessRunner: finished with exit code {exitCode}.")
        PostProcessRunner._active.discard(self)
        self.finished.emit(exitCode == 0)

    def _onError(self, error: QtCore.QProcess.ProcessError) -> None:
        self._logger.warning(
            f"PostProcessRunner: process error — {error.name} ({error.value}). "
            "Check that the program exists and the command is correct."
        )
        PostProcessRunner._active.discard(self)


# ------------------------------------------------------------------
# Helper: build context dict from a finished downloader
# ------------------------------------------------------------------

def buildContext(downloader) -> dict[str, str]:
    """
    Build the variable dict from a finished downloader.
    Import is deferred to avoid circular imports at module load time.
    """
    from Services.Twitch.GQL.TwitchGQLModels import Stream, Video, Clip
    import os

    info    = downloader.downloadInfo
    content = info.content

    try:
        if hasattr(content, "broadcaster"):
            channel = content.broadcaster.displayName or content.broadcaster.login
        elif hasattr(content, "owner"):
            channel = content.owner.displayName or content.owner.login
        else:
            channel = ""
    except Exception:
        channel = ""

    filePath = info.getAbsoluteFileName()

    return {
        "file":      filePath,
        "directory": info.directory,
        "filename":  os.path.basename(filePath),
        "title":     getattr(content, "title", "") or "",
        "channel":   channel,
        "type":      info.type.toString(),
    }


# ------------------------------------------------------------------
# Convenience: fire-and-forget for any download completion site
# ------------------------------------------------------------------

def launch(downloader, override_cmd: str | None = None) -> None:
    """
    Run the configured post-process command for a finished downloader.
    If override_cmd is provided (non-empty), it takes precedence over the
    global setting. No-op if the resolved command is empty.
    Callers need no lifecycle management.
    """
    from Core import App
    cmd = override_cmd if override_cmd else App.Preferences.general.getPostProcessCommand()
    if cmd:
        PostProcessRunner(cmd, buildContext(downloader), App.Instance.logger).start()