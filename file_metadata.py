import os
from typing import Optional

from mutagen import File
from mutagen.flac import FLAC
from mutagen.mp3 import EasyMP3
from mutagen.id3 import ID3, COMM, ID3NoHeaderError
from mutagen.mp4 import MP4, MP4Tags
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis

from models import AlbumMetadata, TrackMetadata


def _safe_first(value) -> Optional[str]:
    if isinstance(value, list) and value:
        return str(value[0])
    if isinstance(value, str):
        return value
    return None


def _from_mp3(path: str) -> Optional[TrackMetadata]:
    try:
        audio = EasyMP3(path)
    except Exception:
        return None
    title = _safe_first(audio.get("title"))
    artist = _safe_first(audio.get("artist"))
    album = _safe_first(audio.get("album"))
    genre = _safe_first(audio.get("genre"))
    date = _safe_first(audio.get("date")) or _safe_first(audio.get("originaldate"))

    if not any([title, artist, album, genre, date]):
        return None

    return TrackMetadata(
        key=path,
        track=title or "",
        artist=artist or "",
        album=AlbumMetadata(name=album or "", artist=artist or ""),
        genre=genre or "",
        date=date,
    )


def _from_flac(path: str) -> Optional[TrackMetadata]:
    try:
        audio = FLAC(path)
    except Exception:
        return None
    title = _safe_first(audio.get("title"))
    artist = _safe_first(audio.get("artist"))
    album = _safe_first(audio.get("album"))
    genre = _safe_first(audio.get("genre"))
    date = _safe_first(audio.get("date"))

    if not any([title, artist, album, genre, date]):
        return None

    return TrackMetadata(
        key=path,
        track=title or "",
        artist=artist or "",
        album=AlbumMetadata(name=album or "", artist=artist or ""),
        genre=genre or "",
        date=date,
    )


def _from_mp4(path: str) -> Optional[TrackMetadata]:
    try:
        audio = MP4(path)
    except Exception:
        return None
    tags = audio.tags or {}

    title = _safe_first(tags.get("\xa9nam"))
    artist = _safe_first(tags.get("\xa9ART"))
    album = _safe_first(tags.get("\xa9alb"))
    genre = _safe_first(tags.get("\xa9gen"))
    date = _safe_first(tags.get("\xa9day"))

    if not any([title, artist, album, genre, date]):
        return None

    return TrackMetadata(
        key=path,
        track=title or "",
        artist=artist or "",
        album=AlbumMetadata(name=album or "", artist=artist or ""),
        genre=genre or "",
        date=date,
    )


def _from_ogg_opus(path: str) -> Optional[TrackMetadata]:
    try:
        audio = OggOpus(path)
    except Exception:
        return None
    title = _safe_first(audio.tags.get("title")) if audio.tags else None
    artist = _safe_first(audio.tags.get("artist")) if audio.tags else None
    album = _safe_first(audio.tags.get("album")) if audio.tags else None
    albumartist = _safe_first(audio.tags.get("albumartist")) if audio.tags else None
    genre = _safe_first(audio.tags.get("genre")) if audio.tags else None
    date = _safe_first(audio.tags.get("date")) if audio.tags else None

    if not any([title, artist, album, genre, date]):
        return None

    return TrackMetadata(
        key=path,
        track=title or "",
        artist=artist or "",
        album=AlbumMetadata(name=album or "", artist=albumartist or artist or ""),
        genre=genre or "",
        date=date,
    )


def _from_ogg_vorbis(path: str) -> Optional[TrackMetadata]:
    try:
        audio = OggVorbis(path)
    except Exception:
        return None
    title = _safe_first(audio.tags.get("title")) if audio.tags else None
    artist = _safe_first(audio.tags.get("artist")) if audio.tags else None
    album = _safe_first(audio.tags.get("album")) if audio.tags else None
    albumartist = _safe_first(audio.tags.get("albumartist")) if audio.tags else None
    genre = _safe_first(audio.tags.get("genre")) if audio.tags else None
    date = _safe_first(audio.tags.get("date")) if audio.tags else None

    if not any([title, artist, album, genre, date]):
        return None

    return TrackMetadata(
        key=path,
        track=title or "",
        artist=artist or "",
        album=AlbumMetadata(name=album or "", artist=albumartist or artist or ""),
        genre=genre or "",
        date=date,
    )


def read_file_metadata(path: str) -> Optional[TrackMetadata]:
    """Read existing metadata from an audio file, if present.

    Supports MP3, FLAC, and MP4/M4A. Returns None if tags are missing
    or the file type is unsupported/unreadable.
    """
    if not os.path.exists(path):
        return None

    lower = path.lower()
    if lower.endswith(".mp3"):
        return _from_mp3(path)
    if lower.endswith(".flac"):
        return _from_flac(path)
    if lower.endswith(".m4a") or lower.endswith(".mp4"):
        return _from_mp4(path)
    if lower.endswith(".opus"):
        return _from_ogg_opus(path)
    if lower.endswith(".ogg"):
        # Try Opus first (Opus-in-Ogg) then Vorbis
        return _from_ogg_opus(path) or _from_ogg_vorbis(path)

    # Fallback: try mutagen generic loader
    # try:
    #     audio = File(path)
    #     if audio is None:
    #         return None
    # except Exception:
    #     return None

    return None


PROCESSED_MARKER = "Processed by song-classifier"


def _has_marker_in_list(value_list, marker: str) -> bool:
    items = value_list if isinstance(value_list, list) else [value_list]
    for v in items:
        if isinstance(v, bytes):
            try:
                v = v.decode("utf-8", errors="ignore")
            except Exception:
                continue
        if isinstance(v, str) and marker in v:
            return True
    return False


def is_already_processed(path: str) -> bool:
    lower = path.lower()
    try:
        if lower.endswith(".mp3"):
            # Check COMM frames for processed marker
            try:
                id3 = ID3(path)
            except ID3NoHeaderError:
                return False
            for comm in id3.getall("COMM"):
                texts = comm.text if isinstance(comm.text, list) else [comm.text]
                if _has_marker_in_list(texts, PROCESSED_MARKER):
                    return True
            return False
        if lower.endswith(".flac"):
            audio = FLAC(path)
            return _has_marker_in_list(audio.get("comment"), PROCESSED_MARKER)
        if lower.endswith(".m4a") or lower.endswith(".mp4"):
            audio = MP4(path)
            tags = audio.tags or {}
            return _has_marker_in_list(tags.get("\xa9cmt"), PROCESSED_MARKER)
        if lower.endswith(".opus"):
            audio = OggOpus(path)
            tags = audio.tags or {}
            return _has_marker_in_list(tags.get("comment"), PROCESSED_MARKER)
        if lower.endswith(".ogg"):
            # Try Opus then Vorbis
            try:
                audio = OggOpus(path)
                tags = audio.tags or {}
                if _has_marker_in_list(tags.get("comment"), PROCESSED_MARKER):
                    return True
            except Exception:
                pass
            try:
                vorb = OggVorbis(path)
                return _has_marker_in_list(vorb.tags.get("comment") if vorb.tags else None, PROCESSED_MARKER)
            except Exception:
                return False
    except Exception:
        return False
    return False


def _merge_comment(existing, marker: str):
    values = []
    if isinstance(existing, list):
        for v in existing:
            if isinstance(v, bytes):
                try:
                    v = v.decode("utf-8", errors="ignore")
                except Exception:
                    continue
            if isinstance(v, str):
                values.append(v)
    elif isinstance(existing, str):
        values.append(existing)
    if marker not in values:
        values.append(marker)
    return values or [marker]


def _write_mp3(path: str, meta: TrackMetadata) -> None:
    audio = EasyMP3(path)
    audio["title"] = meta.track
    audio["artist"] = meta.artist
    audio["album"] = meta.album.name
    audio["albumartist"] = meta.album.artist
    audio["genre"] = meta.genre
    if meta.date:
        audio["date"] = meta.date
    # Save EasyID3 fields first
    audio.save()

    # Ensure processed marker exists in an ID3 COMM frame
    try:
        id3 = ID3(path)
    except ID3NoHeaderError:
        id3 = ID3()

    has_marker = False
    for comm in id3.getall("COMM"):
        texts = comm.text if isinstance(comm.text, list) else [comm.text]
        if _has_marker_in_list(texts, PROCESSED_MARKER):
            has_marker = True
            break
    if not has_marker:
        # Add a new English comment with our marker
        id3.add(COMM(encoding=3, lang="eng", desc="song-classifier", text=PROCESSED_MARKER))
    id3.save(path)


def _write_flac(path: str, meta: TrackMetadata) -> None:
    audio = FLAC(path)
    audio["title"] = meta.track
    audio["artist"] = meta.artist
    audio["album"] = meta.album.name
    audio["albumartist"] = meta.album.artist
    audio["genre"] = meta.genre
    if meta.date:
        audio["date"] = meta.date
    # processed marker in comment
    audio["comment"] = _merge_comment(audio.get("comment"), PROCESSED_MARKER)
    audio.save()


def _write_mp4(path: str, meta: TrackMetadata) -> None:
    audio = MP4(path)
    tags = audio.tags or MP4Tags()
    tags["\xa9nam"] = meta.track
    tags["\xa9ART"] = meta.artist
    tags["\xa9alb"] = meta.album.name
    tags["aART"] = meta.album.artist
    tags["\xa9gen"] = meta.genre
    if meta.date:
        tags["\xa9day"] = meta.date
    # processed marker in comment
    existing = tags.get("\xa9cmt")
    tags["\xa9cmt"] = _merge_comment(existing, PROCESSED_MARKER)
    audio.tags = tags
    audio.save()


def _write_ogg_opus(path: str, meta: TrackMetadata) -> None:
    audio = OggOpus(path)
    tags = audio.tags or {}
    tags["title"] = meta.track
    tags["artist"] = meta.artist
    tags["album"] = meta.album.name
    tags["albumartist"] = meta.album.artist
    tags["genre"] = meta.genre
    if meta.date:
        tags["date"] = meta.date
    # processed marker in comment
    existing = tags.get("comment")
    tags["comment"] = _merge_comment(existing, PROCESSED_MARKER)
    audio.tags = tags
    audio.save()


def _write_ogg_vorbis(path: str, meta: TrackMetadata) -> None:
    audio = OggVorbis(path)
    tags = audio.tags or {}
    tags["title"] = meta.track
    tags["artist"] = meta.artist
    tags["album"] = meta.album.name
    tags["albumartist"] = meta.album.artist
    tags["genre"] = meta.genre
    if meta.date:
        tags["date"] = meta.date
    # processed marker in comment
    existing = tags.get("comment")
    tags["comment"] = _merge_comment(existing, PROCESSED_MARKER)
    audio.tags = tags
    audio.save()


def write_file_metadata(path: str, meta: TrackMetadata) -> None:
    lower = path.lower()
    if lower.endswith(".mp3"):
        _write_mp3(path, meta)
        return
    if lower.endswith(".flac"):
        _write_flac(path, meta)
        return
    if lower.endswith(".m4a") or lower.endswith(".mp4"):
        _write_mp4(path, meta)
        return
    if lower.endswith(".opus"):
        _write_ogg_opus(path, meta)
        return
    if lower.endswith(".ogg"):
        # Try Opus then Vorbis
        try:
            _write_ogg_opus(path, meta)
        except Exception:
            _write_ogg_vorbis(path, meta)
        return
