from Core.Ui import *
from Core.Config import Config
from Download.Downloader.Core.Engine.Config import Config as DownloadEngineConfig
from Ui.Components.Widgets.FileNameTemplateInfo import FileNameTemplateInfo
from Services.Utils.OSUtils import OSUtils

import json
import shutil


class Settings(QtWidgets.QWidget):
    restartRequired = QtCore.pyqtSignal()

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent=parent)
        self._ui = UiLoader.load("settings", self)
        self._ui.openProgressWindow.setChecked(App.Preferences.general.isOpenProgressWindowEnabled())
        self._ui.openProgressWindow.toggled.connect(App.Preferences.general.setOpenProgressWindowEnabled)
        self._ui.notify.setChecked(App.Preferences.general.isNotifyEnabled())
        self._ui.notify.toggled.connect(App.Preferences.general.setNotifyEnabled)
        self._ui.windowClose.setCurrentIndex(1 if App.Preferences.general.isSystemTrayEnabled() else 0)
        self._ui.windowClose.currentIndexChanged.connect(self.windowCloseChanged)
        if not Utils.isMinimizeToSystemTraySupported():
            self._ui.windowCloseArea.hide()
        self.streamTemplateInfoWindow = FileNameTemplateInfo(FileNameTemplateInfo.TYPE.STREAM, parent=self)
        self._ui.streamFilename.setText(App.Preferences.templates.getStreamFilename())
        self._ui.streamFilename.editingFinished.connect(self.setStreamFilename)
        self._ui.streamTemplateInfo.clicked.connect(self.streamTemplateInfoWindow.show)
        Utils.setIconViewer(self._ui.streamTemplateInfo, Icons.HELP)
        self.videoTemplateInfoWindow = FileNameTemplateInfo(FileNameTemplateInfo.TYPE.VIDEO, parent=self)
        self._ui.videoFilename.setText(App.Preferences.templates.getVideoFilename())
        self._ui.videoFilename.editingFinished.connect(self.setVideoFilename)
        self._ui.videoTemplateInfo.clicked.connect(self.videoTemplateInfoWindow.show)
        Utils.setIconViewer(self._ui.videoTemplateInfo, Icons.HELP)
        self.clipTemplateInfoWindow = FileNameTemplateInfo(FileNameTemplateInfo.TYPE.CLIP, parent=self)
        self._ui.clipFilename.setText(App.Preferences.templates.getClipFilename())
        self._ui.clipFilename.editingFinished.connect(self.setClipFilename)
        self._ui.clipTemplateInfo.clicked.connect(self.clipTemplateInfoWindow.show)
        Utils.setIconViewer(self._ui.clipTemplateInfo, Icons.HELP)
        for bookmark in App.Preferences.general.getBookmarks():
            self.addBookmark(bookmark)
        self._ui.bookmarkList.model().rowsInserted.connect(self.saveBookmark)
        self._ui.bookmarkList.model().rowsMoved.connect(self.saveBookmark)
        self._ui.bookmarkList.model().rowsRemoved.connect(self.saveBookmark)
        self._ui.bookmarkList.currentRowChanged.connect(self.reloadBookmarkArea)
        self._ui.newBookmark.returnPressed.connect(self.tryAddBookmark)
        self._ui.newBookmark.textChanged.connect(self.reloadBookmarkArea)
        self._ui.addBookmarkButton.clicked.connect(self.tryAddBookmark)
        Utils.setIconViewer(self._ui.addBookmarkButton, Icons.PLUS)
        self._ui.removeBookmarkButton.clicked.connect(self.removeBookmark)
        Utils.setIconViewer(self._ui.removeBookmarkButton, Icons.TRASH)
        self._ui.automaticThemeIcon = Utils.setSvgIcon(self._ui.automaticThemeIcon, Icons.THEME_AUTOMATIC)
        self._ui.automaticThemeRadioButton.setChecked(App.ThemeManager.getThemeMode().isAuto())
        self._ui.automaticThemeRadioButton.toggled.connect(self._updateThemeMode)
        self._ui.lightThemeIcon = Utils.setSvgIcon(self._ui.lightThemeIcon, Icons.THEME_LIGHT)
        self._ui.lightThemeRadioButton.setChecked(App.ThemeManager.getThemeMode().isLight())
        self._ui.lightThemeRadioButton.toggled.connect(self._updateThemeMode)
        self._ui.darkThemeIcon = Utils.setSvgIcon(self._ui.darkThemeIcon, Icons.THEME_DARK)
        self._ui.darkThemeRadioButton.setChecked(App.ThemeManager.getThemeMode().isDark())
        self._ui.darkThemeRadioButton.toggled.connect(self._updateThemeMode)
        self._ui.searchExternalContent.setChecked(App.Preferences.advanced.isSearchExternalContentEnabled())
        self._ui.searchExternalContent.toggled.connect(App.Preferences.advanced.setSearchExternalContentEnabled)
        self._ui.searchExternalContentInfo.clicked.connect(self.showSearchExternalContentInfo)
        Utils.setIconViewer(self._ui.searchExternalContentInfo, Icons.HELP)

        # ── Post-process command group ─────────────────────────────────────────
        # Inserted programmatically into the General tab (same parent as bookmarkArea)
        hookGroup = QtWidgets.QGroupBox(T("Post-process command"), parent=self)
        hookLayout = QtWidgets.QVBoxLayout(hookGroup)

        hookInfo = QtWidgets.QLabel(
            T("#Command executed after each successful download.\n"
              "Variables: {file}  {directory}  {filename}  {title}  {channel}  {type}"),
            parent=hookGroup,
        )
        hookInfo.setWordWrap(True)
        hookInfo.setStyleSheet("color: palette(shadow); font-size: 11px;")
        hookLayout.addWidget(hookInfo)

        self._hookEdit = QtWidgets.QLineEdit(parent=hookGroup)
        self._hookEdit.setPlaceholderText('echo "Done: {file}"')
        self._hookEdit.setText(App.Preferences.general.getPostProcessCommand())
        self._hookEdit.editingFinished.connect(self._savePostProcessCommand)
        hookLayout.addWidget(self._hookEdit)

        # Insert at the bottom of whichever tab contains bookmarkArea
        generalTab = self._ui.bookmarkArea.parent()
        generalTab.layout().addWidget(hookGroup)
        # ─────────────────────────────────────────────────────────────────────
        for translationPack in App.Translator.getTranslationPacks():
            self._ui.language.addItem(translationPack.getDisplayName(), userData=translationPack.getId())
        self._ui.language.setCurrentIndex(self._ui.language.findData(App.Translator.getCurrentTranslationPackId()))
        self._ui.language.currentIndexChanged.connect(self.updateLanguage)
        self._ui.languageInfoIcon = Utils.setSvgIcon(self._ui.languageInfoIcon, Icons.ALERT_RED)
        self._ui.timezone.addItems(App.Preferences.localization.getTimezoneNameList())
        self._ui.timezone.setCurrentText(App.Preferences.localization.getTimezone().name())
        self._ui.timezone.currentTextChanged.connect(self.setTimezone)
        self._ui.timezoneInfoIcon = Utils.setSvgIcon(self._ui.timezoneInfoIcon, Icons.ALERT_RED)
        self._ui.downloadSpeed.setRange(DownloadEngineConfig.FILE_DOWNLOAD_MANAGER_MIN_POOL_SIZE, DownloadEngineConfig.FILE_DOWNLOAD_MANAGER_MAX_POOL_SIZE)
        self._ui.downloadSpeed.valueChanged.connect(self.setDownloadSpeed)
        self._ui.speedSpinBox.setRange(DownloadEngineConfig.FILE_DOWNLOAD_MANAGER_MIN_POOL_SIZE, DownloadEngineConfig.FILE_DOWNLOAD_MANAGER_MAX_POOL_SIZE)
        self._ui.speedSpinBox.valueChanged.connect(self.setDownloadSpeed)
        self.setDownloadSpeed(App.FileDownloadManager.getPoolSize())

        # ── Retry settings group (inserted after downloadSpeedArea) ───────────
        from AppData.Preferences import Download as DownloadPrefs
        retryGroup = QtWidgets.QGroupBox(T("Retry on error"), parent=self)
        retryForm  = QtWidgets.QFormLayout(retryGroup)
        retryForm.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        self._retryCountSpin = QtWidgets.QSpinBox(parent=retryGroup)
        self._retryCountSpin.setRange(DownloadPrefs.RETRY_COUNT_MIN, DownloadPrefs.RETRY_COUNT_MAX)
        self._retryCountSpin.setSuffix(f"  ({T('#attempts')})")
        self._retryCountSpin.setValue(DownloadEngineConfig.FILE_REQUEST_MAX_RETRY_COUNT)
        self._retryCountSpin.valueChanged.connect(self.setRetryCount)
        retryForm.addRow(T("#Max retries:"), self._retryCountSpin)

        self._retryIntervalSpin = QtWidgets.QSpinBox(parent=retryGroup)
        self._retryIntervalSpin.setRange(DownloadPrefs.RETRY_INTERVAL_MIN, DownloadPrefs.RETRY_INTERVAL_MAX)
        self._retryIntervalSpin.setSuffix(f"  ({T('#seconds')})")
        self._retryIntervalSpin.setValue(DownloadEngineConfig.FILE_REQUEST_RETRY_INTERVAL // 1000)
        self._retryIntervalSpin.valueChanged.connect(self.setRetryInterval)
        retryForm.addRow(T("#Retry interval:"), self._retryIntervalSpin)

        # Insert in the downloadSettings tab layout, right after downloadSpeedArea
        dlTab = self._ui.downloadSpeedArea.parent()
        dlLayout = dlTab.layout()
        speedIdx = dlLayout.indexOf(self._ui.downloadSpeedArea)
        dlLayout.insertWidget(speedIdx + 1, retryGroup)

        # ── Speed limit group ─────────────────────────────────────────────────
        speedLimitGroup = QtWidgets.QGroupBox(T("Bandwidth limit"), parent=self)
        speedLimitLayout = QtWidgets.QVBoxLayout(speedLimitGroup)

        self._speedLimitCheck = QtWidgets.QCheckBox(T("Limit download speed"), parent=speedLimitGroup)
        currentLimit = App.FileDownloadManager.getSpeedLimit()
        self._speedLimitCheck.setChecked(currentLimit > 0)
        self._speedLimitCheck.toggled.connect(self._onSpeedLimitToggled)
        speedLimitLayout.addWidget(self._speedLimitCheck)

        limitRow = QtWidgets.QHBoxLayout()
        self._speedLimitSpin = QtWidgets.QSpinBox(parent=speedLimitGroup)
        self._speedLimitSpin.setRange(DownloadPrefs.SPEED_LIMIT_MIN + 1, DownloadPrefs.SPEED_LIMIT_MAX)
        self._speedLimitSpin.setSuffix("  KB/s")
        self._speedLimitSpin.setValue(max(1, currentLimit // 1024))
        self._speedLimitSpin.setEnabled(currentLimit > 0)
        self._speedLimitSpin.valueChanged.connect(self._onSpeedLimitChanged)
        limitRow.addWidget(self._speedLimitSpin)
        limitRow.addStretch()
        speedLimitLayout.addLayout(limitRow)

        dlLayout.insertWidget(speedIdx + 2, speedLimitGroup)
        # ─────────────────────────────────────────────────────────────────────
        self._ui.resetButton.clicked.connect(self.resetSettings)
        self.reloadBookmarkArea()

        # ── Backup & Restore group (inserted programmatically before resetArea) ─
        self._backupGroup = QtWidgets.QGroupBox(T("Backup & Restore"), parent=self)
        backupLayout = QtWidgets.QVBoxLayout(self._backupGroup)

        exportBtn = QtWidgets.QToolButton(parent=self._backupGroup)
        exportBtn.setText(T("Export Settings…"))
        exportBtn.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )
        exportBtn.setMinimumHeight(30)
        exportBtn.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextOnly)
        exportBtn.clicked.connect(self.exportSettings)
        backupLayout.addWidget(exportBtn)

        importBtn = QtWidgets.QToolButton(parent=self._backupGroup)
        importBtn.setText(T("Import Settings…"))
        importBtn.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )
        importBtn.setMinimumHeight(30)
        importBtn.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextOnly)
        importBtn.clicked.connect(self.importSettings)
        backupLayout.addWidget(importBtn)

        # Insert right before resetArea so it sits in the same tab
        parentLayout = self._ui.resetArea.parent().layout()
        idx = parentLayout.indexOf(self._ui.resetArea)
        parentLayout.insertWidget(idx, self._backupGroup)
        # ───────────────────────────────────────────────────────────────────────
        App.GlobalDownloadManager.runningCountChangedSignal.connect(self.reload)
        self.reload()
        App.ThemeManager.themeUpdated.connect(self._setupThemeStyle)

    def _setupThemeStyle(self) -> None:
        for index in range(self._ui.bookmarkList.count()):
            self._ui.bookmarkList.item(index).setIcon(Icons.MOVE.icon)

    def reload(self) -> None:
        if App.GlobalDownloadManager.isDownloaderRunning():
            self._ui.languageArea.setEnabled(False)
            self._ui.timezoneArea.setEnabled(False)
            self._ui.resetArea.setEnabled(False)
            self._backupGroup.setEnabled(False)
            self._ui.restrictedLabel.show()
        else:
            self._ui.languageArea.setEnabled(True)
            self._ui.timezoneArea.setEnabled(True)
            self._ui.resetArea.setEnabled(True)
            self._backupGroup.setEnabled(True)
            self._ui.restrictedLabel.hide()
        # Sync retry spinboxes with live engine values
        self._retryCountSpin.blockSignals(True)
        self._retryCountSpin.setValue(DownloadEngineConfig.FILE_REQUEST_MAX_RETRY_COUNT)
        self._retryCountSpin.blockSignals(False)
        self._retryIntervalSpin.blockSignals(True)
        self._retryIntervalSpin.setValue(DownloadEngineConfig.FILE_REQUEST_RETRY_INTERVAL // 1000)
        self._retryIntervalSpin.blockSignals(False)
        # Sync speed limit controls
        currentLimit = App.FileDownloadManager.getSpeedLimit()
        self._speedLimitCheck.blockSignals(True)
        self._speedLimitCheck.setChecked(currentLimit > 0)
        self._speedLimitCheck.blockSignals(False)
        self._speedLimitSpin.setEnabled(currentLimit > 0)
        if currentLimit > 0:
            self._speedLimitSpin.blockSignals(True)
            self._speedLimitSpin.setValue(currentLimit // 1024)
            self._speedLimitSpin.blockSignals(False)
        # Sync post-process command
        self._hookEdit.setText(App.Preferences.general.getPostProcessCommand())

    def windowCloseChanged(self, index: int) -> None:
        App.Preferences.general.setSystemTrayEnabled(False if index == 0 else True)

    def setStreamFilename(self) -> None:
        App.Preferences.templates.setStreamFilename(self._ui.streamFilename.text())

    def setVideoFilename(self) -> None:
        App.Preferences.templates.setVideoFilename(self._ui.videoFilename.text())

    def setClipFilename(self) -> None:
        App.Preferences.templates.setClipFilename(self._ui.clipFilename.text())

    def reloadBookmarkArea(self) -> None:
        selected = self._ui.bookmarkList.currentRow() != -1
        text = self._ui.newBookmark.text().strip().lower()
        textNotEmptyOrDuplicate = text != "" and len(self._ui.bookmarkList.findItems(text, QtCore.Qt.MatchFlag.MatchFixedString)) == 0
        self._ui.addBookmarkButton.setEnabled(textNotEmptyOrDuplicate)
        self._ui.removeBookmarkButton.setEnabled(selected)

    def tryAddBookmark(self) -> None:
        if self._ui.addBookmarkButton.isEnabled():
            self.addBookmark(self._ui.newBookmark.text().strip().lower())
            self._ui.newBookmark.clear()

    def addBookmark(self, bookmark: str) -> None:
        item = QtWidgets.QListWidgetItem(bookmark)
        item.setIcon(Icons.MOVE.icon)
        item.setToolTip(T("#Drag to change order."))
        self._ui.bookmarkList.addItem(item)
        self._ui.newBookmark.clear()

    def removeBookmark(self) -> None:
        self._ui.bookmarkList.takeItem(self._ui.bookmarkList.currentRow())
        self._ui.bookmarkList.setCurrentRow(-1)

    def saveBookmark(self) -> None:
        App.Preferences.general.setBookmarks([self._ui.bookmarkList.item(index).text() for index in range(self._ui.bookmarkList.count())])

    def _updateThemeMode(self) -> None:
        if self._ui.automaticThemeRadioButton.isChecked():
            App.ThemeManager.setThemeMode(App.ThemeManager.Modes.AUTO)
        elif self._ui.lightThemeRadioButton.isChecked():
            App.ThemeManager.setThemeMode(App.ThemeManager.Modes.LIGHT)
        elif self._ui.darkThemeRadioButton.isChecked():
            App.ThemeManager.setThemeMode(App.ThemeManager.Modes.DARK)

    def showSearchExternalContentInfo(self) -> None:
        Utils.info("information", "#Allow URL Search to retrieve external content.\nYou can download content outside of Twitch.", parent=self)

    def updateLanguage(self) -> None:
        App.Translator.setTranslationPack(self._ui.language.currentData())
        self.requestRestart()

    def setTimezone(self, timezone: str) -> None:
        App.Preferences.localization.setTimezone(bytes(timezone, encoding="utf-8"))
        self.requestRestart()

    def setDownloadSpeed(self, speed: int) -> None:
        App.FileDownloadManager.setPoolSize(speed)
        self._ui.downloadSpeed.setValueSilent(speed)
        self._ui.speedSpinBox.setValueSilent(speed)

    def setRetryCount(self, count: int) -> None:
        DownloadEngineConfig.FILE_REQUEST_MAX_RETRY_COUNT = count
        self._retryCountSpin.blockSignals(True)
        self._retryCountSpin.setValue(count)
        self._retryCountSpin.blockSignals(False)

    def setRetryInterval(self, seconds: int) -> None:
        DownloadEngineConfig.FILE_REQUEST_RETRY_INTERVAL = seconds * 1000
        self._retryIntervalSpin.blockSignals(True)
        self._retryIntervalSpin.setValue(seconds)
        self._retryIntervalSpin.blockSignals(False)

    def _onSpeedLimitToggled(self, enabled: bool) -> None:
        self._speedLimitSpin.setEnabled(enabled)
        limit = self._speedLimitSpin.value() * 1024 if enabled else 0
        App.FileDownloadManager.setSpeedLimit(limit)

    def _onSpeedLimitChanged(self, kbps: int) -> None:
        if self._speedLimitCheck.isChecked():
            App.FileDownloadManager.setSpeedLimit(kbps * 1024)

    def _savePostProcessCommand(self) -> None:
        App.Preferences.general.setPostProcessCommand(self._hookEdit.text())

    def resetSettings(self) -> None:
        if Utils.ask("warning", "#This will reset all settings.\nProceed?", parent=self):
            App.Preferences.reset()
            self.requestRestart()

    def exportSettings(self) -> None:
        """Copy the current settings.json to a user-chosen file."""
        # Flush any unsaved in-memory state before copying
        App.Preferences.save()
        defaultName = f"TwitchLink_settings_{QtCore.QDate.currentDate().toString('yyyy-MM-dd')}.json"
        filePath, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            T("#Export Settings"),
            OSUtils.joinPath(OSUtils.getSystemHomeRoot(), defaultName),
            "JSON (*.json)",
        )
        if not filePath:
            return
        try:
            shutil.copy2(Config.APPDATA_FILE, filePath)
            Utils.info("export-ok", "Settings exported successfully.", parent=self)
        except Exception as e:
            Utils.info("export-error", f"Export failed:\n{e}", parent=self)

    def importSettings(self) -> None:
        """Load settings from a user-chosen JSON file and apply them live."""
        filePath, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            T("#Import Settings"),
            OSUtils.getSystemHomeRoot(),
            "JSON (*.json)",
        )
        if not filePath:
            return

        # Validate: must be readable JSON with at least one known top-level key
        try:
            with open(filePath, "r", encoding="utf-8") as f:
                raw = json.load(f)
            knownKeys = {"setup", "general", "templates", "advanced", "localization",
                         "download", "scheduledDownloads", "favorites"}
            if not knownKeys.intersection(raw.keys()):
                Utils.info(
                    "import-error",
                    "#This does not appear to be a valid TwitchLink settings file.",
                    parent=self,
                )
                return
        except Exception:
            Utils.info("import-error", "Could not read the selected file.", parent=self)
            return

        if not Utils.ask(
            "warning",
            "#Current settings will be replaced with those from the selected file.\nProceed?",
            parent=self,
        ):
            return

        try:
            shutil.copy2(filePath, Config.APPDATA_FILE)
            App.Preferences.load()
            Utils.info(
                "import-ok",
                "#Settings imported successfully.\nSome changes may require a restart.",
                parent=self,
            )
            self.requestRestart()
        except Exception as e:
            Utils.info("import-error", f"Import failed:\n{e}", parent=self)

    def requestRestart(self) -> None:
        self.restartRequired.emit()