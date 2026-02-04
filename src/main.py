"""Core classification orchestration for song-classifier."""

import os
from typing import Optional, Union

from src.data import get_file_metadata, upsert_album_metadata, upsert_track_metadata
from src.data.models import TrackMetadata
from src.utils.ai_metadata import parse_metadata_with_ai
from src.utils.file_metadata import read_file_metadata, write_file_metadata, is_already_processed
from src.utils.file_transport import LocalTransport, WebdavTransport
from src.utils.logging import get_logger
from src.utils.ui_confirm import confirm_metadata


async def classify_filename(
    filename: str,
    base_path: str,
    file_transport: Union[LocalTransport, WebdavTransport],
    skip_processed_files: bool = True,
    skip_files_in_metadata: bool = False,
    dry_run: bool = False,
) -> Optional[TrackMetadata]:
    """Classify a single audio file using AI metadata inference.

    Args:
        filename: Relative path to the audio file.
        base_path: Base directory path.
        file_transport: Transport for file operations.
        skip_processed_files: Skip files already marked as processed.
        skip_files_in_metadata: Skip files already in metadata.csv.
        dry_run: If True, show what would be done without making changes.

    Returns:
        The confirmed TrackMetadata if processed, None if skipped.
    """
    logger = get_logger()
    logger.info(f"Processing: {filename}")

    if skip_files_in_metadata and get_file_metadata(key=filename):
        logger.info("  Skipping: already in metadata")
        return None

    # Ensure temp local copy
    logger.debug("  Loading file locally")
    local_path = file_transport.load_file(filename, base_path)

    # Read any existing tags from the downloaded file
    logger.debug("  Reading existing metadata")
    existing = read_file_metadata(local_path)

    # If already processed, skip and delete temp
    if skip_processed_files and is_already_processed(local_path):
        logger.info("  Skipping: already processed")
        if file_transport.cleanup_local_files:
            try:
                os.remove(local_path)
            except OSError:
                pass
        return None

    # AI parse using filename
    logger.debug("  Inferring metadata with AI")
    ai_metadata = await parse_metadata_with_ai(filename, existing)

    if dry_run:
        logger.info(f"  Would set: {ai_metadata.track} by {ai_metadata.artist}")
        logger.info(f"    Album: {ai_metadata.album.name} ({ai_metadata.album.artist})")
        logger.info(f"    Genre: {ai_metadata.genre}, Date: {ai_metadata.date}")
        if file_transport.cleanup_local_files:
            try:
                os.remove(local_path)
            except OSError:
                pass
        return ai_metadata

    # UI confirm (blocking - Textual handles its own event loop)
    confirmed = confirm_metadata(ai_metadata)

    # Upsert album and track CSV metadata
    logger.debug("  Saving to metadata CSV")
    upsert_album_metadata(confirmed.album)
    upsert_track_metadata(confirmed)

    # Write the confirmed tags back into the local file
    logger.debug("  Writing file metadata")
    write_file_metadata(local_path, confirmed)

    # Upload and replace original on WebDAV
    logger.debug("  Saving file")
    file_transport.save_file(local_path, base_path, filename)

    # Clean up local temp file
    if file_transport.cleanup_local_files:
        try:
            os.remove(local_path)
        except OSError:
            pass

    logger.info(f"  Done: {confirmed.track} by {confirmed.artist}")
    return confirmed
