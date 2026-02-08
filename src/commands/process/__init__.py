import argparse
import asyncio
import sys
from typing import Union

from rich.progress import Progress

from src.constants import DEFAULT_PATH
from src.scripts import classify_filename
from src.utils.ai_metadata import MissingAPIKeyError, validate_api_key
from src.utils.file_transport import (
    LocalTransport,
    WebdavTransport,
    get_file_transport_for_args,
)
from src.utils.git_sync import pull_metadata, push_metadata
from src.utils.logging import setup_logging
from src.utils.path import validate_path_or_exit
from src.utils.progress import PROGRESS_COLUMNS


async def process_files(
    files: list[str],
    base_path: str,
    file_transport: Union[LocalTransport, WebdavTransport],
    skip_processed: bool,
    skip_in_metadata: bool,
    dry_run: bool,
    auto_accept_metadata: bool = False,
) -> int:
    """Process a list of audio files.

    Args:
        files: List of relative file paths.
        base_path: Base directory path.
        file_transport: Transport for file operations.
        skip_processed: Skip already-processed files.
        skip_in_metadata: Skip files already in metadata.csv.
        dry_run: Show what would be done without making changes.

    Returns:
        Number of files processed.
    """
    processed = 0

    with Progress(*PROGRESS_COLUMNS) as progress:
        task = progress.add_task("Processing...", total=len(files), filename="")

        for filename in files:
            base_filename = file_transport.get_basename_from_path(filename)
            progress.update(task, filename=filename, refresh=True)
            result = await classify_filename(
                base_filename,
                base_path,
                file_transport=file_transport,
                skip_processed_files=skip_processed,
                skip_files_in_metadata=skip_in_metadata,
                dry_run=dry_run,
                auto_accept_metadata=auto_accept_metadata,
            )
            if result is not None:
                processed += 1
            progress.advance(task)

    return processed


def cmd_process(args: argparse.Namespace) -> None:
    """Handle the 'process' subcommand."""
    logger = setup_logging(verbose=args.verbose)

    # Validate API key early
    if not args.dry_run:
        try:
            validate_api_key()
        except MissingAPIKeyError as e:
            logger.error(str(e))
            sys.exit(1)

    # Validate path
    path = validate_path_or_exit(args.path or DEFAULT_PATH)

    skip_processed = not args.no_skip_processed
    skip_in_metadata = not args.no_skip_in_metadata

    # Pull metadata from git if configured
    if not args.no_sync:
        pull_metadata()

    file_transport = get_file_transport_for_args(args)

    # Collect files
    logger.info(f"Scanning {path}...")
    files = list(file_transport.list_files(path))
    logger.info(f"Found {len(files)} audio files")

    if not files:
        logger.info("No audio files found")
        return

    files_processed = 0

    try:
        files_processed = asyncio.run(
            process_files(
                files,
                path,
                file_transport,
                skip_processed,
                skip_in_metadata,
                args.dry_run,
                auto_accept_metadata=args.yes,
            )
        )
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        # Still try to push any changes made before interrupt
        if not args.no_sync and files_processed > 0:
            push_metadata()
        sys.exit(130)

    logger.info(f"Processed {files_processed} files")

    # Push metadata to git if configured
    if not args.no_sync and not args.dry_run:
        push_metadata()
