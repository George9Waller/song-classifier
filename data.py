import csv
from dataclasses import asdict
import os
from functools import partial

from models import AlbumMetadata, TrackMetadata

METADATA_FILE = "data/metadata.csv"
ALBUMS_FILE = "data/albums.csv"

CACHE = {}


def _read_csv(file_path, dataclass, use_cache=False):
    if use_cache and CACHE.get(file_path) is not None:
        return CACHE[file_path]

    if os.path.exists(file_path):
        with open(file_path, mode="r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            CACHE[file_path] = [dataclass(**row) for row in reader]

    return CACHE.get(file_path, [])


def _get_metadata_by_key(*, file_path, dataclass, class_key, key=None):
    data = _read_csv(file_path, dataclass)
    if key:
        return next((row for row in data if getattr(row, class_key) == key), None)
    return data


get_file_metadata = partial(
    _get_metadata_by_key,
    file_path=METADATA_FILE,
    dataclass=TrackMetadata,
    class_key="key"
)
get_album_metadata = partial(
    _get_metadata_by_key,
    file_path=ALBUMS_FILE,
    dataclass=AlbumMetadata,
    class_key="name"
)


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)


def _write_csv(file_path: str, rows: list, fieldnames: list[str]) -> None:
    _ensure_parent_dir(file_path)
    with open(file_path, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    # Invalidate cache
    CACHE[file_path] = None


def upsert_album_metadata(album: AlbumMetadata) -> None:
    """Create or update album row by name."""
    # Load existing as dict rows
    existing = _read_csv(ALBUMS_FILE, AlbumMetadata)
    rows = [
        asdict(a)
        for a in existing
    ]

    updated = False
    for row in rows:
        if row["name"] == album.name:
            row["artist"] = album.artist
            updated = True
            break
    if not updated:
        rows.append(asdict(album))

    _write_csv(ALBUMS_FILE, rows, fieldnames=["name", "artist"])


def upsert_track_metadata(track: TrackMetadata) -> None:
    """Create or update track row by key."""
    existing = _read_csv(METADATA_FILE, TrackMetadata)
    rows = [
        asdict(t)
        for t in existing
    ]

    replaced = False
    for i, row in enumerate(rows):
        if row["key"] == track.key:
            rows[i] = asdict(track)
            replaced = True
            break
    if not replaced:
        rows.append(asdict(track))

    _write_csv(
        METADATA_FILE,
        rows,
        fieldnames=["key", "track", "artist", "album", "genre", "date"],
    )
