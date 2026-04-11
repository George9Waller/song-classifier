"""Tests for data models."""

from src.data.models import AlbumMetadata, TrackMetadata


class TestAlbumMetadata:
    """Tests for AlbumMetadata."""

    def test_to_csv_row(self, sample_album: AlbumMetadata) -> None:
        """Test CSV row serialization."""
        row = sample_album.to_csv_row()
        assert row == {"name": "Test Album", "artist": "Test Artist"}

    def test_from_csv_row(self) -> None:
        """Test CSV row deserialization."""
        row = {"name": "Album Name", "artist": "Album Artist"}
        album = AlbumMetadata.from_csv_row(row)
        assert album.name == "Album Name"
        assert album.artist == "Album Artist"

    def test_roundtrip(self, sample_album: AlbumMetadata) -> None:
        """Test serialization roundtrip."""
        row = sample_album.to_csv_row()
        restored = AlbumMetadata.from_csv_row(row)
        assert restored.name == sample_album.name
        assert restored.artist == sample_album.artist


class TestTrackMetadata:
    """Tests for TrackMetadata."""

    def test_to_csv_row(self, sample_track: TrackMetadata) -> None:
        """Test CSV row serialization."""
        row = sample_track.to_csv_row()
        assert row == {
            "key": "test_file.mp3",
            "track": "Test Track",
            "artist": "Test Artist",
            "album_name": "Test Album",
            "album_artist": "Test Artist",
            "genre": "Electronic",
            "date": "2024",
        }

    def test_to_csv_row_none_date(self, sample_album: AlbumMetadata) -> None:
        """Test CSV row serialization with None date."""
        track = TrackMetadata(
            key="test.mp3",
            track="Track",
            artist="Artist",
            album=sample_album,
            genre="House",
            date=None,
        )
        row = track.to_csv_row()
        assert row["date"] == ""

    def test_from_csv_row(self) -> None:
        """Test CSV row deserialization."""
        row = {
            "key": "file.mp3",
            "track": "Song",
            "artist": "Artist",
            "album_name": "Album",
            "album_artist": "Album Artist",
            "genre": "Techno",
            "date": "2023",
        }
        track = TrackMetadata.from_csv_row(row)
        assert track.key == "file.mp3"
        assert track.track == "Song"
        assert track.artist == "Artist"
        assert track.album.name == "Album"
        assert track.album.artist == "Album Artist"
        assert track.genre == "Techno"
        assert track.date == "2023"

    def test_from_csv_row_empty_date(self) -> None:
        """Test CSV row deserialization with empty date."""
        row = {
            "key": "file.mp3",
            "track": "Song",
            "artist": "Artist",
            "album_name": "Album",
            "album_artist": "Album Artist",
            "genre": "Techno",
            "date": "",
        }
        track = TrackMetadata.from_csv_row(row)
        assert track.date is None

    def test_roundtrip(self, sample_track: TrackMetadata) -> None:
        """Test serialization roundtrip."""
        row = sample_track.to_csv_row()
        restored = TrackMetadata.from_csv_row(row)
        assert restored.key == sample_track.key
        assert restored.track == sample_track.track
        assert restored.artist == sample_track.artist
        assert restored.album.name == sample_track.album.name
        assert restored.album.artist == sample_track.album.artist
        assert restored.genre == sample_track.genre
        assert restored.date == sample_track.date
