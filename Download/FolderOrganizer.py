"""
Download/FolderOrganizer.py

Automatically organizes finished downloads into per-channel / per-type
subdirectories.

Resulting layout example
------------------------
{base_directory}/
    NombreCanal/
        stream/
            archivo.ts
        video/
            clip.mp4
    OtroCanal/
        clip/
            clip.mp4

Usage
-----
Call ``organizeFile(downloader)`` right after a successful download, BEFORE
any PostProcessRunner is launched so that the {file} template variable
in the post-process command already points to the final location.

The feature is controlled by ``App.Preferences.general.isOrganizeByChannelEnabled()``.
"""

from __future__ import annotations

import os
import shutil

from Services.Logging.Logger import Logger


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _getChannelName(content) -> str:
    """Return the display name (or login) of the broadcaster / content owner."""
    try:
        if hasattr(content, "broadcaster"):
            return (
                content.broadcaster.displayName
                or content.broadcaster.login
                or "Unknown"
            )
        if hasattr(content, "owner"):
            return content.owner.displayName or content.owner.login or "Unknown"
    except Exception:
        pass
    return "Unknown"


def _safeDirectoryName(name: str) -> str:
    """Strip characters that are invalid in directory names on any platform."""
    from Services.Utils.OSUtils import OSUtils
    try:
        safe = OSUtils.getValidFileName(name)
        return safe if safe else "Unknown"
    except Exception:
        # Fallback: replace the most common invalid characters manually.
        for ch in r'\/:*?"<>|':
            name = name.replace(ch, "_")
        return name.strip() or "Unknown"


def _uniquePath(path: str) -> str:
    """Return *path* unchanged if it does not exist, otherwise append (n)."""
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    n = 1
    candidate = f"{base} ({n}){ext}"
    while os.path.exists(candidate):
        n += 1
        candidate = f"{base} ({n}){ext}"
    return candidate


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def organizeFile(downloader, logger: Logger | None = None) -> str | None:
    """
    Move the finished download to ``{base_dir}/{channel}/{type}/``.

    Parameters
    ----------
    downloader:
        Any completed downloader object that exposes ``.downloadInfo`` and
        ``.status``.
    logger:
        Optional logger; falls back to the app-level logger when omitted.

    Returns
    -------
    str | None
        The new absolute file path on success, or ``None`` if the file was
        not moved (feature disabled, file absent, error …).
    """
    from Core import App  # deferred to avoid circular imports at load time

    # Honour the user preference.
    if not App.Preferences.general.isOrganizeByChannelEnabled():
        return None

    info = downloader.downloadInfo

    # Nothing to move if the engine removed the file (e.g. empty download).
    if downloader.status.isFileRemoved():
        return None

    currentPath = info.getAbsoluteFileName()
    if not os.path.isfile(currentPath):
        return None

    # Resolve the effective logger.
    _log: Logger = logger or App.Instance.logger

    # Build the target directory: {base}/{channel}/{type}/
    channel  = _getChannelName(info.content)
    typeStr  = info.type.toString()          # "stream" | "video" | "clip"
    safeChannel = _safeDirectoryName(channel)

    targetDir = os.path.join(info.directory, safeChannel, typeStr)

    try:
        os.makedirs(targetDir, exist_ok=True)
    except OSError as exc:
        _log.warning(
            f"[FolderOrganizer] Could not create directory '{targetDir}': {exc}"
        )
        return None

    # Determine the destination path (resolve name collisions).
    fileName = os.path.basename(currentPath)
    destPath = _uniquePath(os.path.join(targetDir, fileName))

    # Move the file.
    try:
        shutil.move(currentPath, destPath)
    except Exception as exc:  # noqa: BLE001
        _log.warning(
            f"[FolderOrganizer] Could not move '{currentPath}' → '{destPath}': {exc}"
        )
        return None

    # Keep downloadInfo in sync so PostProcessRunner gets the right {file}.
    try:
        info.setAbsoluteFileName(destPath)
    except Exception as exc:
        _log.warning(
            f"[FolderOrganizer] Could not update downloadInfo path: {exc}"
        )

    _log.info(
        f"[FolderOrganizer] Moved to: {destPath}"
    )
    return destPath
