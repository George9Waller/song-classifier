"""Tests for AI metadata module."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.data.models import AlbumMetadata, TrackMetadata
from src.utils.ai_metadata import (
    MissingAPIKeyError,
    _build_prompt,
    _extract_json,
    parse_metadata_with_ai,
    validate_api_key,
)


class TestAPIKeyValidation:
    """Tests for API key validation."""

    def test_validate_api_key_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test validation fails when key is missing."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(MissingAPIKeyError):
            validate_api_key()

    def test_validate_api_key_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test validation passes when key is present."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        validate_api_key()  # Should not raise


class TestPromptBuilding:
    """Tests for prompt building."""

    def test_build_prompt_basic(self, config_dir) -> None:
        """Test basic prompt building."""
        prompt = _build_prompt("Artist - Track.mp3", None)
        assert "Artist - Track.mp3" in prompt
        assert "JSON" in prompt
        assert "track" in prompt
        assert "artist" in prompt
        assert "album" in prompt

    def test_build_prompt_with_existing(self, sample_track: TrackMetadata, config_dir) -> None:
        """Test prompt building with existing metadata."""
        prompt = _build_prompt("test.mp3", sample_track)
        assert "Existing tags" in prompt
        assert "Test Track" in prompt


class TestJSONExtraction:
    """Tests for JSON extraction from responses."""

    def test_extract_json_plain(self) -> None:
        """Test extracting plain JSON."""
        text = '{"track": "Test", "artist": "Artist"}'
        result = _extract_json(text)
        assert result == text

    def test_extract_json_with_markdown(self) -> None:
        """Test extracting JSON from markdown code block."""
        text = '```json\n{"track": "Test"}\n```'
        result = _extract_json(text)
        assert result == '{"track": "Test"}'

    def test_extract_json_with_surrounding_text(self) -> None:
        """Test extracting JSON from surrounding text."""
        text = 'Here is the result: {"track": "Test"} That is all.'
        result = _extract_json(text)
        assert result == '{"track": "Test"}'


class TestParseMetadataWithAI:
    """Tests for AI metadata parsing."""

    @pytest.mark.asyncio
    async def test_parse_metadata_success(
        self, mock_openai_client: MagicMock, mock_openai_response: dict, config_dir
    ) -> None:
        """Test successful metadata parsing."""
        result = await parse_metadata_with_ai(
            "test_file.mp3",
            existing=None,
            client=mock_openai_client,
        )

        assert result.key == "test_file.mp3"
        assert result.track == mock_openai_response["track"]
        assert result.artist == mock_openai_response["artist"]
        assert result.album.name == mock_openai_response["album"]["name"]
        assert result.genre == mock_openai_response["genre"]
        assert result.date == mock_openai_response["date"]

    @pytest.mark.asyncio
    async def test_parse_metadata_invalid_json(self, config_dir) -> None:
        """Test handling of invalid JSON response."""
        mock_client = AsyncMock()
        mock_completion = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "This is not valid JSON"
        mock_choice.message = mock_message
        mock_completion.choices = [mock_choice]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        with pytest.raises(RuntimeError, match="Failed to parse JSON"):
            await parse_metadata_with_ai("test.mp3", client=mock_client)

    @pytest.mark.asyncio
    async def test_parse_metadata_missing_fields(self, config_dir) -> None:
        """Test handling of response with missing fields."""
        mock_client = AsyncMock()
        mock_completion = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = '{"track": "Test"}'  # Missing most fields
        mock_choice.message = mock_message
        mock_completion.choices = [mock_choice]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        result = await parse_metadata_with_ai("test.mp3", client=mock_client)

        # Should handle missing fields gracefully
        assert result.track == "Test"
        assert result.artist == ""
        assert result.album.name == ""
        assert result.genre == ""
        assert result.date is None
