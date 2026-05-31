"""
Ui/BatchDownload.py

Dialog for queueing multiple Twitch downloads at once.
The user can paste URLs / IDs (one per line) or load them from a .txt file.
Each entry is resolved sequentially (SearchEngine → PlaybackGenerator → DownloadManager)
to avoid hitting the GQL rate limit.

Supported inputs (same as the regular search):
  - twitch.tv/channel_name          → live stream
  - twitch.tv/videos/1234567890     → VOD
  - clips.twitch.tv/SlugHere        → clip
  - Raw video ID (numeric)          → VOD
  - Raw clip slug                   → clip
"""

from Core.Ui import *
from Services.Messages import Messages
from Services import ContentManager
from Services.Twitch.GQL import TwitchGQLModels
from Services.Twitch.Playback import TwitchPlaybackGenerator
from Search import Engine as SearchEngine
from Search.SearchMode import SearchMode
from Download.DownloadInfo import DownloadInfo


# ── Status labels for each row ────────────────────────────────────────────────
class _Status:
    PENDING   = "pending"
    RESOLVING = "resolving"
    FETCHING  = "fetching"
    QUEUED    = "queued"
    SKIPPED   = "skipped"
    ERROR     = "error"

_STATUS_COLOR = {
    _Status.PENDING:   "",
    _Status.RESOLVING: "#2196F3",
    _Status.FETCHING:  "#2196F3",
    _Status.QUEUED:    "#4CAF50",
    _Status.SKIPPED:   "#FF9800",
    _Status.ERROR:     "#F44336",
}


class BatchDownload(QtWidgets.QDialog):
    """Modal dialog that resolves and queues a list of Twitch URLs/IDs."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent=parent)
        self.setWindowTitle(T("#Batch Download"))
        self.setMinimumSize(680, 520)
        self.setWindowFlag(QtCore.Qt.WindowType.WindowMaximizeButtonHint)

        self._entries: list[str] = []          # raw queries
        self._currentIndex: int = -1           # index being processed
        self._processing: bool = False

        self._buildUi()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _buildUi(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        # Title
        titleLabel = QtWidgets.QLabel(T("#Batch Download"), self)
        font = titleLabel.font()
        font.setPointSize(14)
        font.setBold(True)
        titleLabel.setFont(font)
        layout.addWidget(titleLabel)

        line = QtWidgets.QFrame(self)
        line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        layout.addWidget(line)

        # Input area
        inputLabel = QtWidgets.QLabel(
            T("#Enter one URL or ID per line (channel, video, clip):"), self
        )
        layout.addWidget(inputLabel)

        self._textEdit = QtWidgets.QPlainTextEdit(self)
        self._textEdit.setPlaceholderText(
            "https://www.twitch.tv/videos/1234567890\n"
            "https://clips.twitch.tv/FancySlugHere\n"
            "1234567890\n"
            "ClipSlugHere"
        )
        self._textEdit.setMinimumHeight(100)
        self._textEdit.setMaximumHeight(160)
        layout.addWidget(self._textEdit)

        # Load file button
        fileRow = QtWidgets.QHBoxLayout()
        loadFileBtn = QtWidgets.QPushButton(T("#Load from .txt file…"), self)
        loadFileBtn.setFixedWidth(180)
        loadFileBtn.clicked.connect(self._loadFromFile)
        fileRow.addWidget(loadFileBtn)
        fileRow.addStretch()
        layout.addLayout(fileRow)

        # Progress table
        self._table = QtWidgets.QTableWidget(0, 3, self)
        self._table.setHorizontalHeaderLabels([T("#URL / ID"), T("#Content"), T("#Status")])
        self._table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(2, 100)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table)

        # Bottom buttons
        btnRow = QtWidgets.QHBoxLayout()
        self._startBtn = QtWidgets.QPushButton(T("#Start Batch Download"), self)
        self._startBtn.setDefault(True)
        self._startBtn.clicked.connect(self._startBatch)
        closeBtn = QtWidgets.QPushButton(T("close"), self)
        closeBtn.clicked.connect(self.close)
        btnRow.addStretch()
        btnRow.addWidget(self._startBtn)
        btnRow.addWidget(closeBtn)
        layout.addLayout(btnRow)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _loadFromFile(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, T("#Load URL list"), "", "Text files (*.txt);;All files (*)"
        )
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._textEdit.setPlainText(f.read())
            except Exception as e:
                Utils.info("file-error", f"#Could not read file:\n{e}", parent=self)

    def _startBatch(self) -> None:
        if self._processing:
            return
        # Parse non-empty lines
        raw = self._textEdit.toPlainText()
        entries = [line.strip() for line in raw.splitlines() if line.strip()]
        if not entries:
            Utils.info("no-input", "#Please enter at least one URL or ID.", parent=self)
            return

        self._entries = entries
        self._currentIndex = 0
        self._processing = True
        self._startBtn.setEnabled(False)
        self._textEdit.setReadOnly(True)

        # Populate table
        self._table.setRowCount(0)
        for entry in entries:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QtWidgets.QTableWidgetItem(entry))
            self._table.setItem(row, 1, QtWidgets.QTableWidgetItem(""))
            self._setRowStatus(row, _Status.PENDING)

        self._processNext()

    def _processNext(self) -> None:
        if self._currentIndex >= len(self._entries):
            self._onBatchComplete()
            return
        query = self._entries[self._currentIndex]
        self._setRowStatus(self._currentIndex, _Status.RESOLVING)
        mode = SearchMode()
        SearchEngine.SearchEngine(
            mode=mode,
            query=query,
            searchExternalContent=App.Preferences.advanced.isSearchExternalContentEnabled(),
            parent=self,
        ).finished.connect(self._onSearchFinished)

    def _onSearchFinished(self, engine: SearchEngine.SearchEngine) -> None:
        row = self._currentIndex
        if engine.getError() is not None:
            self._setRowStatus(row, _Status.ERROR, str(engine.getError()))
            self._advance()
            return

        data = engine.getData()

        if isinstance(data, TwitchGQLModels.Channel):
            # A channel result — only downloadable if live
            if data.stream is None:
                self._table.item(row, 1).setText(data.displayName or data.login)
                self._setRowStatus(row, _Status.SKIPPED, T("#Channel is offline"))
                self._advance()
            else:
                self._table.item(row, 1).setText(
                    f"{data.displayName or data.login} (Stream)"
                )
                self._setRowStatus(row, _Status.FETCHING)
                TwitchPlaybackGenerator.TwitchStreamPlaybackGenerator(
                    data.login, parent=self
                ).finished.connect(self._onPlaybackFinished)

        elif isinstance(data, TwitchGQLModels.Stream):
            self._table.item(row, 1).setText(
                f"{data.broadcaster.displayName or data.broadcaster.login} (Stream)"
            )
            self._setRowStatus(row, _Status.FETCHING)
            TwitchPlaybackGenerator.TwitchStreamPlaybackGenerator(
                data.broadcaster.login, parent=self
            ).finished.connect(self._onPlaybackFinished)

        elif isinstance(data, TwitchGQLModels.Video):
            self._table.item(row, 1).setText(data.title or data.id)
            self._setRowStatus(row, _Status.FETCHING)
            TwitchPlaybackGenerator.TwitchVideoPlaybackGenerator(
                data.id, parent=self
            ).finished.connect(self._onPlaybackFinished)

        elif isinstance(data, TwitchGQLModels.Clip):
            self._table.item(row, 1).setText(data.title or data.slug)
            self._setRowStatus(row, _Status.FETCHING)
            TwitchPlaybackGenerator.TwitchClipPlaybackGenerator(
                data.slug, parent=self
            ).finished.connect(self._onPlaybackFinished)

        else:
            # External playback or unknown type — skip
            self._setRowStatus(row, _Status.SKIPPED, T("#Unsupported content type"))
            self._advance()

    def _onPlaybackFinished(self, generator) -> None:
        row = self._currentIndex
        if generator.getError() is not None:
            self._setRowStatus(row, _Status.ERROR, str(generator.getError()))
            self._advance()
            return

        playback = generator.getData()
        # Find the content object that was resolved for this row
        # We rebuild it from the stored search — use a dummy to trigger DownloadInfo defaults
        content = self._getContentForRow(row)
        if content is None:
            self._setRowStatus(row, _Status.ERROR, T("#Could not determine content"))
            self._advance()
            return

        downloadInfo = DownloadInfo(content, playback)
        try:
            App.DownloadManager.create(downloadInfo)
            self._setRowStatus(row, _Status.QUEUED)
        except ContentManager.Exceptions.RestrictedContent:
            self._setRowStatus(row, _Status.SKIPPED, T("#Content restricted"))
        except Exception as e:
            self._setRowStatus(row, _Status.ERROR, str(e))
        self._advance()

    def _advance(self) -> None:
        self._currentIndex += 1
        # Small delay between requests to respect the GQL rate limit
        QtCore.QTimer.singleShot(500, self._processNext)

    def _onBatchComplete(self) -> None:
        self._processing = False
        self._startBtn.setEnabled(True)
        self._textEdit.setReadOnly(False)
        queued  = sum(1 for r in range(self._table.rowCount())
                      if self._table.item(r, 2) and
                      self._table.item(r, 2).text() == T(f"#{_Status.QUEUED}"))
        errors  = sum(1 for r in range(self._table.rowCount())
                      if self._table.item(r, 2) and
                      self._table.item(r, 2).text().startswith(T(f"#{_Status.ERROR}")))
        Utils.info(
            "batch-complete",
            T("#Batch complete.\nQueued: {q}   Errors/skipped: {e}",
              q=queued, e=self._table.rowCount() - queued),
            parent=self,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _setRowStatus(self, row: int, status: str, detail: str = "") -> None:
        text  = T(f"#{status.capitalize()}") + (f": {detail}" if detail else "")
        item  = QtWidgets.QTableWidgetItem(text)
        color = _STATUS_COLOR.get(status, "")
        if color:
            item.setForeground(QtGui.QColor(color))
        self._table.setItem(row, 2, item)
        self._table.scrollToItem(item)

    # We need to store the resolved content per row so _onPlaybackFinished can use it.
    # We keep a parallel list updated in _onSearchFinished.
    def _getContentForRow(self, row: int) -> TwitchGQLModels.Stream | TwitchGQLModels.Video | TwitchGQLModels.Clip | None:
        return self._resolvedContent.get(row)

    def _onSearchFinished(self, engine: SearchEngine.SearchEngine) -> None:  # noqa: F811
        """Override with content caching."""
        row = self._currentIndex
        if engine.getError() is not None:
            self._setRowStatus(row, _Status.ERROR, str(engine.getError()))
            self._advance()
            return

        data = engine.getData()
        if not hasattr(self, "_resolvedContent"):
            self._resolvedContent: dict[int, object] = {}

        if isinstance(data, TwitchGQLModels.Channel):
            if data.stream is None:
                self._table.item(row, 1).setText(data.displayName or data.login)
                self._setRowStatus(row, _Status.SKIPPED, T("#Channel is offline"))
                self._advance()
                return
            content = data.stream
            label = f"{data.displayName or data.login} (Stream)"
        elif isinstance(data, TwitchGQLModels.Stream):
            content = data
            label = f"{data.broadcaster.displayName or data.broadcaster.login} (Stream)"
        elif isinstance(data, TwitchGQLModels.Video):
            content = data
            label = data.title or data.id
        elif isinstance(data, TwitchGQLModels.Clip):
            content = data
            label = data.title or data.slug
        else:
            self._setRowStatus(row, _Status.SKIPPED, T("#Unsupported content type"))
            self._advance()
            return

        self._resolvedContent[row] = content
        self._table.item(row, 1).setText(label)
        self._setRowStatus(row, _Status.FETCHING)

        if isinstance(content, TwitchGQLModels.Stream):
            TwitchPlaybackGenerator.TwitchStreamPlaybackGenerator(
                content.broadcaster.login, parent=self
            ).finished.connect(self._onPlaybackFinished)
        elif isinstance(content, TwitchGQLModels.Video):
            TwitchPlaybackGenerator.TwitchVideoPlaybackGenerator(
                content.id, parent=self
            ).finished.connect(self._onPlaybackFinished)
        elif isinstance(content, TwitchGQLModels.Clip):
            TwitchPlaybackGenerator.TwitchClipPlaybackGenerator(
                content.slug, parent=self
            ).finished.connect(self._onPlaybackFinished)