"""
Services/Logging/LogRotator.py

Keeps a bounded set of log files in a directory by deleting the oldest
ones when the count exceeds a configured limit.

Usage (called once at app startup, before creating the new log file):

    LogRotator.rotate(
        directory = Config.LOG_PATH,
        pattern   = "session_*.log",
        maxCount  = Config.MAX_SESSION_LOGS,
    )
"""

from Services.Utils.OSUtils import OSUtils

import glob
import os


class LogRotator:

    @staticmethod
    def rotate(directory: str, pattern: str, maxCount: int) -> None:
        """Delete the oldest files matching *pattern* inside *directory* until
        only (maxCount - 1) remain, making room for the new file about to be
        created.

        Args:
            directory: Absolute path to the log directory.
            pattern:   Glob pattern relative to *directory* (e.g. "*.log").
            maxCount:  Maximum number of files to keep *after* the new file
                       is created.  Rotation deletes files until the count is
                       strictly below this value.
        """
        if not os.path.isdir(directory):
            return
        files = sorted(
            glob.glob(os.path.join(directory, pattern))
        )
        # Leave room for the one we are about to create
        while len(files) >= maxCount:
            oldest = files.pop(0)
            try:
                os.remove(oldest)
            except OSError:
                # File may be locked or already gone — skip silently
                files = files  # just continue

    @staticmethod
    def listLogs(directory: str, pattern: str = "*.log") -> list[str]:
        """Return all log files matching *pattern* sorted newest-first."""
        if not os.path.isdir(directory):
            return []
        return sorted(
            glob.glob(os.path.join(directory, pattern)),
            reverse=True,
        )
