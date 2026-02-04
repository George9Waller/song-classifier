"""Tests for data module."""

from pathlib import Path

import pytest

from src.data import (
    TRACK_FIELDNAMES,
    ALBUM_FIELDNAMES,
    _read_csv_rows,
    _is_legacy_track_format,
    _migrate_legacy_track_row,
    _read_track_metadata,
    _read_album_metadata,
    get_file_metadata,
    get_album_metadata,
    upsert_album_metadata,
    upsert_track_metadata,
    clear_cache,
)
from src.data.models import AlbumMetadata, TrackMetadata


class TestCSVReading:
    """Tests for CSV reading functions."""

    def test_read_csv_rows_nonexistent(self, temp_dir: Path) -> None:
        """Test reading nonexistent file returns empty list."""
        rows = _read_csv_rows(str(temp_dir / "nonexistent.csv"))
        assert rows == []

    def test_read_csv_rows(self, temp_dir: Path, sample_csv_content: str) -> None:
        """Test reading CSV rows."""
        csv_path = temp_dir / "test.csv"
        csv_path.write_text(sample_csv_content)

        rows = _read_csv_rows(str(csv_path))
        assert len(rows) == 2
        assert rows[0]["key"] == "test1.mp3"
        assert rows[1]["key"] == "test2.mp3"


class TestLegacyFormat:
    """Tests for legacy format detection and migration."""

    def test_is_legacy_format_empty(self) -> None:
        """Test empty rows is not legacy format."""
        assert _is_legacy_track_format([]) is False

    def test_is_legacy_format_new(self) -> None:
        """Test new format detection."""
        rows = [{"key": "a", "album_name": "b", "album_artist": "c"}]
        assert _is_legacy_track_format(rows) is False

    def test_is_legacy_format_old(self) -> None:
        """Test legacy format detection."""
        rows = [{"key": "a", "album": "b"}]
        assert _is_legacy_track_format(rows) is True

    def test_migrate_legacy_row(self) -> None:
        """Test migrating legacy row to new format."""
        legacy_row = {
            "key": "test.mp3",
            "track": "Track",
            "artist": "Artist",
            "album": "Album",
            "genre": "House",
            "date": "2024",
        }
        new_row = _migrate_legacy_track_row(legacy_row)
        assert new_row["key"] == "test.mp3"
        assert new_row["album_name"] == "Album"
        assert new_row["album_artist"] == "Artist"


class TestMetadataReading:
    """Tests for metadata reading functions."""

    def test_read_track_metadata(self, temp_dir: Path, sample_csv_content: str) -> None:
        """Test reading track metadata."""
        csv_path = temp_dir / "metadata.csv"
        csv_path.write_text(sample_csv_content)
        clear_cache()

        tracks = _read_track_metadata(str(csv_path))
        assert len(tracks) == 2
        assert tracks[0].key == "test1.mp3"
        assert tracks[0].album.name == "Album One"

    def test_read_legacy_track_metadata(self, temp_dir: Path, legacy_csv_content: str) -> None:
        """Test reading legacy track metadata with migration."""
        csv_path = temp_dir / "metadata.csv"
        csv_path.write_text(legacy_csv_content)
        clear_cache()

        tracks = _read_track_metadata(str(csv_path))
        assert len(tracks) == 2
        assert tracks[0].album.name == "Album One"
        # Album artist defaults to track artist in legacy migration
        assert tracks[0].album.artist == "Artist One"

    def test_read_album_metadata(self, temp_dir: Path) -> None:
        """Test reading album metadata."""
        csv_content = "name,artist\nAlbum A,Artist A\nAlbum B,Artist B\n"
        csv_path = temp_dir / "albums.csv"
        csv_path.write_text(csv_content)
        clear_cache()

        albums = _read_album_metadata(str(csv_path))
        assert len(albums) == 2
        assert albums[0].name == "Album A"
        assert albums[1].artist == "Artist B"


class TestUpsert:
    """Tests for upsert functions."""

    def test_upsert_album_new(self, config_dir: Path) -> None:
        """Test inserting new album."""
        clear_cache()
        album = AlbumMetadata(name="New Album", artist="New Artist")
        upsert_album_metadata(album)

        albums_file = config_dir / "albums.csv"
        assert albums_file.exists()
        content = albums_file.read_text()
        assert "New Album" in content
        assert "New Artist" in content

    def test_upsert_album_update(self, config_dir: Path) -> None:
        """Test updating existing album."""
        clear_cache()
        # Insert first
        album1 = AlbumMetadata(name="Album", artist="Artist 1")
        upsert_album_metadata(album1)

        # Update
        album2 = AlbumMetadata(name="Album", artist="Artist 2")
        upsert_album_metadata(album2)

        albums_file = config_dir / "albums.csv"
        content = albums_file.read_text()
        # Should only have one entry for "Album"
        assert content.count("Album") == 1
        assert "Artist 2" in content

    def test_upsert_track_new(self, config_dir: Path, sample_track: TrackMetadata) -> None:
        """Test inserting new track."""
        clear_cache()
        upsert_track_metadata(sample_track)

        metadata_file = config_dir / "metadata.csv"
        assert metadata_file.exists()
        content = metadata_file.read_text()
        assert "test_file.mp3" in content
        assert "Test Track" in content

    def test_upsert_track_update(self, config_dir: Path, sample_album: AlbumMetadata) -> None:
        """Test updating existing track."""
        clear_cache()
        # Insert first
        track1 = TrackMetadata(
            key="file.mp3",
            track="Track 1",
            artist="Artist",
            album=sample_album,
            genre="House",
            date="2024",
        )
        upsert_track_metadata(track1)

        # Update
        track2 = TrackMetadata(
            key="file.mp3",
            track="Track 2",
            artist="Artist",
            album=sample_album,
            genre="Techno",
            date="2025",
        )
        upsert_track_metadata(track2)

        metadata_file = config_dir / "metadata.csv"
        content = metadata_file.read_text()
        # Should only have one entry for "file.mp3"
        assert content.count("file.mp3") == 1
        assert "Track 2" in content
        assert "Techno" in content
