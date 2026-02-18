import argparse
import itertools
from typing import Optional
from multiprocessing.dummy import Pool

from rich.progress import Progress, TaskID

from src.scripts.sync_file import sync_file
from src.utils.file_transport import FileTransport
from src.utils.logging import setup_logging, get_logger
from src.utils.git_sync import sync_metadata
from src.utils.progress import PROGRESS_COLUMNS
from src.utils.validate import validate_path


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


@validate_path
@sync_metadata
def cmd_sync_metadata(args: argparse.Namespace, *, path, file_transport) -> None:
    """
    Handle the 'sync-metadata' command.

    This command syncs the stored metadata with the files.
    - If there is stored metadata for the file it updates the file's metadata tags to match the stored metadata, overwriting any existing tags.
    - If there is no stored metadata for the file it reads the metadata tags from the file and stores it in the metadata store.
    """

    setup_logging(verbose=args.verbose)
    logger = get_logger()

    dry_run = args.dry_run

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
