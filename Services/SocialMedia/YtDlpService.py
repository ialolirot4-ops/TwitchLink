"""
YtDlpService.py — Servicio central para descargas multi-plataforma
Soporta: YouTube, TikTok, Instagram (videos, reels, historias, IGTV),
         Twitter/X, Facebook, Twitch clips externos, y +1800 sitios más.
"""

from PyQt6 import QtCore

import yt_dlp
import os
import re
import threading


# ---------------------------------------------------------------------------
# Constantes de plataforma
# ---------------------------------------------------------------------------

class Platform:
    YOUTUBE   = "youtube"
    TIKTOK    = "tiktok"
    INSTAGRAM = "instagram"
    TWITTER   = "twitter"
    FACEBOOK  = "facebook"
    TWITCH    = "twitch"
    UNKNOWN   = "unknown"

    YOUTUBE_DOMAINS   = ("youtube.com", "youtu.be", "music.youtube.com")
    TIKTOK_DOMAINS    = ("tiktok.com", "vm.tiktok.com")
    INSTAGRAM_DOMAINS = ("instagram.com", "instagr.am")
    TWITTER_DOMAINS   = ("twitter.com", "x.com", "t.co")
    FACEBOOK_DOMAINS  = ("facebook.com", "fb.com", "fb.watch")
    TWITCH_DOMAINS    = ("twitch.tv", "clips.twitch.tv")

    @classmethod
    def detect(cls, url: str) -> str:
        url_lower = url.lower()
        for domain in cls.YOUTUBE_DOMAINS:
            if domain in url_lower:
                return cls.YOUTUBE
        for domain in cls.TIKTOK_DOMAINS:
            if domain in url_lower:
                return cls.TIKTOK
        for domain in cls.INSTAGRAM_DOMAINS:
            if domain in url_lower:
                return cls.INSTAGRAM
        for domain in cls.TWITTER_DOMAINS:
            if domain in url_lower:
                return cls.TWITTER
        for domain in cls.FACEBOOK_DOMAINS:
            if domain in url_lower:
                return cls.FACEBOOK
        for domain in cls.TWITCH_DOMAINS:
            if domain in url_lower:
                return cls.TWITCH
        return cls.UNKNOWN

    @classmethod
    def displayName(cls, platform: str) -> str:
        names = {
            cls.YOUTUBE: "YouTube",
            cls.TIKTOK: "TikTok",
            cls.INSTAGRAM: "Instagram",
            cls.TWITTER: "Twitter / X",
            cls.FACEBOOK: "Facebook",
            cls.TWITCH: "Twitch",
            cls.UNKNOWN: "Web",
        }
        return names.get(platform, "Desconocido")


# ---------------------------------------------------------------------------
# Modelo de información de descarga social
# ---------------------------------------------------------------------------

class SocialMediaInfo:
    """Metadatos extraídos por yt-dlp antes de descargar."""

    def __init__(self, data: dict):
        self.url          = data.get("webpage_url", "")
        self.title        = data.get("title") or data.get("description") or "Sin título"
        self.uploader     = data.get("uploader") or data.get("channel") or "Desconocido"
        self.platform     = Platform.detect(self.url)
        self.duration     = data.get("duration")          # segundos, puede ser None
        self.thumbnail    = data.get("thumbnail")
        self.description  = data.get("description", "")
        self.like_count   = data.get("like_count")
        self.view_count   = data.get("view_count")
        self.upload_date  = data.get("upload_date")       # "YYYYMMDD"
        self.is_live      = data.get("is_live", False)
        self.formats      = data.get("formats", [])
        self.entries      = data.get("entries")            # playlist / historias
        self.is_playlist  = self.entries is not None

    @property
    def duration_str(self) -> str:
        if self.duration is None:
            return "Desconocida"
        h, rem = divmod(int(self.duration), 3600)
        m, s   = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

    @property
    def available_resolutions(self) -> list[str]:
        """Resoluciones de video únicas disponibles (más alta primero)."""
        seen = set()
        result = []
        for f in sorted(self.formats, key=lambda x: x.get("height") or 0, reverse=True):
            h = f.get("height")
            if h and h not in seen and f.get("vcodec") != "none":
                seen.add(h)
                result.append(f"{h}p")
        if not result:
            result = ["Mejor calidad disponible"]
        return result


# ---------------------------------------------------------------------------
# Configuraciones de descarga
# ---------------------------------------------------------------------------

class DownloadConfig:
    """Encapsula todas las opciones de una descarga social."""

    # Formatos de video
    VIDEO_FORMATS = ["mp4", "mkv", "webm", "mov", "avi"]
    # Formatos de audio
    AUDIO_FORMATS = ["mp3", "aac", "opus", "m4a", "flac", "wav"]

    def __init__(self):
        self.url: str          = ""
        self.output_dir: str   = os.path.expanduser("~/Downloads")
        self.audio_only: bool  = False
        self.format_pref: str  = "mp4"          # video
        self.audio_format: str = "mp3"          # audio only
        self.quality: str      = "best"         # "best", "worst", "1080p", "720p"…
        self.embed_subs: bool  = False
        self.embed_thumb: bool = True
        self.playlist: bool    = False          # descargar toda la playlist
        self.playlist_start: int = 1
        self.playlist_end: int | None = None
        self.cookies_from_browser: str | None = None  # "chrome", "firefox"…
        self.rate_limit: str | None = None      # ej. "5M"
        self.filename_template: str = "%(uploader)s - %(title)s.%(ext)s"
        self.proxy: str | None = None
        self.metadata: bool    = True           # embed metadata
        self.chapters: bool    = True           # embed chapters (YT)

    def build_ydl_opts(self, progress_hook=None) -> dict:
        """Convierte la config en opciones de yt-dlp."""

        # ------ Selección de formato ------
        if self.audio_only:
            format_str = "bestaudio/best"
            postprocessors = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": self.audio_format,
                    "preferredquality": "320" if self.audio_format == "mp3" else "0",
                }
            ]
            if self.embed_thumb:
                postprocessors.append({"key": "EmbedThumbnail"})
            if self.metadata:
                postprocessors.append({"key": "FFmpegMetadata", "add_metadata": True})
        else:
            height_map = {
                "best":  "bestvideo+bestaudio/best",
                "worst": "worstvideo+worstaudio/worst",
                "2160p": "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
                "1440p": "bestvideo[height<=1440]+bestaudio/best[height<=1440]",
                "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
                "720p":  "bestvideo[height<=720]+bestaudio/best[height<=720]",
                "480p":  "bestvideo[height<=480]+bestaudio/best[height<=480]",
                "360p":  "bestvideo[height<=360]+bestaudio/best[height<=360]",
            }
            format_str = height_map.get(self.quality, "bestvideo+bestaudio/best")
            postprocessors = [
                {
                    "key": "FFmpegVideoConvertor",
                    "preferedformat": self.format_pref,
                }
            ]
            if self.embed_subs:
                postprocessors.append({"key": "FFmpegEmbedSubtitle"})
            if self.embed_thumb:
                postprocessors.append({"key": "EmbedThumbnail"})
            if self.metadata or self.chapters:
                postprocessors.append({
                    "key": "FFmpegMetadata",
                    "add_metadata": bool(self.metadata),
                    "add_chapters": bool(self.chapters),
                })

        opts = {
            "format": format_str,
            "outtmpl": os.path.join(self.output_dir, self.filename_template),
            "postprocessors": postprocessors,
            "writethumbnail": self.embed_thumb,
            "writesubtitles": self.embed_subs,
            "embedsubtitles": self.embed_subs,
            "noplaylist": not self.playlist,
            "playliststart": self.playlist_start,
            "merge_output_format": self.format_pref if not self.audio_only else None,
            "ignoreerrors": True,
            "retries": 5,
            "fragment_retries": 5,
        }

        if progress_hook:
            opts["progress_hooks"] = [progress_hook]
        if self.playlist_end:
            opts["playlistend"] = self.playlist_end
        if self.cookies_from_browser:
            opts["cookiesfrombrowser"] = (self.cookies_from_browser,)
        if self.rate_limit:
            opts["ratelimit"] = self._parse_rate(self.rate_limit)
        if self.proxy:
            opts["proxy"] = self.proxy

        return opts

    @staticmethod
    def _parse_rate(rate_str: str) -> int:
        """Convierte "5M" → 5242880, "500K" → 512000."""
        m = re.match(r"(\d+(?:\.\d+)?)\s*([KMG]?)", rate_str.upper())
        if not m:
            return 0
        val, unit = float(m.group(1)), m.group(2)
        return int(val * {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3}.get(unit, 1))


# ---------------------------------------------------------------------------
# Servicio Qt para extracción de info y descarga
# ---------------------------------------------------------------------------

class InfoExtractorWorker(QtCore.QThread):
    """Extrae metadatos en un hilo separado para no bloquear la UI."""
    finished = QtCore.pyqtSignal(object)   # SocialMediaInfo
    error    = QtCore.pyqtSignal(str)

    def __init__(self, url: str, cookies_browser: str | None = None, parent=None):
        super().__init__(parent=parent)
        self.url            = url
        self.cookies_browser = cookies_browser

    def run(self):
        opts = {
            "quiet": True,
            "no_warnings": True,
            # extract_flat omitido intencionalmente: con "in_playlist" yt-dlp
            # devuelve solo un esqueleto sin thumbnail, duración ni descripción
            # para URLs de video individual. skip_download=True es suficiente.
            "skip_download": True,
        }
        if self.cookies_browser:
            opts["cookiesfrombrowser"] = (self.cookies_browser,)
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                data = ydl.extract_info(self.url, download=False)
            if data:
                self.finished.emit(SocialMediaInfo(data))
            else:
                self.error.emit("No se pudo extraer información de la URL.")
        except yt_dlp.utils.DownloadError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"Error inesperado: {e}")


class SocialMediaDownloadWorker(QtCore.QThread):
    """Ejecuta la descarga real en un hilo separado."""
    progressUpdated = QtCore.pyqtSignal(dict)   # datos del hook de progreso
    statusMessage   = QtCore.pyqtSignal(str)
    finished        = QtCore.pyqtSignal(bool, str)  # éxito, mensaje

    def __init__(self, config: DownloadConfig, parent=None):
        super().__init__(parent=parent)
        self.config   = config
        self._cancel  = threading.Event()

    def cancel(self):
        self._cancel.set()

    def _hook(self, d: dict):
        if self._cancel.is_set():
            raise yt_dlp.utils.DownloadError("Cancelado por el usuario.")
        self.progressUpdated.emit(d)

    def run(self):
        opts = self.config.build_ydl_opts(progress_hook=self._hook)
        opts["quiet"] = True
        opts["no_warnings"] = True
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([self.config.url])
            if not self._cancel.is_set():
                self.finished.emit(True, "Descarga completada correctamente.")
            else:
                self.finished.emit(False, "Descarga cancelada.")
        except yt_dlp.utils.DownloadError as e:
            self.finished.emit(False, str(e))
        except Exception as e:
            self.finished.emit(False, f"Error inesperado: {e}")


# ---------------------------------------------------------------------------
# Manager de alto nivel (instancia global)
# ---------------------------------------------------------------------------

class SocialMediaDownloadManager(QtCore.QObject):
    """
    Manager global. Se instancia una sola vez en App.py:
        SocialDownloadManager = SocialMediaDownloadManager(parent=Instance)
    """
    downloadStarted  = QtCore.pyqtSignal(object)   # SocialMediaDownloadWorker
    downloadFinished = QtCore.pyqtSignal(object, bool, str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._workers: list[SocialMediaDownloadWorker] = []

    def startDownload(self, config: DownloadConfig) -> SocialMediaDownloadWorker:
        worker = SocialMediaDownloadWorker(config, parent=self)
        worker.finished.connect(lambda ok, msg: self._onFinished(worker, ok, msg))
        self._workers.append(worker)
        self.downloadStarted.emit(worker)
        worker.start()
        return worker

    def _onFinished(self, worker: SocialMediaDownloadWorker, ok: bool, msg: str):
        self.downloadFinished.emit(worker, ok, msg)
        if worker in self._workers:
            self._workers.remove(worker)

    def cancelAll(self):
        for w in list(self._workers):
            w.cancel()

    def activeCount(self) -> int:
        return len(self._workers)
