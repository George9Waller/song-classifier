import argparse
import asyncio
from typing import Union

from rich.progress import Progress

from src.scripts import classify_filename
from src.utils.file_transport import LocalTransport, WebdavTransport
from src.utils.git_sync import sync_metadata
from src.utils.logging import setup_logging
from src.utils.progress import PROGRESS_COLUMNS
from src.utils.validate import has_openai_api_key_set, validate_path


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


@has_openai_api_key_set
@validate_path
@sync_metadata
def cmd_process(args: argparse.Namespace, *, path, file_transport) -> None:
    """Handle the 'process' subcommand."""
    logger = setup_logging(verbose=args.verbose)

    skip_processed = not args.no_skip_processed
    skip_in_metadata = not args.no_skip_in_metadata

    # Collect files
    logger.info(f"Scanning {path}...")
    files = list(file_transport.list_files(path))
    logger.info(f"Found {len(files)} audio files")

    if not files:
        logger.info("No audio files found")
        return

    files_processed = 0

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

    logger.info(f"Processed {files_processed} files")
