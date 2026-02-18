"""Core classification orchestration for song-classifier."""

from typing import Optional, Union

from src.data import get_file_metadata, upsert_album_metadata, upsert_track_metadata
from src.data.models import TrackMetadata
from src.utils.ai_metadata import parse_metadata_with_ai
from src.utils.file_metadata import (
    read_file_metadata,
    write_file_metadata,
    is_already_processed,
)
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
    auto_accept_metadata: bool = False,
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
    logger.debug(f"Processing: {filename}")

    stored_metadata = get_file_metadata(key=filename)

    if skip_files_in_metadata and stored_metadata is not None:
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
        file_transport.cleanup_local_file_if_needed(local_path)
        return None

    # Get metadata from stored metadata or ai
    if stored_metadata is not None:
        metadata_to_set = stored_metadata
    else:
        # AI parse using filename
        logger.debug("  Inferring metadata with AI")
        metadata_to_set = await parse_metadata_with_ai(filename, existing)

    if dry_run:
        logger.info(f"  Would set: {metadata_to_set.track} by {metadata_to_set.artist}")
        logger.info(
            f"    Album: {metadata_to_set.album.name} ({metadata_to_set.album.artist})"
        )
        logger.info(f"    Genre: {metadata_to_set.genre}, Date: {metadata_to_set.date}")
        file_transport.cleanup_local_file_if_needed(local_path)
        return metadata_to_set

    if auto_accept_metadata:
        confirmed = metadata_to_set
    else:
        # UI confirm (blocking - Textual handles its own event loop)
        confirmed = await confirm_metadata(metadata_to_set)

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
    file_transport.cleanup_local_file_if_needed(local_path)

    logger.info(f"  Done: {confirmed.track} by {confirmed.artist}")
    return confirmed
