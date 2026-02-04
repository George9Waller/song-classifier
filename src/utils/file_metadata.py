"""Audio file metadata reading and writing using mutagen."""

import os
from typing import Optional

from mutagen import MutagenError
from mutagen.flac import FLAC
from mutagen.mp3 import EasyMP3
from mutagen.id3 import ID3, COMM, ID3NoHeaderError
from mutagen.mp4 import MP4, MP4Tags
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis

from src.data.models import AlbumMetadata, TrackMetadata
from src.utils.constants import PROCESSED_MARKER
from src.utils.logging import get_logger


def _safe_first(value: object) -> Optional[str]:
    """Extract first string value from a potentially list-wrapped tag value.

    Args:
        value: Tag value which may be a string, list, or None.

    Returns:
        First string value or None.
    """
    if isinstance(value, list) and value:
        return str(value[0])
    if isinstance(value, str):
        return value
    return None


def _from_mp3(path: str) -> Optional[TrackMetadata]:
    """Read metadata from MP3 file."""
    logger = get_logger()
    try:
        audio = EasyMP3(path)
    except MutagenError as e:
        logger.debug(f"Failed to read MP3 {path}: {e}")
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
    """Read metadata from FLAC file."""
    logger = get_logger()
    try:
        audio = FLAC(path)
    except MutagenError as e:
        logger.debug(f"Failed to read FLAC {path}: {e}")
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
    """Read metadata from MP4/M4A file."""
    logger = get_logger()
    try:
        audio = MP4(path)
    except MutagenError as e:
        logger.debug(f"Failed to read MP4 {path}: {e}")
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
    """Read metadata from Ogg Opus file."""
    logger = get_logger()
    try:
        audio = OggOpus(path)
    except MutagenError as e:
        logger.debug(f"Failed to read Opus {path}: {e}")
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
    """Read metadata from Ogg Vorbis file."""
    logger = get_logger()
    try:
        audio = OggVorbis(path)
    except MutagenError as e:
        logger.debug(f"Failed to read Vorbis {path}: {e}")
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

    Supports MP3, FLAC, MP4/M4A, Opus, and Ogg Vorbis.

    Args:
        path: Path to the audio file.

    Returns:
        TrackMetadata if tags exist, None otherwise.
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

    return None


def _has_marker_in_list(value_list: object, marker: str) -> bool:
    """Check if marker exists in a potentially list-wrapped value.

    Args:
        value_list: Value to check (may be list, string, or None).
        marker: Marker string to search for.

    Returns:
        True if marker is found.
    """
    if value_list is None:
        return False
    items = value_list if isinstance(value_list, list) else [value_list]
    for v in items:
        if isinstance(v, bytes):
            try:
                v = v.decode("utf-8", errors="ignore")
            except (UnicodeDecodeError, AttributeError):
                continue
        if isinstance(v, str) and marker in v:
            return True
    return False


def is_already_processed(path: str) -> bool:
    """Check if a file has been processed by song-classifier.

    Args:
        path: Path to the audio file.

    Returns:
        True if the file has the processed marker.
    """
    logger = get_logger()
    lower = path.lower()

    try:
        if lower.endswith(".mp3"):
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
            except MutagenError:
                pass
            try:
                vorb = OggVorbis(path)
                return _has_marker_in_list(vorb.tags.get("comment") if vorb.tags else None, PROCESSED_MARKER)
            except MutagenError:
                return False

    except MutagenError as e:
        logger.debug(f"Error checking processed status for {path}: {e}")
        return False

    return False


def _merge_comment(existing: object, marker: str) -> list[str]:
    """Merge marker into existing comment values.

    Args:
        existing: Existing comment value(s).
        marker: Marker to add.

    Returns:
        List of comment values including the marker.
    """
    values: list[str] = []
    if isinstance(existing, list):
        for v in existing:
            if isinstance(v, bytes):
                try:
                    v = v.decode("utf-8", errors="ignore")
                except (UnicodeDecodeError, AttributeError):
                    continue
            if isinstance(v, str):
                values.append(v)
    elif isinstance(existing, str):
        values.append(existing)

    if marker not in values:
        values.append(marker)

    return values or [marker]


def _write_mp3(path: str, meta: TrackMetadata) -> None:
    """Write metadata to MP3 file."""
    audio = EasyMP3(path)
    audio["title"] = meta.track
    audio["artist"] = meta.artist
    audio["album"] = meta.album.name
    audio["albumartist"] = meta.album.artist
    audio["genre"] = meta.genre
    if meta.date:
        audio["date"] = meta.date
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
        id3.add(COMM(encoding=3, lang="eng", desc="song-classifier", text=PROCESSED_MARKER))
    id3.save(path)


def _write_flac(path: str, meta: TrackMetadata) -> None:
    """Write metadata to FLAC file."""
    audio = FLAC(path)
    audio["title"] = meta.track
    audio["artist"] = meta.artist
    audio["album"] = meta.album.name
    audio["albumartist"] = meta.album.artist
    audio["genre"] = meta.genre
    if meta.date:
        audio["date"] = meta.date
    audio["comment"] = _merge_comment(audio.get("comment"), PROCESSED_MARKER)
    audio.save()


def _write_mp4(path: str, meta: TrackMetadata) -> None:
    """Write metadata to MP4/M4A file."""
    audio = MP4(path)
    tags = audio.tags or MP4Tags()
    tags["\xa9nam"] = meta.track
    tags["\xa9ART"] = meta.artist
    tags["\xa9alb"] = meta.album.name
    tags["aART"] = meta.album.artist
    tags["\xa9gen"] = meta.genre
    if meta.date:
        tags["\xa9day"] = meta.date
    existing = tags.get("\xa9cmt")
    tags["\xa9cmt"] = _merge_comment(existing, PROCESSED_MARKER)
    audio.tags = tags
    audio.save()


def _write_ogg_opus(path: str, meta: TrackMetadata) -> None:
    """Write metadata to Ogg Opus file."""
    audio = OggOpus(path)
    tags = audio.tags or {}
    tags["title"] = meta.track
    tags["artist"] = meta.artist
    tags["album"] = meta.album.name
    tags["albumartist"] = meta.album.artist
    tags["genre"] = meta.genre
    if meta.date:
        tags["date"] = meta.date
    existing = tags.get("comment")
    tags["comment"] = _merge_comment(existing, PROCESSED_MARKER)
    audio.tags = tags
    audio.save()


def _write_ogg_vorbis(path: str, meta: TrackMetadata) -> None:
    """Write metadata to Ogg Vorbis file."""
    audio = OggVorbis(path)
    tags = audio.tags or {}
    tags["title"] = meta.track
    tags["artist"] = meta.artist
    tags["album"] = meta.album.name
    tags["albumartist"] = meta.album.artist
    tags["genre"] = meta.genre
    if meta.date:
        tags["date"] = meta.date
    existing = tags.get("comment")
    tags["comment"] = _merge_comment(existing, PROCESSED_MARKER)
    audio.tags = tags
    audio.save()


def write_file_metadata(path: str, meta: TrackMetadata) -> None:
    """Write metadata to an audio file.

    Supports MP3, FLAC, MP4/M4A, Opus, and Ogg Vorbis.
    Also adds the processed marker to the file.

    Args:
        path: Path to the audio file.
        meta: Metadata to write.

    Raises:
        MutagenError: If writing fails.
    """
    logger = get_logger()
    lower = path.lower()

    try:
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
            except MutagenError:
                _write_ogg_vorbis(path, meta)
            return
    except MutagenError as e:
        logger.error(f"Failed to write metadata to {path}: {e}")
        raise
