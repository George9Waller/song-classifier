import argparse
import itertools
from typing import Optional
from multiprocessing.dummy import Pool

from rich.progress import Progress, TaskID

from src.constants import DEFAULT_PATH
from src.scripts.sync_file import sync_file
from src.utils.file_transport import FileTransport, get_file_transport_for_args
from src.utils.logging import setup_logging, get_logger
from src.utils.git_sync import pull_metadata, push_metadata
from src.utils.path import validate_path_or_exit
from src.utils.progress import PROGRESS_COLUMNS


def sync_file_and_update_progress(
    filename: str,
    file_transport: FileTransport,
    initial_path: str,
    progress: Progress,
    progress_task_id: TaskID,
    dry_run: Optional[bool] = False,
) -> None:
    progress.update(progress_task_id, filename=filename, refresh=True)

    sync_file(
        filename,
        file_transport=file_transport,
        initial_path=initial_path,
        dry_run=dry_run,
    )

    progress.advance(progress_task_id)


def cmd_sync_metadata(args: argparse.Namespace) -> None:
    """
    Handle the 'sync-metadata' command.

    This command syncs the stored metadata with the files.
    - If there is stored metadata for the file it updates the file's metadata tags to match the stored metadata, overwriting any existing tags.
    - If there is no stored metadata for the file it reads the metadata tags from the file and stores it in the metadata store.
    """

    setup_logging(verbose=args.verbose)
    logger = get_logger()

    sync = not args.no_sync
    dry_run = args.dry_run

    file_transport = get_file_transport_for_args(args)
    path = validate_path_or_exit(
        args.path or DEFAULT_PATH, file_transport=file_transport
    )

    # Pull metadata from git if configured
    if sync:
        pull_metadata()

    logger.info(
        f"Syncing metadata for files in {path} using {file_transport.__class__.__name__}"
    )
    files = list(file_transport.list_files(path))

    pool = Pool(processes=10)

    with Progress(*PROGRESS_COLUMNS) as progress:
        task = progress.add_task("Syncing metadata...", total=len(files), filename="")

        pool.starmap(
            sync_file_and_update_progress,
            zip(
                files,
                itertools.repeat(file_transport),
                itertools.repeat(path),
                itertools.repeat(progress),
                itertools.repeat(task),
                itertools.repeat(dry_run),
            ),
        )
        pool.close()
        pool.join()

    if sync and not dry_run:
        push_metadata()
