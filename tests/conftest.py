"""Pytest fixtures for song-classifier tests."""

import os
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.data.models import AlbumMetadata, TrackMetadata


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_album() -> AlbumMetadata:
    """Create a sample album for testing."""
    return AlbumMetadata(name="Test Album", artist="Test Artist")


@pytest.fixture
def sample_track(sample_album: AlbumMetadata) -> TrackMetadata:
    """Create a sample track for testing."""
    return TrackMetadata(
        key="test_file.mp3",
        track="Test Track",
        artist="Test Artist",
        album=sample_album,
        genre="Electronic",
        date="2024",
    )


@pytest.fixture
def sample_csv_content() -> str:
    """Sample CSV content in new format."""
    return """key,track,artist,album_name,album_artist,genre,date
test1.mp3,Track One,Artist One,Album One,Artist One,House,2024
test2.mp3,Track Two,Artist Two,Album Two,Artist Two,Techno,2023
"""


@pytest.fixture
def legacy_csv_content() -> str:
    """Sample CSV content in legacy format."""
    return """key,track,artist,album,genre,date
test1.mp3,Track One,Artist One,Album One,House,2024
test2.mp3,Track Two,Artist Two,Album Two,Techno,2023
"""


@pytest.fixture
def mock_openai_response() -> dict:
    """Mock OpenAI API response."""
    return {
        "track": "Test Track",
        "artist": "Test Artist",
        "album": {"name": "Test Album", "artist": "Test Artist"},
        "genre": "Electronic",
        "date": "2024",
    }


@pytest.fixture
def mock_openai_client(mock_openai_response: dict) -> MagicMock:
    """Create a mock OpenAI client."""
    import json

    mock_client = AsyncMock()
    mock_completion = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()
    mock_message.content = json.dumps(mock_openai_response)
    mock_choice.message = mock_message
    mock_completion.choices = [mock_choice]
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

    return mock_client


@pytest.fixture
def config_dir(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a temporary config directory and patch the config module."""
    config_path = temp_dir / "config"
    config_path.mkdir()

    # Patch the config functions
    import src.utils.config as config_module

    original_get_config_dir = config_module.get_or_create_config_dir

    def mock_get_config_dir() -> Path:
        return config_path

    config_module.get_or_create_config_dir = mock_get_config_dir

    yield config_path

    # Restore original
    config_module.get_or_create_config_dir = original_get_config_dir
