import os
from datetime import datetime

import pytest

from src.data.models import AlbumMetadata, TrackMetadata
from src.utils.file_metadata import (
    read_file_metadata,
    write_file_metadata,
    is_already_processed,
)


def _get_sample_file_path(extension: str, *, name: str = "sample") -> str:
    original_path = os.path.join(
        os.path.dirname(__file__), "test_data", f"{name}.{extension}"
    )

    now = datetime.now().timestamp()
    temp_path = os.path.join(
        os.path.dirname(__file__), "test_data", f"{name}_{now}.{extension}"
    )

    with open(original_path, "rb") as src, open(temp_path, "wb") as dst:
        dst.write(src.read())

    return temp_path


def _teardown_sample_file(path: str) -> None:
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def sample_mp3_file():
    temp_path = _get_sample_file_path("mp3")

    yield temp_path

    _teardown_sample_file(temp_path)


@pytest.fixture
def sample_mp4_file():
    temp_path = _get_sample_file_path("mp4")

    yield temp_path

    _teardown_sample_file(temp_path)


@pytest.fixture
def sample_m4a_file():
    temp_path = _get_sample_file_path("m4a")

    yield temp_path

    _teardown_sample_file(temp_path)


@pytest.fixture
def sample_wav_file():
    temp_path = _get_sample_file_path("wav")

    yield temp_path

    _teardown_sample_file(temp_path)


@pytest.fixture
def sample_flac_file():
    temp_path = _get_sample_file_path("flac")

    yield temp_path

    _teardown_sample_file(temp_path)


@pytest.fixture
def sample_opus_file():
    temp_path = _get_sample_file_path("opus")

    yield temp_path

    _teardown_sample_file(temp_path)


@pytest.fixture
def sample_ogg_opus_file():
    temp_path = _get_sample_file_path("ogg", name="opus")

    yield temp_path

    _teardown_sample_file(temp_path)


@pytest.fixture
def sample_ogg_file():
    temp_path = _get_sample_file_path("ogg", name="vorbis")

    yield temp_path

    _teardown_sample_file(temp_path)


ALL_FILE_FIXTURES = [
    "sample_mp3_file",
    "sample_mp4_file",
    "sample_m4a_file",
    "sample_wav_file",
    "sample_flac_file",
    "sample_opus_file",
    "sample_ogg_opus_file",
    "sample_ogg_file",
]


@pytest.fixture(scope="function")
def track_metadata():
    return TrackMetadata(
        key="test_key",
        track="Title",
        artist="Artist",
        album=AlbumMetadata(
            name="Album",
            artist="Album Artist",
        ),
        genre="Genre",
        date="2026-02-09",
    )


@pytest.mark.parametrize("sample_file_fixture_name", ALL_FILE_FIXTURES)
def test_file_metadata(request, sample_file_fixture_name, track_metadata):
    sample_file = request.getfixturevalue(sample_file_fixture_name)

    # Test writing metadata to an MP3 file
    write_file_metadata(sample_file, track_metadata)

    # Test reading metadata from the MP3 file
    track_metadata.key = sample_file
    read_metadata = read_file_metadata(sample_file)
    assert read_metadata == track_metadata


@pytest.mark.parametrize("sample_file_fixture_name", ALL_FILE_FIXTURES)
def test_is_already_processed(request, sample_file_fixture_name, track_metadata):
    sample_file = request.getfixturevalue(sample_file_fixture_name)

    # Before writing metadata
    assert is_already_processed(sample_file) is False

    # Write metadata to the file
    write_file_metadata(sample_file, track_metadata)

    # After writing metadata
    assert is_already_processed(sample_file) is True
