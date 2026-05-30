"""
Services/Favorites/FavoritesManager.py
Manager central del sistema de canales favoritos.
"""
from __future__ import annotations
from AppData.EncoderDecoder import Serializable
from Services.Twitch.GQL import TwitchGQLModels
from PyQt6 import QtCore
import enum
import datetime


class FavoriteChannel(Serializable):
    SERIALIZABLE_STRICT_MODE = False

    def __init__(self, login="", display_name="", profile_image_url="", added_at=""):
        self.login             = login.lower().strip()
        self.display_name      = display_name or login
        self.profile_image_url = profile_image_url
        self.added_at          = added_at or datetime.datetime.utcnow().isoformat()
        self._init_runtime()

    def _init_runtime(self):
        self._is_live        = False
        self._stream         = None
        self._channel_data   = None
        self._is_partner     = False
        self._is_affiliate   = False
        self._is_staff       = False
        self._followers      = 0
        self._offline_image  = ""
        self._last_broadcast = None

    def __setup__(self):
        self._init_runtime()

    # ── Runtime properties ────────────────────────────────────────────────────
    @property
    def is_live(self) -> bool:
        return self._is_live

    @property
    def stream(self):
        return self._stream

    @property
    def is_partner(self) -> bool:
        return self._is_partner

    @property
    def is_affiliate(self) -> bool:
        return self._is_affiliate

    @property
    def is_staff(self) -> bool:
        return self._is_staff

    @property
    def followers(self) -> int:
        return self._followers

    @property
    def offline_image(self) -> str:
        return self._offline_image

    @property
    def last_broadcast(self):
        return self._last_broadcast

    @property
    def viewers(self) -> int:
        return self._stream.viewersCount if self._stream else 0

    @property
    def game_name(self) -> str:
        if self._stream and self._stream.game:
            return self._stream.game.displayName or self._stream.game.name or ""
        return ""

    @property
    def stream_title(self) -> str:
        return self._stream.title if self._stream else ""

    @property
    def box_art_url(self) -> str:
        if self._stream and self._stream.game:
            return self._stream.game.boxArtURL or ""
        if self._last_broadcast and self._last_broadcast.game:
            return self._last_broadcast.game.boxArtURL or ""
        return ""

    @property
    def followers_str(self) -> str:
        f = self._followers
        if not f:
            return ""
        if f >= 1_000_000:
            return f"{f/1_000_000:.1f}M seguidores"
        if f >= 1_000:
            return f"{f/1_000:.1f}K seguidores"
        return f"{f:,} seguidores"

    @property
    def last_broadcast_str(self) -> str:
        if not self._last_broadcast:
            return ""
        dt = self._last_broadcast.startedAt
        if not dt or not dt.isValid():
            return ""
        secs = dt.secsTo(QtCore.QDateTime.currentDateTimeUtc())
        if secs < 0:
            return ""
        if secs < 3600:
            m = secs // 60
            return f"Hace {m} min" if m > 0 else "Hace unos segundos"
        if secs < 86400:
            h = secs // 3600
            return f"Hace {h}h"
        d = secs // 86400
        if d == 1:
            return "Hace 1 día"
        if d < 30:
            return f"Hace {d} días"
        m2 = d // 30
        return f"Hace {m2} mes{'es' if m2>1 else ''}"

    @property
    def twitch_url(self) -> str:
        return f"https://www.twitch.tv/{self.login}"

    def update_from_api(self, channel: TwitchGQLModels.Channel) -> bool:
        was_live             = self._is_live
        self._channel_data   = channel
        self._stream         = channel.stream
        self._is_live        = channel.stream is not None and channel.stream.isLive()
        self.display_name    = channel.displayName or self.display_name
        self.profile_image_url = channel.profileImageURL or self.profile_image_url
        self._is_partner     = channel.isPartner
        self._is_affiliate   = channel.isAffiliate
        self._is_staff       = channel.isStaff
        self._followers      = channel.followers
        self._offline_image  = channel.offlineImageURL or ""
        self._last_broadcast = channel.lastBroadcast
        return (not was_live) and self._is_live

    def __eq__(self, other):
        if isinstance(other, FavoriteChannel):
            return self.login == other.login
        if isinstance(other, str):
            return self.login == other.lower()
        return False

    def __hash__(self):
        return hash(self.login)


class SortCriteria(enum.Enum):
    STATUS_THEN_VIEWERS = "status_viewers"
    ALPHABETICAL_ASC    = "alpha_asc"
    ALPHABETICAL_DESC   = "alpha_desc"
    VIEWERS_DESC        = "viewers_desc"
    RECENTLY_ADDED      = "recently_added"
    OLDEST_ADDED        = "oldest_added"

    @property
    def label(self) -> str:
        return {
            self.STATUS_THEN_VIEWERS: "Estado → Viewers",
            self.ALPHABETICAL_ASC:    "Nombre (A → Z)",
            self.ALPHABETICAL_DESC:   "Nombre (Z → A)",
            self.VIEWERS_DESC:        "Viewers (mayor primero)",
            self.RECENTLY_ADDED:      "Agregado recientemente",
            self.OLDEST_ADDED:        "Agregado hace más tiempo",
        }[self]


class _PollWorker(QtCore.QThread):
    channelUpdated = QtCore.pyqtSignal(str, object)
    finished       = QtCore.pyqtSignal()

    def __init__(self, logins: list[str], parent=None):
        super().__init__(parent=parent)
        self._logins = list(logins)

    def run(self):
        from Core import App
        for login in self._logins:
            if self.isInterruptionRequested():
                break
            try:
                response   = App.TwitchGQL.getChannel(login=login)
                result_box: list = []
                loop       = QtCore.QEventLoop()

                def on_finished(resp, _b=result_box, _l=loop):
                    _b.append(getattr(resp, "_data", None))
                    _l.quit()

                response.finished.connect(on_finished, QtCore.Qt.ConnectionType.DirectConnection)
                timer = QtCore.QTimer()
                timer.setSingleShot(True)
                timer.setInterval(12_000)
                timer.timeout.connect(loop.quit)
                timer.start()
                loop.exec()
                timer.stop()

                self.channelUpdated.emit(login, result_box[0] if result_box else None)
            except Exception:
                self.channelUpdated.emit(login, None)
        self.finished.emit()


class FavoritesManager(QtCore.QObject):
    channelAdded      = QtCore.pyqtSignal(object)
    channelRemoved    = QtCore.pyqtSignal(str)
    channelUpdated    = QtCore.pyqtSignal(object)
    channelWentLive   = QtCore.pyqtSignal(object)
    liveCountChanged  = QtCore.pyqtSignal(int)
    sortCriteriaChanged = QtCore.pyqtSignal(object)
    pollStarted       = QtCore.pyqtSignal()
    pollFinished      = QtCore.pyqtSignal()
    listReordered     = QtCore.pyqtSignal()

    POLL_INTERVAL_MS  = 60_000
    MIN_POLL_INTERVAL = 30_000

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._channels: list[FavoriteChannel] = []
        self._sort     = SortCriteria.STATUS_THEN_VIEWERS
        self._worker: _PollWorker | None = None
        self._initializing = True
        self._timer    = QtCore.QTimer(self)
        self._timer.setInterval(self.POLL_INTERVAL_MS)
        self._timer.timeout.connect(self.poll)
        self._timer.start()

    # ── Persistencia ──────────────────────────────────────────────────────────
    def load_from_data(self, data: list[dict]) -> None:
        self._channels.clear()
        for item in data:
            ch = FavoriteChannel(
                login=item.get("login", ""),
                display_name=item.get("display_name", ""),
                profile_image_url=item.get("profile_image_url", ""),
                added_at=item.get("added_at", ""),
            )
            self._channels.append(ch)
        QtCore.QTimer.singleShot(2_000, self.poll)

    def to_data(self) -> list[dict]:
        return [
            {"login": ch.login, "display_name": ch.display_name,
             "profile_image_url": ch.profile_image_url, "added_at": ch.added_at}
            for ch in self._channels
        ]

    # ── API pública ───────────────────────────────────────────────────────────
    def channels(self) -> list[FavoriteChannel]:
        return self._apply_sort(list(self._channels))

    def raw_channels(self) -> list[FavoriteChannel]:
        return list(self._channels)

    def live_count(self) -> int:
        return sum(1 for ch in self._channels if ch.is_live)

    def contains(self, login: str) -> bool:
        return login.lower() in (ch.login for ch in self._channels)

    def get(self, login: str) -> FavoriteChannel | None:
        login = login.lower()
        return next((ch for ch in self._channels if ch.login == login), None)

    def add(self, login: str, display_name: str = "", profile_image_url: str = "") -> FavoriteChannel | None:
        if self.contains(login):
            return None
        ch = FavoriteChannel(login=login, display_name=display_name or login,
                             profile_image_url=profile_image_url)
        self._channels.append(ch)
        self.channelAdded.emit(ch)
        self._save()
        QtCore.QTimer.singleShot(300, lambda: self._poll_single(ch.login))
        return ch

    def remove(self, login: str) -> bool:
        login = login.lower()
        for i, ch in enumerate(self._channels):
            if ch.login == login:
                self._channels.pop(i)
                self.channelRemoved.emit(login)
                self._save()
                self.liveCountChanged.emit(self.live_count())
                return True
        return False

    def set_sort(self, criteria: SortCriteria) -> None:
        if criteria != self._sort:
            self._sort = criteria
            self.sortCriteriaChanged.emit(criteria)
            self._save()

    def sort_criteria(self) -> SortCriteria:
        return self._sort

    # ── Polling ───────────────────────────────────────────────────────────────
    def poll(self) -> None:
        if not self._channels or (self._worker and self._worker.isRunning()):
            return
        logins = [ch.login for ch in self._channels]
        self._worker = _PollWorker(logins, parent=self)
        self._worker.channelUpdated.connect(self._on_channel_updated)
        self._worker.finished.connect(self._on_poll_finished)
        self.pollStarted.emit()
        self._worker.start()

    def poll_now(self) -> None:
        self._timer.stop()
        self.poll()
        self._timer.start()

    # ── Internos ──────────────────────────────────────────────────────────────
    def _poll_single(self, login: str) -> None:
        from Core import App
        try:
            response = App.TwitchGQL.getChannel(login=login)
            def on_done(resp, _l=login):
                ch_data = getattr(resp, "_data", None)
                if isinstance(ch_data, TwitchGQLModels.Channel):
                    self._process_update(_l, ch_data)
            response.finished.connect(on_done)
        except Exception:
            pass

    def _on_channel_updated(self, login: str, channel) -> None:
        if isinstance(channel, TwitchGQLModels.Channel):
            self._process_update(login, channel)

    def _process_update(self, login: str, channel: TwitchGQLModels.Channel) -> None:
        ch = self.get(login)
        if ch is None:
            return
        went_live = ch.update_from_api(channel)
        self.channelUpdated.emit(ch)
        if went_live and not self._initializing:
            self.channelWentLive.emit(ch)
            self._notify_live(ch)
        self.liveCountChanged.emit(self.live_count())

    def _on_poll_finished(self) -> None:
        self._initializing = False
        # Liberar el QThread anterior para evitar acumulación en sesiones largas
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
        self.pollFinished.emit()
        self.liveCountChanged.emit(self.live_count())

    def _notify_live(self, ch: FavoriteChannel) -> None:
        """Notificación nativa de Windows via QSystemTrayIcon."""
        from Core import App
        from Services.Utils.OSUtils import OSUtils
        try:
            if not App.Preferences.general.isNotifyEnabled():
                return
            viewers_str = f"  •  {ch.viewers:,} espectadores" if ch.viewers else ""
            lines = [f"twitch.tv/{ch.login}{viewers_str}"]
            if ch.game_name:
                lines.append(ch.game_name)
            if ch.stream_title:
                t = ch.stream_title[:100] + "…" if len(ch.stream_title) > 100 else ch.stream_title
                lines.append(t)
            # Capturar la URL en el closure para que no dependa de ch al momento del click
            channel_url = ch.twitch_url
            App.Instance.notification.toastMessage(
                title   = f"🔴  {ch.display_name} está en LIVE",
                message = "\n".join(lines),
                action  = lambda url=channel_url: OSUtils.openUrl(url),
            )
        except Exception:
            pass

    def _apply_sort(self, lst: list[FavoriteChannel]) -> list[FavoriteChannel]:
        s = self._sort
        if s == SortCriteria.STATUS_THEN_VIEWERS:
            return sorted(lst, key=lambda c: (not c.is_live, -c.viewers, c.display_name.lower()))
        if s == SortCriteria.ALPHABETICAL_ASC:
            return sorted(lst, key=lambda c: c.display_name.lower())
        if s == SortCriteria.ALPHABETICAL_DESC:
            return sorted(lst, key=lambda c: c.display_name.lower(), reverse=True)
        if s == SortCriteria.VIEWERS_DESC:
            return sorted(lst, key=lambda c: (-c.viewers, c.display_name.lower()))
        if s == SortCriteria.RECENTLY_ADDED:
            return sorted(lst, key=lambda c: c.added_at, reverse=True)
        if s == SortCriteria.OLDEST_ADDED:
            return sorted(lst, key=lambda c: c.added_at)
        return lst

    def _save(self) -> None:
        from Core import App
        try:
            App.Preferences.favorites.set_channels(self.to_data())
            App.Preferences.favorites.set_sort(self._sort.value)
            App.Preferences.save()
        except Exception:
            pass
