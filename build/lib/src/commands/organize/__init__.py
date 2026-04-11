import argparse

from rich.progress import Progress

from src.data import get_file_metadata
from src.constants import EXCLUDED_FILENAMES_FOR_EMPTY_DIRECTORY_DELETION
from src.utils.file_transport import FileTransport
from src.utils.logging import get_logger, setup_logging
from src.utils.progress import PROGRESS_COLUMNS
from src.utils.git_sync import sync_metadata
from src.utils.validate import validate_path


def get_new_path_for_file(filename: str, file_transport: FileTransport) -> str:
    logger = get_logger()

    basename = file_transport.get_basename_from_path(filename)
    metadata = get_file_metadata(key=basename)

    if metadata is None or isinstance(metadata, list):
        logger.warning(
            f"No metadata found for {filename}, run 'process' command to classify files first. Placing file in 'Unknown' directory."
        )
        new_path = f"Unknown/{basename}"

    else:
        artist = metadata.artist
        album = metadata.album.name
        new_path = f"{artist}/{album}/{basename}"

    return new_path


def orgnize_file(
    *, original_path: str, new_path: str, file_transport: FileTransport, root: str
) -> None:
    logger = get_logger()

    file_transport.move_file(original_path, new_path=new_path, initial_path=root)
    logger.info(f"Moved {original_path} -> {new_path}")


def clear_empty_directories(path: str, file_transport: FileTransport) -> None:
    logger = get_logger()

    for dirpath, dirnames, filenames in file_transport.walk(path):
        filenames_with_excluded = (
            set(filenames) - EXCLUDED_FILENAMES_FOR_EMPTY_DIRECTORY_DELETION
        )
        if dirnames or filenames_with_excluded:
            continue

        file_transport.delete_directory_if_exists(dirpath)
        logger.info(f"Deleted empty directory: {dirpath}")

        parent = file_transport.get_parent_directory(dirpath)
        if parent and parent.startswith(path):
            logger.debug(f"Checking parent directory for cleanup: {parent}")
            clear_empty_directories(parent, file_transport)


@validate_path
@sync_metadata
def cmd_organize(args: argparse.Namespace, *, path, file_transport) -> None:
    """
    Handle the 'organize' command.

    This command uses the stored metadata for files to origanize the files into directories for each artist and subdirectories for each album.
    """
    setup_logging(verbose=args.verbose)
    logger = get_logger()

    dry_run = args.dry_run

    # Collect files
    logger.info(f"Scanning {path}...")
    files = list(file_transport.list_files(path))
    logger.info(f"Found {len(files)} audio files")

    # Move files to /artist/album directories based on metadata
    with Progress(*PROGRESS_COLUMNS) as progress:
        task = progress.add_task("Organizing files...", total=len(files), filename="")

        for filename in files:
            progress.update(task, filename=filename, refresh=True)

            new_path = get_new_path_for_file(filename, file_transport=file_transport)
            if new_path == filename:
                logger.debug(
                    f"File {filename} is already in the correct location, skipping."
                )
                progress.advance(task)
                continue

            if dry_run:
                logger.info(f"Would move {filename} -> {new_path}")
                progress.advance(task)
                continue

            orgnize_file(
                original_path=filename,
                new_path=new_path,
                file_transport=file_transport,
                root=path,
            )

            progress.advance(task)

    if not dry_run:
        # Clear up empty directories
        clear_empty_directories(path, file_transport)
