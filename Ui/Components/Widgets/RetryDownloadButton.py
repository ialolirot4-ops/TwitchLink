from Core.Ui import *
from Services.Twitch.Playback import TwitchPlaybackModels
from Services.Twitch.Playback import TwitchPlaybackGenerator
from Search import ExternalPlaybackGenerator
from Download.DownloadInfo import DownloadInfo
from Ui.Components.Widgets.DownloadButton import DownloadButton

import uuid


class RetryDownloadButton(DownloadButton):
    """
    Retries a download from history using the original file name, directory
    and format — without reopening the DownloadMenu options dialog.

    Flow:
        click → single confirmation dialog → fetch fresh playback token
              → startDownload() directly (bypasses DownloadMenu)
    """

    def __init__(
        self,
        downloadInfo: DownloadInfo,
        button: QtWidgets.QPushButton | QtWidgets.QToolButton,
        buttonIcon: ThemedIcon | None = None,
        buttonText: str | None = None,
        downloaderId: uuid.UUID | None = None,
        parent: QtCore.QObject | None = None,
    ):
        super().__init__(downloadInfo.content, button, buttonIcon, buttonText, parent=parent)
        self.downloadInfo = downloadInfo
        self.downloaderId = downloaderId
        if isinstance(self.downloadInfo.playback, ExternalPlaybackGenerator.ExternalPlayback):
            self.button.clicked.disconnect()
            self.button.clicked.connect(self.retryExternalContentDownload)

    # ── Confirmation (single dialog) ──────────────────────────────────────────

    def _confirmRetry(self, properties: tuple[str, ...]) -> bool:
        """One confirmation dialog that replaces the old two-dialog flow."""
        return self.ask(
            "warning",
            T(
                "#Retry the download with the same settings?\n\n"
                "Note: some metadata may differ from the original "
                "({properties}).",
                properties=", ".join(properties),
            ),
            contentTranslate=False,
        )

    # ── Trigger methods ───────────────────────────────────────────────────────

    def downloadStream(self) -> None:
        if self._confirmRetry((T("id"), T("title"), T("started-at"))):
            super().downloadStream()

    def downloadVideo(self) -> None:
        if self._confirmRetry((T("title"), T("duration"), T("views"))):
            super().downloadVideo()

    def downloadClip(self) -> None:
        if self._confirmRetry((T("title"), T("duration"))):
            super().downloadClip()

    # ── Playback result handlers — bypass DownloadMenu, start directly ────────

    def _processStreamPlaybackResult(
        self, generator: TwitchPlaybackGenerator.TwitchStreamPlaybackGenerator
    ) -> None:
        self.showLoading(False)
        if generator.getError() is None:
            self.startDownload(self.generateDownloadInfo(generator.getData()))
        else:
            self.handleExceptions(generator.getError())

    def _processVideoPlaybackResult(
        self, generator: TwitchPlaybackGenerator.TwitchStreamPlaybackGenerator
    ) -> None:
        self.showLoading(False)
        if generator.getError() is None:
            self.startDownload(self.generateDownloadInfo(generator.getData()))
        elif isinstance(generator.getError(), TwitchPlaybackGenerator.Exceptions.VideoRestricted):
            if App.Account.isSignedIn():
                advice = T(
                    "#Unable to find subscription in your account.\n"
                    "Subscribe to this streamer or sign in with another account."
                )
                okText = T("change-account")
            else:
                advice = T("#You need to sign in to download subscriber-only videos.")
                okText = T("sign-in")
            if self.ask(
                "unable-to-download",
                T("#This video is for subscribers only.\n{advice}", advice=advice),
                contentTranslate=False,
                okText=okText,
                cancelText=T("ok"),
            ):
                self.accountPageShowRequested.emit()
        elif isinstance(generator.getError(), TwitchPlaybackGenerator.Exceptions.VideoNotFound):
            self.info("unable-to-download", "#Video not found. Deleted or temporary error.")
        else:
            self.handleExceptions(generator.getError())

    def _processClipPlaybackResult(
        self, generator: TwitchPlaybackGenerator.TwitchStreamPlaybackGenerator
    ) -> None:
        self.showLoading(False)
        if generator.getError() is None:
            self.startDownload(self.generateDownloadInfo(generator.getData()))
        elif isinstance(generator.getError(), TwitchPlaybackGenerator.Exceptions.ClipNotFound):
            self.info("unable-to-download", "#Clip not found. Deleted or temporary error.")
        else:
            self.handleExceptions(generator.getError())

    # ── DownloadInfo — preserves original file settings exactly ──────────────

    def generateDownloadInfo(
        self,
        playback: (
            TwitchPlaybackModels.TwitchStreamPlayback
            | TwitchPlaybackModels.TwitchVideoPlayback
            | TwitchPlaybackModels.TwitchClipPlayback
        ),
    ) -> DownloadInfo:
        """
        Deep-copy the original downloadInfo, refresh the playback token,
        then restore the exact fileName / directory / fileFormat so the
        output file is identical to what the user originally set up.
        """
        originalFileName   = self.downloadInfo.fileName
        originalDirectory  = self.downloadInfo.directory
        originalFileFormat = self.downloadInfo.fileFormat

        downloadInfo = self.downloadInfo.copy()
        downloadInfo.updatePlayback(playback)

        # Restore original file settings after updatePlayback() may touch them
        downloadInfo.fileName   = originalFileName
        downloadInfo.fileFormat = originalFileFormat
        downloadInfo.setDirectory(originalDirectory)
        return downloadInfo

    # ── Start ─────────────────────────────────────────────────────────────────

    def startDownload(self, downloadInfo: DownloadInfo) -> None:
        if self.downloaderId is not None:
            App.DownloadManager.remove(self.downloaderId)
        super().startDownload(downloadInfo)

    # ── External content ──────────────────────────────────────────────────────

    def retryExternalContentDownload(self) -> None:
        self.askDownload(self.downloadInfo.copy())
