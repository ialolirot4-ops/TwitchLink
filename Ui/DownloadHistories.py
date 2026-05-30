from Core.Ui import *
from Core.Config import Config
from Services.PartnerContent.PartnerContentInFeedWidgetListViewer import PartnerContentInFeedWidgetListViewer
from Services.Utils.OSUtils import OSUtils
from Download.History.DownloadHistory import DownloadHistory

import csv
import json


class DownloadHistories(QtWidgets.QWidget):
    accountPageShowRequested = QtCore.pyqtSignal()

    # Combo-box index constants
    _TYPE_ALL    = 0
    _TYPE_STREAM = 1
    _TYPE_VIDEO  = 2
    _TYPE_CLIP   = 3

    _RESULT_ALL       = 0
    _RESULT_COMPLETED = 1
    _RESULT_STOPPED   = 2   # stopped (stream) OR canceled (vod/clip)
    _RESULT_ABORTED   = 3   # error / unexpected abort

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent=parent)
        self.previewWidgets: dict[DownloadHistory, Ui.DownloadHistoryView] = {}
        self._ui = UiLoader.load("downloadHistories", self)
        App.ThemeManager.themeUpdated.connect(self._setupThemeStyle)
        self._setupThemeStyle()
        self._ui.infoIcon = Utils.setSvgIcon(self._ui.infoIcon, Icons.HISTORY)
        self._widgetListViewer = PartnerContentInFeedWidgetListViewer(
            self._ui.previewWidgetView,
            partnerContentSize=QtCore.QSize(320, 100),
            parent=self,
        )
        self._widgetListViewer.widgetClicked.connect(self.openFile)
        App.DownloadHistory.historyCreated.connect(self.createHistoryView)
        App.DownloadHistory.historyRemoved.connect(self.removeHistoryView)

        self._buildFilterBar()
        self._buildExportButton()
        self._buildNoResultsLabel()
        self.loadHistory()

    # ── UI construction ────────────────────────────────────────────────────────

    def _buildFilterBar(self) -> None:
        """Search box + Type combo + Result combo + Clear button."""
        filterLayout = QtWidgets.QHBoxLayout()
        filterLayout.setContentsMargins(0, 4, 0, 0)
        filterLayout.setSpacing(6)

        self._searchBox = QtWidgets.QLineEdit(parent=self)
        self._searchBox.setPlaceholderText(T("#Search title, channel or game…"))
        self._searchBox.setClearButtonEnabled(True)
        self._searchBox.textChanged.connect(self._applyFilters)
        filterLayout.addWidget(self._searchBox, stretch=1)

        self._typeCombo = QtWidgets.QComboBox(parent=self)
        for label in (T("#All types"), T("stream"), T("video"), T("clip")):
            self._typeCombo.addItem(label)
        self._typeCombo.currentIndexChanged.connect(self._applyFilters)
        filterLayout.addWidget(self._typeCombo)

        self._resultCombo = QtWidgets.QComboBox(parent=self)
        for label in (T("#All results"), T("download-complete"),
                      T("download-stopped"), T("download-aborted")):
            self._resultCombo.addItem(label)
        self._resultCombo.currentIndexChanged.connect(self._applyFilters)
        filterLayout.addWidget(self._resultCombo)

        self._filterBar = QtWidgets.QWidget(parent=self)
        self._filterBar.setLayout(filterLayout)
        self._filterBar.hide()   # shown only when history exists

        formLayout = self.layout()
        stackedIdx = formLayout.indexOf(self._ui.stackedWidget)
        formLayout.insertWidget(stackedIdx, self._filterBar)

    def _buildExportButton(self) -> None:
        """Export button — right-aligned above the filter bar."""
        exportLayout = QtWidgets.QHBoxLayout()
        exportLayout.setContentsMargins(0, 4, 0, 0)
        exportLayout.addStretch()
        self._exportButton = QtWidgets.QToolButton(parent=self)
        self._exportButton.setText(T("#Export History…"))
        self._exportButton.setMinimumHeight(28)
        self._exportButton.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._exportButton.clicked.connect(self.exportHistory)
        self._exportButton.setEnabled(False)
        exportLayout.addWidget(self._exportButton)

        formLayout = self.layout()
        stackedIdx = formLayout.indexOf(self._filterBar)   # insert above filter bar
        formLayout.insertLayout(stackedIdx, exportLayout)

    def _buildNoResultsLabel(self) -> None:
        """Label shown inside the list page when filters hide every entry."""
        self._noResultsLabel = QtWidgets.QLabel(
            T("#No results match your search."), parent=self
        )
        self._noResultsLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._noResultsLabel.hide()
        # Insert at top of previewWidgetPage layout (above the list)
        self._ui.previewWidgetPage.layout().insertWidget(0, self._noResultsLabel)

    def _setupThemeStyle(self) -> None:
        color = App.Instance.palette().color(
            QtGui.QPalette.ColorGroup.Normal, QtGui.QPalette.ColorRole.Base
        ).name()
        self._ui.stackedWidget.setStyleSheet(
            f"#stackedWidget {{background-color: {color};}}"
        )

    # ── History management ─────────────────────────────────────────────────────

    def loadHistory(self) -> None:
        self._widgetListViewer.setAutoReloadEnabled(False)
        for downloadHistory in App.DownloadHistory.getHistoryList():
            self.createHistoryView(downloadHistory)
        self._widgetListViewer.setAutoReloadEnabled(True)
        self._refreshControls()

    def historyCountChanged(self) -> None:
        hasItems = len(self.previewWidgets) > 0
        self._ui.stackedWidget.setCurrentIndex(1 if hasItems else 0)
        self._filterBar.setVisible(hasItems)
        self._refreshControls()

    def _refreshControls(self) -> None:
        hasItems = len(App.DownloadHistory.getHistoryList()) > 0
        self._exportButton.setEnabled(hasItems)

    def createHistoryView(self, downloadHistory: DownloadHistory) -> None:
        widget = Ui.DownloadHistoryView(downloadHistory, parent=None)
        widget.accountPageShowRequested.connect(self.accountPageShowRequested)
        self._widgetListViewer.insertWidget(0, widget)
        self.previewWidgets[downloadHistory] = widget
        self.historyCountChanged()
        self._applyFilters()   # apply current filters to the new entry

    def removeHistoryView(self, downloadHistory: DownloadHistory) -> None:
        self._widgetListViewer.removeWidget(self.previewWidgets.pop(downloadHistory))
        self.historyCountChanged()
        self._applyFilters()

    def openFile(self, widget: Ui.DownloadHistoryView) -> None:
        widget.clickHandler()

    # ── Filtering ──────────────────────────────────────────────────────────────

    def _applyFilters(self) -> None:
        """Show / hide history entries based on the current filter criteria."""
        query     = self._searchBox.text().strip().lower()
        typeIdx   = self._typeCombo.currentIndex()
        resultIdx = self._resultCombo.currentIndex()

        visibleCount = 0
        for history, widget in self.previewWidgets.items():
            matches = self._matchesFilter(history, query, typeIdx, resultIdx)
            self._widgetListViewer.setHidden(widget, not matches)
            if matches:
                visibleCount += 1

        # Show inline "no results" label when filters hide everything
        hasEntries = len(self.previewWidgets) > 0
        self._noResultsLabel.setVisible(hasEntries and visibleCount == 0)

    def _matchesFilter(
        self,
        history: DownloadHistory,
        query: str,
        typeIdx: int,
        resultIdx: int,
    ) -> bool:
        info    = history.downloadInfo
        content = info.content

        # ── Type filter ──────────────────────────────────────────────────────
        if typeIdx == self._TYPE_STREAM and not info.type.isStream():
            return False
        if typeIdx == self._TYPE_VIDEO and not info.type.isVideo():
            return False
        if typeIdx == self._TYPE_CLIP and not info.type.isClip():
            return False

        # ── Result filter ────────────────────────────────────────────────────
        result = history.result
        if resultIdx == self._RESULT_COMPLETED and result != DownloadHistory.Result.completed:
            return False
        if resultIdx == self._RESULT_STOPPED and result not in (
            DownloadHistory.Result.stopped, DownloadHistory.Result.canceled
        ):
            return False
        if resultIdx == self._RESULT_ABORTED and result != DownloadHistory.Result.aborted:
            return False

        # ── Text search ──────────────────────────────────────────────────────
        if query:
            title = (getattr(content, "title", "") or "").lower()
            try:
                if hasattr(content, "broadcaster"):
                    channel = (
                        content.broadcaster.displayName or content.broadcaster.login or ""
                    ).lower()
                elif hasattr(content, "owner"):
                    channel = (
                        content.owner.displayName or content.owner.login or ""
                    ).lower()
                else:
                    channel = ""
            except Exception:
                channel = ""
            try:
                game = (content.game.name or "").lower() if getattr(content, "game", None) else ""
            except Exception:
                game = ""
            fileName = info.fileName.lower()

            if not any(query in field for field in (title, channel, game, fileName)):
                return False

        return True

    # ── Export ────────────────────────────────────────────────────────────────

    def exportHistory(self) -> None:
        histories = App.DownloadHistory.getHistoryList()
        if not histories:
            Utils.info("no-history", "#There is no download history to export.", parent=self)
            return
        defaultName = f"TwitchLink_history_{QtCore.QDate.currentDate().toString('yyyy-MM-dd')}"
        filePath, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            T("#Export Download History"),
            OSUtils.joinPath(OSUtils.getSystemHomeRoot(), defaultName),
            "CSV (*.csv);;JSON (*.json)",
        )
        if not filePath:
            return
        rows = [self._historyToDict(h) for h in histories]
        try:
            if filePath.lower().endswith(".json"):
                self._exportJson(filePath, rows)
            else:
                if not filePath.lower().endswith(".csv"):
                    filePath += ".csv"
                self._exportCsv(filePath, rows)
            Utils.info(
                "export-ok",
                T("#Exported {count} entries to:\n{path}", count=len(rows), path=filePath),
                parent=self,
            )
        except Exception as e:
            Utils.info("export-error", f"#Export failed:\n{e}", parent=self)

    def _historyToDict(self, history: DownloadHistory) -> dict:
        info    = history.downloadInfo
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
        try:
            game = content.game.name if getattr(content, "game", None) else ""
        except Exception:
            game = ""
        try:
            resolution = info.resolution.name
        except Exception:
            resolution = ""

        def fmt(dt: QtCore.QDateTime | None) -> str:
            if dt is None or not dt.isValid():
                return ""
            return dt.toLocalTime().toString("yyyy-MM-dd HH:mm:ss")

        pd = history.progressDetails
        size_bytes = pd.totalByteSize
        return {
            "type":             info.type.toString(),
            "title":            getattr(content, "title", "") or "",
            "channel":          channel,
            "game":             game,
            "resolution":       resolution,
            "file_name":        info.fileName,
            "file_path":        info.getAbsoluteFileName(),
            "directory":        info.directory,
            "started_at":       fmt(history.startedAt),
            "completed_at":     fmt(history.completedAt),
            "result":           history.result,
            "error":            history.error or "",
            "duration_seconds": pd.milliseconds // 1000,
            "file_size_bytes":  size_bytes,
            "file_size_mb":     round(size_bytes / (1024 * 1024), 2),
        }

    def _exportCsv(self, filePath: str, rows: list[dict]) -> None:
        with open(filePath, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    def _exportJson(self, filePath: str, rows: list[dict]) -> None:
        with open(filePath, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2, ensure_ascii=False)
