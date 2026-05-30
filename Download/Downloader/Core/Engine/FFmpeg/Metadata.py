from Services.Twitch.GQL.TwitchGQLModels import Stream, Video, Clip
from Download.DownloadInfo import DownloadInfo
from Core.Meta import Meta

from PyQt6 import QtCore


class MetadataBuilder:
    """
    Builds a dict of FFmpeg -metadata key=value pairs from a DownloadInfo.

    Supported tags work in MP4, MKV and most remuxed containers.
    Clips are post-processed after download; streams and VODs receive
    the tags during the FFmpeg mux pass.
    """

    # Keys with characters that break FFmpeg's key=value parsing
    _STRIP = str.maketrans({"=": "-", ";": ",", "#": "", "\n": " ", "\r": ""})

    @staticmethod
    def build(downloadInfo: DownloadInfo) -> dict[str, str]:
        content = downloadInfo.content
        if isinstance(content, Stream):
            return MetadataBuilder._fromStream(content)
        elif isinstance(content, Video):
            return MetadataBuilder._fromVideo(content)
        elif isinstance(content, Clip):
            return MetadataBuilder._fromClip(content)
        return {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clean(value: str) -> str:
        """Sanitize a string so it is safe as an FFmpeg metadata value."""
        return value.translate(MetadataBuilder._STRIP).strip()

    @staticmethod
    def _isoDate(dt: QtCore.QDateTime) -> str:
        """Return YYYY-MM-DD from a QDateTime, or '' if invalid."""
        if dt is None or not dt.isValid():
            return ""
        return dt.toUTC().date().toString("yyyy-MM-dd")

    # ------------------------------------------------------------------
    # Per-content-type builders
    # ------------------------------------------------------------------

    @classmethod
    def _fromStream(cls, stream: Stream) -> dict[str, str]:
        broadcaster = stream.broadcaster.displayName or stream.broadcaster.login
        game        = stream.game.name
        date        = cls._isoDate(stream.createdAt)

        description_parts = ["Twitch Stream", broadcaster]
        if game:
            description_parts.append(game)
        if date:
            description_parts.append(date)

        return cls._pack(
            title       = stream.title or "Twitch Stream",
            artist      = broadcaster,
            game        = game,
            date        = date,
            description = " | ".join(description_parts),
            episode_id  = stream.id,
        )

    @classmethod
    def _fromVideo(cls, video: Video) -> dict[str, str]:
        channel = video.owner.displayName or video.owner.login
        game    = video.game.name
        # prefer publishedAt; fall back to createdAt
        date    = cls._isoDate(video.publishedAt) or cls._isoDate(video.createdAt)

        description_parts = ["Twitch VOD", channel]
        if game:
            description_parts.append(game)
        if date:
            description_parts.append(date)

        return cls._pack(
            title       = video.title or "Twitch VOD",
            artist      = channel,
            game        = game,
            date        = date,
            description = " | ".join(description_parts),
            episode_id  = video.id,
        )

    @classmethod
    def _fromClip(cls, clip: Clip) -> dict[str, str]:
        broadcaster = clip.broadcaster.displayName or clip.broadcaster.login
        curator     = clip.curator.displayName or clip.curator.login
        game        = clip.game.name
        date        = cls._isoDate(clip.createdAt)

        description_parts = ["Twitch Clip", broadcaster]
        if curator:
            description_parts.append(f"Clipped by {curator}")
        if game:
            description_parts.append(game)
        if date:
            description_parts.append(date)

        return cls._pack(
            title       = clip.title or "Twitch Clip",
            artist      = broadcaster,
            game        = game,
            date        = date,
            description = " | ".join(description_parts),
            episode_id  = clip.slug or clip.id,
        )

    @classmethod
    def _pack(
        cls,
        title: str,
        artist: str,
        game: str,
        date: str,
        description: str,
        episode_id: str,
    ) -> dict[str, str]:
        """
        Assemble the final metadata dict, sanitizing every value and
        omitting empty fields so FFmpeg never receives blank tags.
        """
        raw = {
            "title":        title,
            "artist":       artist,
            "album_artist": artist,
            "comment":      game,
            "date":         date,
            "description":  description,
            "service_name": "Twitch",
            "episode_id":   episode_id,
            "encoder":      f"TwitchLink {Meta.APP_VERSION}",
        }
        return {k: cls._clean(v) for k, v in raw.items() if v}
