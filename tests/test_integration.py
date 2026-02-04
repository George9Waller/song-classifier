"""Integration tests for song-classifier."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.data import clear_cache, get_file_metadata, upsert_track_metadata
from src.data.models import AlbumMetadata, TrackMetadata
from src.main import classify_filename
from src.utils.file_transport import LocalTransport


class TestClassifyFilename:
    """Integration tests for classify_filename."""

    @pytest.fixture
    def mock_ai_metadata(self) -> TrackMetadata:
        """Create mock AI metadata result."""
        return TrackMetadata(
            key="test_file.mp3",
            track="Test Track",
            artist="Test Artist",
            album=AlbumMetadata(name="Test Album", artist="Test Artist"),
            genre="Electronic",
            date="2024",
        )

    @pytest.mark.asyncio
    async def test_classify_dry_run(
        self, temp_dir: Path, config_dir: Path, mock_openai_client: MagicMock
    ) -> None:
        """Test classify_filename with dry-run mode."""
        # Create a test file
        test_file = temp_dir / "test_song.mp3"
        test_file.touch()

        transport = LocalTransport()

        with patch("src.main.parse_metadata_with_ai") as mock_parse:
            mock_parse.return_value = TrackMetadata(
                key="test_song.mp3",
                track="Test Song",
                artist="Test Artist",
                album=AlbumMetadata(name="Test Album", artist="Test Artist"),
                genre="Electronic",
                date="2024",
            )

            result = await classify_filename(
                "test_song.mp3",
                str(temp_dir),
                transport,
                skip_processed_files=False,
                skip_files_in_metadata=False,
                dry_run=True,
            )

            assert result is not None
            assert result.track == "Test Song"
            # In dry-run mode, nothing should be written to CSV
            clear_cache()
            metadata = get_file_metadata(key="test_song.mp3")
            assert metadata is None

    @pytest.mark.asyncio
    async def test_classify_skip_in_metadata(
        self, temp_dir: Path, config_dir: Path
    ) -> None:
        """Test skipping files already in metadata."""
        # Add a file to metadata first
        track = TrackMetadata(
            key="existing.mp3",
            track="Existing",
            artist="Artist",
            album=AlbumMetadata(name="Album", artist="Artist"),
            genre="House",
            date="2024",
        )
        clear_cache()
        upsert_track_metadata(track)

        # Create the file
        (temp_dir / "existing.mp3").touch()
        transport = LocalTransport()

        result = await classify_filename(
            "existing.mp3",
            str(temp_dir),
            transport,
            skip_processed_files=False,
            skip_files_in_metadata=True,
            dry_run=False,
        )

        # Should be skipped
        assert result is None


class TestEndToEndFlow:
    """End-to-end flow tests."""

    @pytest.mark.asyncio
    async def test_full_processing_flow_dry_run(
        self, temp_dir: Path, config_dir: Path, mock_openai_response: dict
    ) -> None:
        """Test the full processing flow in dry-run mode."""
        # Create test audio files
        (temp_dir / "song1.mp3").touch()
        (temp_dir / "song2.flac").touch()
        (temp_dir / "readme.txt").touch()  # Should be ignored

        transport = LocalTransport()

        # List files
        files = list(transport.list_files(str(temp_dir)))
        assert len(files) == 2

        # Process with mocked AI
        with patch("src.main.parse_metadata_with_ai") as mock_parse:
            mock_parse.return_value = TrackMetadata(
                key="song1.mp3",
                track="Song One",
                artist="Artist",
                album=AlbumMetadata(name="Album", artist="Artist"),
                genre="Electronic",
                date="2024",
            )

            result = await classify_filename(
                "song1.mp3",
                str(temp_dir),
                transport,
                dry_run=True,
            )

            assert result is not None
            assert result.track == "Song One"
