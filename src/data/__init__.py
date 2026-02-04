"""Data layer for reading/writing track and album metadata."""

import csv
import os
from typing import Optional

from src.data.models import AlbumMetadata, TrackMetadata
from src.utils.config import get_or_create_metadata_file_path, get_or_create_albums_file_path

# CSV field names
TRACK_FIELDNAMES = ["key", "track", "artist", "album_name", "album_artist", "genre", "date"]
ALBUM_FIELDNAMES = ["name", "artist"]

# Legacy field names for backwards compatibility
LEGACY_TRACK_FIELDNAMES = ["key", "track", "artist", "album", "genre", "date"]

# In-memory cache
CACHE: dict[str, list] = {}


def _read_csv_rows(file_path: str) -> list[dict[str, str]]:
    """Read raw CSV rows from file."""
    if not os.path.exists(file_path):
        return []
    with open(file_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _is_legacy_track_format(rows: list[dict[str, str]]) -> bool:
    """Check if rows use legacy 'album' column instead of 'album_name'/'album_artist'."""
    if not rows:
        return False
    return "album" in rows[0] and "album_name" not in rows[0]


def _migrate_legacy_track_row(row: dict[str, str]) -> dict[str, str]:
    """Convert legacy track row to new format."""
    album_value = row.get("album", "")
    return {
        "key": row.get("key", ""),
        "track": row.get("track", ""),
        "artist": row.get("artist", ""),
        "album_name": album_value,
        "album_artist": row.get("artist", ""),  # Default album artist to track artist
        "genre": row.get("genre", ""),
        "date": row.get("date", ""),
    }


def _read_track_metadata(file_path: str, use_cache: bool = False) -> list[TrackMetadata]:
    """Read track metadata from CSV file."""
    if use_cache and file_path in CACHE:
        return CACHE[file_path]

    rows = _read_csv_rows(file_path)

    # Handle legacy format migration
    if _is_legacy_track_format(rows):
        rows = [_migrate_legacy_track_row(row) for row in rows]

    tracks = [TrackMetadata.from_csv_row(row) for row in rows]

    if use_cache:
        CACHE[file_path] = tracks

    return tracks


def _read_album_metadata(file_path: str, use_cache: bool = False) -> list[AlbumMetadata]:
    """Read album metadata from CSV file."""
    if use_cache and file_path in CACHE:
        return CACHE[file_path]

    rows = _read_csv_rows(file_path)
    albums = [AlbumMetadata.from_csv_row(row) for row in rows]

    if use_cache:
        CACHE[file_path] = albums

    return albums


def _ensure_parent_dir(path: str) -> None:
    """Create parent directory if it doesn't exist."""
    parent = os.path.dirname(path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)


def _write_csv(file_path: str, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    """Write rows to CSV file."""
    _ensure_parent_dir(file_path)
    with open(file_path, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    # Invalidate cache - use del to properly remove the entry
    if file_path in CACHE:
        del CACHE[file_path]


def get_file_metadata(key: Optional[str] = None) -> TrackMetadata | list[TrackMetadata] | None:
    """Get track metadata by key, or all tracks if no key provided."""
    file_path = str(get_or_create_metadata_file_path())
    tracks = _read_track_metadata(file_path)
    if key:
        return next((t for t in tracks if t.key == key), None)
    return tracks


def get_album_metadata(key: Optional[str] = None) -> AlbumMetadata | list[AlbumMetadata] | None:
    """Get album metadata by name, or all albums if no key provided."""
    file_path = str(get_or_create_albums_file_path())
    albums = _read_album_metadata(file_path)
    if key:
        return next((a for a in albums if a.name == key), None)
    return albums


def upsert_album_metadata(album: AlbumMetadata) -> None:
    """Create or update album row by name."""
    albums_file_path = str(get_or_create_albums_file_path())
    existing = _read_album_metadata(albums_file_path)
    rows = [a.to_csv_row() for a in existing]

    updated = False
    for row in rows:
        if row["name"] == album.name:
            row["artist"] = album.artist
            updated = True
            break
    if not updated:
        rows.append(album.to_csv_row())

    _write_csv(albums_file_path, rows, fieldnames=ALBUM_FIELDNAMES)


def upsert_track_metadata(track: TrackMetadata) -> None:
    """Create or update track row by key."""
    metadata_file_path = str(get_or_create_metadata_file_path())
    existing = _read_track_metadata(metadata_file_path)
    rows = [t.to_csv_row() for t in existing]

    replaced = False
    for i, row in enumerate(rows):
        if row["key"] == track.key:
            rows[i] = track.to_csv_row()
            replaced = True
            break
    if not replaced:
        rows.append(track.to_csv_row())

    _write_csv(metadata_file_path, rows, fieldnames=TRACK_FIELDNAMES)


def clear_cache() -> None:
    """Clear the in-memory cache. Useful for testing."""
    CACHE.clear()
