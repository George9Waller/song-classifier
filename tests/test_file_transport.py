"""Tests for file transport module."""

import os
from pathlib import Path

import pytest

from src.utils.file_transport import (
    AUDIO_EXTENSIONS,
    is_audio_file,
    TransportType,
    FileTransport,
    LocalTransport,
)


class TestIsAudioFile:
    """Tests for is_audio_file function."""

    @pytest.mark.parametrize("ext", list(AUDIO_EXTENSIONS))
    def test_supported_extensions(self, ext: str) -> None:
        """Test all supported extensions are recognized."""
        assert is_audio_file(f"test{ext}") is True

    @pytest.mark.parametrize("ext", [".txt", ".pdf", ".jpg", ".mp", ".fla"])
    def test_unsupported_extensions(self, ext: str) -> None:
        """Test unsupported extensions are rejected."""
        assert is_audio_file(f"test{ext}") is False

    def test_case_insensitive(self) -> None:
        """Test extension matching is case insensitive."""
        assert is_audio_file("test.MP3") is True
        assert is_audio_file("test.FLAC") is True
        assert is_audio_file("test.M4A") is True


class TestTransportType:
    """Tests for TransportType enum."""

    def test_enum_values(self) -> None:
        """Test enum has expected values."""
        assert TransportType.LOCAL.value == "LOCAL"
        assert TransportType.WEBDAV.value == "WEBDAV"


class TestFileTransportFactory:
    """Tests for FileTransport factory."""

    def test_create_local_transport(self) -> None:
        """Test creating local transport."""
        transport = FileTransport(TransportType.LOCAL)
        assert isinstance(transport, LocalTransport)

    def test_create_webdav_transport_without_host_raises(self) -> None:
        """Test creating WebDAV transport without host raises error."""
        with pytest.raises(ValueError, match="webdav_host must be provided"):
            FileTransport(TransportType.WEBDAV)


class TestLocalTransport:
    """Tests for LocalTransport."""

    def test_list_files_empty_dir(self, temp_dir: Path) -> None:
        """Test listing files in empty directory."""
        transport = LocalTransport()
        files = list(transport.list_files(str(temp_dir)))
        assert files == []

    def test_list_files_with_audio(self, temp_dir: Path) -> None:
        """Test listing audio files."""
        # Create some test files
        (temp_dir / "song.mp3").touch()
        (temp_dir / "album.flac").touch()
        (temp_dir / "readme.txt").touch()

        transport = LocalTransport()
        files = list(transport.list_files(str(temp_dir)))

        assert len(files) == 2
        assert "song.mp3" in files
        assert "album.flac" in files

    def test_list_files_recursive(self, temp_dir: Path) -> None:
        """Test listing files recursively."""
        # Create nested structure
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        (temp_dir / "root.mp3").touch()
        (subdir / "nested.mp3").touch()

        transport = LocalTransport()
        files = list(transport.list_files(str(temp_dir)))

        assert len(files) == 2
        assert "root.mp3" in files
        # Nested file should have relative path
        nested_files = [f for f in files if "nested" in f]
        assert len(nested_files) == 1

    def test_load_file_returns_full_path(self, temp_dir: Path) -> None:
        """Test load_file returns full path."""
        (temp_dir / "test.mp3").touch()

        transport = LocalTransport()
        result = transport.load_file("test.mp3", str(temp_dir))

        assert result == str(temp_dir / "test.mp3")

    def test_save_file_noop(self, temp_dir: Path) -> None:
        """Test save_file does nothing for local transport."""
        transport = LocalTransport()
        result = transport.save_file(
            str(temp_dir / "test.mp3"),
            str(temp_dir),
            "test.mp3",
        )
        assert result is None

    def test_cleanup_local_files_false(self) -> None:
        """Test cleanup_local_files is False for local transport."""
        transport = LocalTransport()
        assert transport.cleanup_local_files is False
