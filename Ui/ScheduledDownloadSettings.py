from Core.Ui import *
from Services.Playlist.Resolution import Resolution
from Services.Twitch.GQL import TwitchGQLModels
from Search.QueryParser import TwitchQueryParser
from Download.ScheduledDownloadPreset import ScheduledDownloadPreset
from Ui.Components.Utils.FileNameGenerator import FileNameGenerator
from Ui.Components.Widgets.FileNameTemplateInfo import FileNameTemplateInfo


class ScheduledDownloadSettings(QtWidgets.QDialog, WindowGeometryManager):
    scheduledDownloadUpdated = QtCore.pyqtSignal(ScheduledDownloadPreset)

    def __init__(self, scheduledDownloadPreset: ScheduledDownloadPreset | None = None, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent=parent)
        self.isEditMode = scheduledDownloadPreset != None
        self.scheduledDownloadPreset = scheduledDownloadPreset if self.isEditMode else ScheduledDownloadPreset()
        self._ui = UiLoader.load("scheduledDownloadSettings", self)
        self.finished.connect(self.saveWindowGeometry)
        self.setWindowFlag(QtCore.Qt.WindowType.WindowMaximizeButtonHint)
        self.loadWindowGeometry()
        self.virtualPreset = scheduledDownloadPreset.copy() if self.isEditMode else self.scheduledDownloadPreset
        self._ui.channelEdit.setText(self.virtualPreset.channel)
        self._ui.channelEdit.setEnabled(not self.isEditMode)
        self._ui.channelEdit.textChanged.connect(self.channelChanged)
        self.reloadDirectory()
        self._ui.searchDirectory.clicked.connect(self.askDirectory)
        self.filenameTemplateInfoWindow = FileNameTemplateInfo(FileNameTemplateInfo.TYPE.STREAM, parent=self)
        self._ui.filenameTemplate.setText(self.virtualPreset.filenameTemplate)
        self._ui.filenameTemplate.textChanged.connect(self.filenameTemplateChanged)
        self._ui.filenameTemplateInfo.clicked.connect(self.filenameTemplateInfoWindow.show)
        Utils.setIconViewer(self._ui.filenameTemplateInfo, Icons.HELP)
        self.reloadFileFormat()
        self._ui.fileFormat.currentTextChanged.connect(self.fileFormatChanged)
        self._ui.filenamePreviewInfo.clicked.connect(self.showFilenamePreviewInfo)
        Utils.setIconViewer(self._ui.filenamePreviewInfo, Icons.HELP)
        for quality in self.virtualPreset.getQualityList():
            self._ui.preferredQuality.addItem(quality.toString() if quality.isValid() else T(quality.toString()))
        self._ui.preferredQuality.setCurrentIndex(self.virtualPreset.preferredQualityIndex)
        self._ui.preferredQuality.currentIndexChanged.connect(self.preferredQualityChanged)
        for frameRate in self.virtualPreset.getFrameRateList():
            self._ui.preferredFrameRate.addItem(frameRate.toString() if frameRate.isValid() else T(frameRate.toString()))
        self._ui.preferredFrameRate.setCurrentIndex(self.virtualPreset.preferredFrameRateIndex)
        self._ui.preferredFrameRate.currentIndexChanged.connect(self.preferredFrameRateChanged)
        self._ui.preferredResolutionOnlyCheckBox.setChecked(self.virtualPreset.isPreferredResolutionOnlyEnabled())
        self._ui.preferredResolutionOnlyCheckBox.toggled.connect(self.virtualPreset.setPreferredResolutionOnlyEnabled)
        self._ui.preferredResolutionOnlyInfo.clicked.connect(self.showPreferredResolutionOnlyInfo)
        Utils.setIconViewer(self._ui.preferredResolutionOnlyInfo, Icons.HELP)
        self._ui.adBlockSkipSegmentsRadioButton.setChecked(self.virtualPreset.isSkipAdsEnabled())
        self._ui.adBlockAlternativeScreenRadioButton.setChecked(not self.virtualPreset.isSkipAdsEnabled())
        self._ui.adBlockSkipSegmentsRadioButton.toggled.connect(self.virtualPreset.setSkipAdsEnabled)
        self._ui.adBlockInfo.clicked.connect(self.showAdBlockInfo)
        Utils.setIconViewer(self._ui.adBlockInfo, Icons.HELP)
        self._ui.remuxRadioButton.setChecked(self.virtualPreset.isRemuxEnabled())
        self._ui.concatRadioButton.setChecked(not self.virtualPreset.isRemuxEnabled())
        self._ui.remuxRadioButton.toggled.connect(self.virtualPreset.setRemuxEnabled)
        self._ui.encoderInfo.clicked.connect(self.showEncoderInfo)
        Utils.setIconViewer(self._ui.encoderInfo, Icons.HELP)
        self._ui.nextDownloadLabel.setVisible(self.isEditMode)
        self.updateFilenamePreview()

        # ── Recording conditions group (programmatic) ─────────────────────────
        condGroup = QtWidgets.QGroupBox(T("#Recording conditions"), parent=self)
        condForm  = QtWidgets.QFormLayout(condGroup)
        condForm.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        self._gameFilterEdit = QtWidgets.QLineEdit(parent=condGroup)
        self._gameFilterEdit.setPlaceholderText(T("#Any game"))
        self._gameFilterEdit.setText(self.virtualPreset.getGameFilter())
        self._gameFilterEdit.setToolTip(T("#Record only when the game name contains this text (case-insensitive). Leave empty to record any game."))
        condForm.addRow(T("#Game contains:"), self._gameFilterEdit)

        self._titleFilterEdit = QtWidgets.QLineEdit(parent=condGroup)
        self._titleFilterEdit.setPlaceholderText(T("#Any title"))
        self._titleFilterEdit.setText(self.virtualPreset.getTitleFilter())
        self._titleFilterEdit.setToolTip(T("#Record only when the stream title contains this text (case-insensitive). Leave empty to record any title."))
        condForm.addRow(T("#Title contains:"), self._titleFilterEdit)

        self._maxRecordingsSpin = QtWidgets.QSpinBox(parent=condGroup)
        self._maxRecordingsSpin.setRange(0, 9999)
        self._maxRecordingsSpin.setSpecialValueText(T("#Unlimited"))
        self._maxRecordingsSpin.setValue(self.virtualPreset.getMaxRecordings())
        self._maxRecordingsSpin.setToolTip(T("#Stop recording after this many streams (0 = unlimited). Resets when the app restarts."))
        condForm.addRow(T("#Max recordings:"), self._maxRecordingsSpin)

        # Insert before the last widget (save/cancel button row) in the dialog layout
        dialogLayout = self._ui.Dialog.layout() if hasattr(self._ui, "Dialog") else self.layout()
        dialogLayout.insertWidget(dialogLayout.count() - 1, condGroup)
        # ─────────────────────────────────────────────────────────────────────

    def channelChanged(self, text: str) -> None:
        channel = text.lower()
        self.virtualPreset.setChannel(channel)
        self.updateFilenamePreview()

    def reloadDirectory(self) -> None:
        self._ui.currentDirectory.setText(self.virtualPreset.directory)
        self._ui.currentDirectory.setToolTip(self.virtualPreset.directory)

    def askDirectory(self) -> None:
        newDirectory = Utils.askDirectory(self.virtualPreset.directory, parent=self)
        if newDirectory != None:
            self.virtualPreset.setDirectory(newDirectory)
            self.reloadDirectory()

    def filenameTemplateChanged(self, text: str) -> None:
        self.virtualPreset.setFilenameTemplate(text)
        self.updateFilenamePreview()

    def fileFormatChanged(self, text: str) -> None:
        self.virtualPreset.setFileFormat(text)
        self.updateFilenamePreview()

    def reloadFileFormat(self) -> None:
        self._ui.fileFormat.blockSignals(True)
        self._ui.fileFormat.clear()
        self._ui.fileFormat.addItems(self.virtualPreset.getAvailableFormats())
        self._ui.fileFormat.setCurrentText(self.virtualPreset.fileFormat)
        self._ui.fileFormat.blockSignals(False)

    def showFilenamePreviewInfo(self) -> None:
        Utils.info("information", T("#This is just a preview.\nSome values may be different from the actual ones. ({properties}, etc.)", properties=", ".join((f"{T('stream')} {T('id')}", T("title"), f"{T('channel')} {T('displayname')}"))), contentTranslate=False, parent=self)

    def preferredQualityChanged(self, index: int) -> None:
        self.virtualPreset.setPreferredQuality(index)
        self.reloadFileFormat()
        self.updateFilenamePreview()

    def preferredFrameRateChanged(self, index: int) -> None:
        self.virtualPreset.setPreferredFrameRate(index)
        self.updateFilenamePreview()

    def showPreferredResolutionOnlyInfo(self) -> None:
        Utils.info("information", "#Please note that certain video qualities (such as Source) may not be available immediately after a live broadcast begins.\nIf this option is disabled, it will automatically select and begin downloading the closest available quality.\nIf this option is enabled, it will wait until the selected quality is available.\n(Please be aware that if the selected quality continues to be unavailable, the download will not proceed.)", parent=self)

    def showAdBlockInfo(self) -> None:
        skipSegmentsInfo = T("#[Skip Segments]\n\nAds are skipped, but the stream during that time cannot be downloaded.\nIn this case, no alternative screen is shown, and it will directly connect to the scene after the ad, making the stream appear as if it's interrupted in the middle.")
        alternativeScreenInfo = T("#[Alternative Screen]\n\nDisplays an alternate screen instead of skipping ads.\nIn this case, the entire length of the stream is maintained, but some players might not play the video correctly.")
        Utils.info("information", f"{T('#If commercials are broadcast during this stream, they will be handled according to the following rules.')}\n\n{skipSegmentsInfo}\n\n\n{alternativeScreenInfo}", contentTranslate=False, parent=self)

    def showEncoderInfo(self) -> None:
        remuxInfo = T("#[Remux]\n\nThe file will be saved as a standard video file.\nThis involves a minor conversion process of the Transport Stream file to ensure its compatibility with standard players.\nThe quality of the video is retained, with only additional information about the video being modified for compatibility with standard players.")
        concatInfo = T("#[Concat]\n\nThis feature enables you to store Transport Stream file in its original form, without any conversion to ensure its compatibility with standard players.\nSince these files are typically designed for streaming, they may not play correctly on certain players.\nAdditionally, if commercials are broadcast during a live stream or parts are missing due to network issues, some players might not play the video correctly.")
        Utils.info("information", f"{remuxInfo}\n\n\n{concatInfo}", contentTranslate=False, parent=self)

    def createPreviewStream(self) -> TwitchGQLModels.Stream:
        return TwitchGQLModels.Stream({
            "id": "0",
            "title": "Stream Title",
            "game": {
                "displayName": "Just Chatting"
            },
            "broadcaster": {
                "login": self.virtualPreset.channel,
                "displayName": self.virtualPreset.channel
            },
            "createdAt": QtCore.QDateTime.currentDateTimeUtc().toString("yyyy-MM-ddTHH:mm:ssZ"),
            "viewersCount": 0
        })

    def createPreviewResolution(self) -> Resolution:
        return self.virtualPreset.selectResolution([
            Resolution("1080p60", "chunked", QtCore.QUrl()),
            Resolution("1080p30", "1080p30", QtCore.QUrl()),
            Resolution("720p60", "720p60", QtCore.QUrl()),
            Resolution("720p30", "720p30", QtCore.QUrl()),
            Resolution("480p", "480p", QtCore.QUrl()),
            Resolution("360p", "360p", QtCore.QUrl()),
            Resolution("160p", "160p", QtCore.QUrl()),
            Resolution("audio_only", "audio_only", QtCore.QUrl())
        ])

    def updateFilenamePreview(self) -> None:
        self._ui.filenamePreview.setText(FileNameGenerator.generateFileName(self.createPreviewStream(), self.createPreviewResolution(), filenameTemplate=f"{self.virtualPreset.filenameTemplate}.{self.virtualPreset.fileFormat}"))

    def savePreset(self) -> None:
        self.scheduledDownloadPreset.channel = self.virtualPreset.channel
        self.scheduledDownloadPreset.directory = self.virtualPreset.directory
        self.scheduledDownloadPreset.filenameTemplate = self.virtualPreset.filenameTemplate
        self.scheduledDownloadPreset.fileFormat = self.virtualPreset.fileFormat
        self.scheduledDownloadPreset.preferredQualityIndex = self.virtualPreset.preferredQualityIndex
        self.scheduledDownloadPreset.preferredFrameRateIndex = self.virtualPreset.preferredFrameRateIndex
        self.scheduledDownloadPreset.preferredResolutionOnly = self.virtualPreset.preferredResolutionOnly
        self.scheduledDownloadPreset.skipAds = self.virtualPreset.skipAds
        self.scheduledDownloadPreset.remux = self.virtualPreset.remux
        # Recording conditions
        self.scheduledDownloadPreset.setGameFilter(self._gameFilterEdit.text())
        self.scheduledDownloadPreset.setTitleFilter(self._titleFilterEdit.text())
        self.scheduledDownloadPreset.setMaxRecordings(self._maxRecordingsSpin.value())

    def getChannelFromText(self, text: str) -> str | None:
        parsedData = TwitchQueryParser.parseQuery(text)
        for mode, query in parsedData:
            if mode.isChannel():
                return query
        return None

    def accept(self) -> None:
        formCheck = []
        if self.virtualPreset.channel == "":
            formCheck.append(T("channel"))
        if self.virtualPreset.filenameTemplate == "":
            formCheck.append(T("filename-template"))
        if len(formCheck) != 0:
            formInfo = "\n".join(formCheck)
            Utils.info("warning", f"{T('#Some fields are empty.')}\n\n{formInfo}", contentTranslate=False, parent=self)
            return
        if not self.isEditMode:
            channel = self.getChannelFromText(self.virtualPreset.channel)
            if channel == None:
                Utils.info("error", "#Channel ID is invalid.", parent=self)
                return
            else:
                self.virtualPreset.channel = channel
        self.savePreset()
        self.scheduledDownloadPreset.saveOptionHistory()
        self.scheduledDownloadUpdated.emit(self.scheduledDownloadPreset)
        super().accept()