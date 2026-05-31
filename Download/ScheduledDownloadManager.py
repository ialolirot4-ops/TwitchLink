from Core import App
from Core.GlobalExceptions import Exceptions
from Services.Utils.Utils import Utils
from Services.Twitch.GQL import TwitchGQLAPI
from Services.Twitch.GQL import TwitchGQLModels
from Services.Twitch.Playback import TwitchPlaybackGenerator
from Services.Twitch.Playback import TwitchPlaybackModels
from Services.Twitch.EventSub.TwitchEventSub import EventSubEvent
from Services.Twitch.EventSub.TwitchEventSubEvents import SubscriptionTypes
from Services.FileNameLocker import FileNameLocker
from Download.DownloadInfo import DownloadInfo
from Download.Downloader.TwitchDownloader import TwitchDownloader
from Download.Downloader.Core.StreamDownloader import StreamDownloader
from Download.Downloader.Core.Engine.Config import Config
from Download.ScheduledDownloadPreset import ScheduledDownloadPreset
from Download.ScheduledDownloadEventSubManager import ScheduledDownloadEventSubSubscriber
from Ui.Components.Utils.FileNameGenerator import FileNameGenerator

from PyQt6 import QtCore

import uuid


class ScheduledDownloadStatus(QtCore.QObject):
    updated = QtCore.pyqtSignal()

    NONE = 0
    GENERATING_PLAYBACK = 1
    DOWNLOADING = 2
    ERROR = 3
    DOWNLOADER_ERROR = 4

    def __init__(self, parent: QtCore.QObject | None = None):
        super().__init__(parent=parent)
        self.setNone()

    def setNone(self) -> None:
        self._status = self.NONE
        self._error = None
        self.updated.emit()

    def setGeneratingPlayback(self) -> None:
        self._status = self.GENERATING_PLAYBACK
        self._error = None
        self.updated.emit()

    def setDownloading(self) -> None:
        self._status = self.DOWNLOADING
        self._error = None
        self.updated.emit()

    def setError(self, error: Exception) -> None:
        self._status = self.ERROR
        self._error = error
        self.updated.emit()

    def setDownloaderError(self, error: Exception) -> None:
        self._status = self.DOWNLOADER_ERROR
        self._error = error
        self.updated.emit()

    def isNone(self) -> bool:
        return self._status == self.NONE

    def isGeneratingPlayback(self) -> bool:
        return self._status == self.GENERATING_PLAYBACK

    def isDownloading(self) -> bool:
        return self._status == self.DOWNLOADING

    def isError(self) -> bool:
        return self._status == self.ERROR

    def isDownloaderError(self) -> bool:
        return self._status == self.DOWNLOADER_ERROR

    def getError(self) -> Exception | None:
        return self._error

    def cleanup(self) -> None:
        if self.isError() or self.isDownloaderError():
            self.setNone()


class ScheduledDownload(QtCore.QObject):
    activeChanged = QtCore.pyqtSignal()
    channelDataUpdateStarted = QtCore.pyqtSignal()
    channelDataUpdateFinished = QtCore.pyqtSignal()
    channelDataUpdated = QtCore.pyqtSignal()
    eventSubStateChanged = QtCore.pyqtSignal()
    downloaderCreated = QtCore.pyqtSignal(object, object)
    downloaderDestroyed = QtCore.pyqtSignal(object, object)

    STREAM_PREVIEW_IMAGE_URL_FORMAT = "https://static-cdn.jtvnw.net/previews-ttv/live_user_{login}-{{width}}x{{height}}.jpg"
    GAME_BOX_ART_URL_FORMAT = "https://static-cdn.jtvnw.net/ttv-boxart/{id}-{{width}}x{{height}}.jpg"

    def __init__(self, scheduledDownloadPreset: ScheduledDownloadPreset, parent: QtCore.QObject | None = None):
        super().__init__(parent=parent)
        self._blocked = True
        self.uuid = uuid.uuid4()
        self.preset = scheduledDownloadPreset
        self.channel = None
        self._eventSubSubscriber: ScheduledDownloadEventSubSubscriber | None = None
        self._updatingChannelData = False
        self._autoUpdateTimer = QtCore.QTimer(parent=self)
        self._autoUpdateTimer.setInterval(Config.CHANNEL_AUTO_UPDATE_INTERVAL)
        self._autoUpdateTimer.timeout.connect(self.updateChannelData)
        self.downloader: StreamDownloader | None = None
        self.status = ScheduledDownloadStatus(parent=self)
        self._recordingCount: int = 0   # incremented each time a download starts
        self.updateChannelData()

    def getId(self) -> uuid.UUID:
        return self.uuid

    def setBlocked(self, blocked: bool) -> None:
        if blocked != self.isBlocked():
            self._blocked = blocked
            self._syncEnabledState()
            if not self._blocked:
                self.updateChannelData()
            self.activeChanged.emit()

    def isBlocked(self) -> bool:
        return self._blocked

    def setEnabled(self, enabled: bool) -> None:
        if enabled != self.preset.isEnabled():
            self.preset.setEnabled(enabled)
            self.status.cleanup()
            self._syncEnabledState()
            self.activeChanged.emit()

    def isEnabled(self) -> bool:
        return self.preset.isEnabled()

    def isActive(self) -> bool:
        return not self.isBlocked() and self.isEnabled()

    def _syncEnabledState(self) -> None:
        if self.isChannelRetrieved():
            if self.isActive():
                self.connectEventSub()
                self.startDownloadIfOnline()
            else:
                self.disconnectEventSub()
                if self.status.isDownloading():
                    self.downloader.cancel()
                elif self.status.isError() or self.status.isDownloaderError():
                    self.status.setNone()
            self._syncAutoUpdate()

    def isChannelRetrieved(self) -> bool:
        return self.channel != None

    def isEventSubConnected(self) -> bool:
        return self._eventSubSubscriber != None

    def isSubscribed(self) -> bool:
        return self.isEventSubConnected() and self._eventSubSubscriber.isSubscribed()

    def isConnecting(self) -> bool:
        return self.isEventSubConnected() and self._eventSubSubscriber.hasPendingRequest()

    def connectEventSub(self) -> None:
        if not self.isEventSubConnected():
            self._eventSubSubscriber = App.ScheduledDownloadEventSubManager.subscribe(self.channel.id, key=self.getId())
            self._eventSubSubscriber.stateChanged.connect(self.eventSubStateChanged)
            self._eventSubSubscriber.eventReceived.connect(self.eventSubEventHandler)
            self.eventSubStateChanged.emit()

    def disconnectEventSub(self) -> None:
        if self.isEventSubConnected():
            App.ScheduledDownloadEventSubManager.unsubscribe(self.channel.id, key=self.getId())
            self._eventSubSubscriber = None
            self.eventSubStateChanged.emit()

    def _syncAutoUpdate(self) -> None:
        if self.isActive() and self.isChannelRetrieved() and self.isOffline():
            self._autoUpdateTimer.start()
        else:
            self._autoUpdateTimer.stop()

    def canStartDownload(self) -> bool:
        return self.isActive() and self.isChannelRetrieved() and self.isOnline() and not self.status.isGeneratingPlayback() and not self.status.isDownloading()

    def isUpdatingChannelData(self) -> bool:
        return self._updatingChannelData

    def updateChannelData(self) -> None:
        if not self.isUpdatingChannelData():
            self._updatingChannelData = True
            self.channelDataUpdateStarted.emit()
            if self.isChannelRetrieved():
                App.TwitchGQL.getChannel(id=self.channel.id).finished.connect(self._channelDataUpdateResult)
            else:
                App.TwitchGQL.getChannel(login=self.preset.channel).finished.connect(self._channelDataUpdateResult)

    def _channelDataUpdateResult(self, response: TwitchGQLAPI.TwitchGQLResponse) -> None:
        if response.getError() == None:
            isFirst = not self.isChannelRetrieved()
            self.channel = response.getData()
            self.channelDataUpdated.emit()
            if isFirst:
                self._syncEnabledState()
            else:
                self.startDownloadIfOnline()
        self._updatingChannelData = False
        self.channelDataUpdateFinished.emit()

    def setOnline(self) -> None:
        if self.isOffline():
            self.channel.stream = TwitchGQLModels.Stream({
                "title": self.channel.lastBroadcast.title,
                "previewImageURL": "" if self.channel.login == "" else self.STREAM_PREVIEW_IMAGE_URL_FORMAT.format(login=self.channel.login),
                "broadcaster": {
                    "id": self.channel.id,
                    "login": self.channel.login,
                    "displayName": self.channel.displayName
                }
            })
            self.channel.stream.game = self.channel.lastBroadcast.game
            self.channel.stream.createdAt = QtCore.QDateTime.currentDateTimeUtc()
            self.channelDataUpdated.emit()
            self._syncAutoUpdate()

    def setOffline(self) -> None:
        if self.isOnline():
            self.channel.stream = None
            self.channelDataUpdated.emit()
            self._syncAutoUpdate()

    def isOnline(self) -> bool:
        return self.channel.stream != None

    def isOffline(self) -> bool:
        return not self.isOnline()

    def eventSubEventHandler(self, event: EventSubEvent) -> None:
        sub_type = event.subscription_type
        data     = event.data

        if sub_type == SubscriptionTypes.StreamOnline:
            self.setOnline()
            # "started_at" es ISO 8601, ej: "2024-01-01T00:00:00Z"
            started_at = QtCore.QDateTime.fromString(
                data.get("started_at", ""),
                QtCore.Qt.DateFormat.ISODate
            )
            if started_at.isValid() and self.isOnline():
                self.channel.stream.createdAt = started_at.toUTC()

        elif sub_type == SubscriptionTypes.StreamOffline:
            self.setOffline()

        elif sub_type == SubscriptionTypes.ChannelUpdate:
            self.channel.lastBroadcast.title = data.get("title", "")
            category_id = data.get("category_id", "")
            if not category_id:
                gameData = {}
            else:
                gameData = {
                    "id":          category_id,
                    "name":        data.get("category_name", ""),
                    "boxArtURL":   self.GAME_BOX_ART_URL_FORMAT.format(id=category_id),
                    "displayName": data.get("category_name", ""),
                }
            self.channel.lastBroadcast.game = TwitchGQLModels.Game(gameData)
            if self.isOnline():
                self.channel.stream.title = self.channel.lastBroadcast.title
                self.channel.stream.game  = self.channel.lastBroadcast.game

        self.channelDataUpdated.emit()
        self.startDownloadIfOnline()

    def startDownloadIfOnline(self) -> None:
        if self.canStartDownload():
            condResult = self._matchesConditions()
            if condResult is True:
                self.generateStreamPlayback()
            else:
                # Conditions not met — log the reason but stay subscribed
                self.logger.info(f"[ScheduledDownload] Conditions not met: {condResult}")

    def _matchesConditions(self) -> bool | str:
        """
        Check user-configured recording conditions against the live stream.

        Returns True if all conditions pass, or a human-readable reason string
        if any condition fails.
        """
        stream = self.channel.stream if self.isChannelRetrieved() else None
        if stream is None:
            return "stream data unavailable"

        # Game filter
        gameFilter = self.preset.getGameFilter()
        if gameFilter:
            gameName = (stream.game.name if stream.game else "").lower()
            if gameFilter.lower() not in gameName:
                return f"game '{stream.game.name if stream.game else ''}' does not match filter '{gameFilter}'"

        # Title filter
        titleFilter = self.preset.getTitleFilter()
        if titleFilter:
            title = (stream.title or "").lower()
            if titleFilter.lower() not in title:
                return f"title '{stream.title}' does not match filter '{titleFilter}'"

        # Max recordings
        maxRec = self.preset.getMaxRecordings()
        if maxRec > 0 and self._recordingCount >= maxRec:
            return f"max recordings ({maxRec}) reached"

        return True

    def generateStreamPlayback(self) -> None:
        try:
            App.ContentManager.checkRestriction(self.channel.stream)
        except Exception as e:
            self.status.setError(e)
        else:
            self.status.setGeneratingPlayback()
            TwitchPlaybackGenerator.TwitchStreamPlaybackGenerator(self.channel.stream.broadcaster.login, parent=self).finished.connect(self._processStreamPlaybackResult)

    def _processStreamPlaybackResult(self, generator: TwitchPlaybackGenerator.TwitchStreamPlaybackGenerator) -> None:
        if generator.getError() == None:
            if self.isActive() and self.isOnline():
                streamPlayback = generator.getData()
                try:
                    self.createDownloader(streamPlayback)
                except Exception as e:
                    self.status.setError(e)
            else:
                self.status.setNone()
        elif isinstance(generator.getError(), TwitchPlaybackGenerator.Exceptions.ChannelIsOffline):
            self.setOffline()
            self.status.setNone()
        else:
            if self.isActive():
                self.status.setError(generator.getError())
            else:
                self.status.setNone()

    def createDownloader(self, playback: TwitchPlaybackModels.TwitchStreamPlayback) -> None:
        downloadInfo = DownloadInfo(self.channel.stream, playback)
        downloadInfo.setDirectory(self.preset.directory)
        selectedResolution = self.preset.selectResolution(playback.getResolutions())
        downloadInfo.setResolution(playback.getResolutions().index(selectedResolution))
        downloadInfo.setAbsoluteFileName(Utils.createUniqueFile(downloadInfo.directory, FileNameGenerator.generateFileName(self.channel.stream, selectedResolution, filenameTemplate=self.preset.filenameTemplate), self.preset.fileFormat, exclude=FileNameLocker.getLockedFiles()))
        if not playback.token.hideAds:
            downloadInfo.setSkipAdsEnabled(self.preset.isSkipAdsEnabled())
        downloadInfo.setRemuxEnabled(self.preset.isRemuxEnabled())
        self._recordingCount += 1
        self.downloader = TwitchDownloader.create(downloadInfo, parent=self)
        self.downloader.finished.connect(self.downloadResultHandler)
        self.downloaderCreated.emit(self, self.downloader)
        self.status.setDownloading()
        self.downloader.start()

    def downloadResultHandler(self, downloader: StreamDownloader) -> None:
        error = downloader.status.getError()
        if error == None:
            self.setOffline()
            self.status.setNone()
        elif self.isActive():
            self.status.setDownloaderError(error)
        else:
            self.status.setNone()
        downloader.deleteLater()
        self.downloader = None
        self.downloaderDestroyed.emit(self, downloader)
        if isinstance(error, Exceptions.NetworkError):
            self.startDownloadIfOnline()

    def isDownloading(self) -> bool:
        return self.downloader != None

    def __del__(self):
        try:
            if self.isEventSubConnected():
                App.ScheduledDownloadEventSubManager.unsubscribe(self.channel.id, key=self.getId())
        except:
            pass


class ScheduledDownloadManager(QtCore.QObject):
    blockedChangedSignal = QtCore.pyqtSignal(bool)
    enabledChangedSignal = QtCore.pyqtSignal(bool)
    createdSignal = QtCore.pyqtSignal(object)
    destroyedSignal = QtCore.pyqtSignal(object)
    downloaderCreatedSignal = QtCore.pyqtSignal(object, object)
    downloaderDestroyedSignal = QtCore.pyqtSignal(object, object)
    downloaderCountChangedSignal = QtCore.pyqtSignal(int)

    def __init__(self, parent: QtCore.QObject | None = None):
        super().__init__(parent=parent)
        self._blocked = True
        self._enabled = False
        self.scheduledDownloads: dict[uuid.UUID, ScheduledDownload] = {}
        self.runningScheduledDownloads: list[ScheduledDownload] = []
        self._syncState()

    def setBlocked(self, blocked: bool) -> None:
        if blocked != self._blocked:
            self._blocked = blocked
            self._syncState()
            self.blockedChangedSignal.emit(self._blocked)

    def isBlocked(self) -> bool:
        return self._blocked

    def setEnabled(self, enabled: bool) -> None:
        if enabled != self._enabled:
            self._enabled = enabled
            self._syncState()
            self.enabledChangedSignal.emit(self._enabled)

    def isEnabled(self) -> bool:
        return self._enabled

    def _syncState(self) -> None:
        self._syncScheduledDownloadsBlockedState()
        self._updateEventSubState()

    def _syncScheduledDownloadsBlockedState(self) -> None:
        blocked = not self.isEnabled() or self.isBlocked()
        for scheduledDownload in self.scheduledDownloads.values():
            scheduledDownload.setBlocked(blocked)

    def _updateEventSubState(self) -> None:
        if not self.isBlocked() and self.isEnabled() and any(scheduledDownload.isEnabled() for scheduledDownload in self.scheduledDownloads.values()):
            if not App.ScheduledDownloadEventSubManager.isOpened():
                App.ScheduledDownloadEventSubManager.open()
        else:
            if App.ScheduledDownloadEventSubManager.isOpened():
                App.ScheduledDownloadEventSubManager.close()

    def setPresets(self, presetList: list[ScheduledDownloadPreset]) -> None:
        for scheduledDownload in self.getScheduledDownloads():
            self.remove(scheduledDownload.getId())
        for scheduledDownloadPreset in presetList:
            self.create(scheduledDownloadPreset)

    def getPresets(self) -> list[ScheduledDownloadPreset]:
        return [scheduledDownload.preset for scheduledDownload in self.getScheduledDownloads()]

    def create(self, scheduledDownloadPreset: ScheduledDownloadPreset) -> uuid.UUID:
        scheduledDownload = ScheduledDownload(scheduledDownloadPreset, parent=self)
        scheduledDownload.activeChanged.connect(self._updateEventSubState)
        scheduledDownload.downloaderCreated.connect(self.downloaderCreated)
        scheduledDownload.downloaderDestroyed.connect(self.downloaderDestroyed)
        scheduledDownloadId = scheduledDownload.getId()
        self.scheduledDownloads[scheduledDownloadId] = scheduledDownload
        self.createdSignal.emit(scheduledDownloadId)
        self._syncState()
        return scheduledDownloadId

    def downloaderCreated(self, scheduledDownload: ScheduledDownload, downloader: StreamDownloader) -> None:
        self.runningScheduledDownloads.append(scheduledDownload)
        self.downloaderCountChangedSignal.emit(len(self.getRunningDownloaders()))
        self.downloaderCreatedSignal.emit(scheduledDownload, downloader)

    def downloaderDestroyed(self, scheduledDownload: ScheduledDownload, downloader: StreamDownloader) -> None:
        self.runningScheduledDownloads.remove(scheduledDownload)
        self.downloaderCountChangedSignal.emit(len(self.getRunningDownloaders()))
        self.downloaderDestroyedSignal.emit(scheduledDownload, downloader)

    def get(self, scheduledDownloadId: uuid.UUID) -> ScheduledDownload:
        return self.scheduledDownloads[scheduledDownloadId]

    def remove(self, scheduledDownloadId: uuid.UUID) -> None:
        if not self.scheduledDownloads[scheduledDownloadId].isDownloading():
            self.scheduledDownloads.pop(scheduledDownloadId).deleteLater()
            self.destroyedSignal.emit(scheduledDownloadId)
            self._syncState()

    def cancelAll(self) -> None:
        for downloader in self.getRunningDownloaders():
            downloader.cancel()

    def getScheduledDownloadKeys(self) -> list[uuid.UUID]:
        return list(self.scheduledDownloads.keys())

    def getScheduledDownloads(self) -> list[ScheduledDownload]:
        return list(self.scheduledDownloads.values())

    def getRunningScheduledDownloads(self) -> list[ScheduledDownload]:
        return self.runningScheduledDownloads

    def getRunningDownloaders(self) -> list[StreamDownloader]:
        return [scheduledDownloads.downloader for scheduledDownloads in self.getRunningScheduledDownloads()]

    def isDownloaderRunning(self) -> bool:
        return len(self.getRunningDownloaders()) != 0