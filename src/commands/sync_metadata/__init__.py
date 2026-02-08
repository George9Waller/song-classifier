import argparse
from dataclasses import dataclass
from typing import Optional, Type

from rich.progress import Progress
from rich.console import Console

from src.data.models import TrackMetadata, AlbumMetadata
from src.constants import DEFAULT_PATH
from src.data import get_file_metadata, upsert_album_metadata, upsert_track_metadata
from src.utils.file_metadata import read_file_metadata, write_file_metadata
from src.utils.file_transport import FileTransport, get_file_transport_for_args
from src.utils.logging import setup_logging, get_logger
from src.utils.git_sync import pull_metadata, push_metadata
from src.utils.path import validate_path_or_exit
from src.utils.progress import PROGRESS_COLUMNS


def diff_metadata(
    stored: Optional[TrackMetadata], file: Optional[TrackMetadata]
) -> list[dict]:
    diffs = []
    for attr, field in stored.__dataclass_fields__.items():
        if attr == "key":
            continue

        if field.type.__name__ == AlbumMetadata.__name__:
            nested_diffs = diff_metadata(getattr(stored, attr), getattr(file, attr))
            if nested_diffs:
                diffs.append((attr, nested_diffs))
        else:
            stored_value = getattr(stored, attr)
            file_value = getattr(file, attr)
            if stored_value != file_value:
                diffs.append((attr, {"stored": stored_value, "file": file_value}))
    return diffs


def render_diffs(diffs: list[dict], indent: int = 0) -> str:
    console = Console()
    for attr, diff in diffs:
        if isinstance(diff, dict):
            stored_value = diff["stored"]
            file_value = diff["file"]
            console.print(f"{' ' * indent}- [red]{attr}: {file_value}[/red]")
            console.print(f"{' ' * indent}+ [green]{attr}: {stored_value}[/green]")

        # Nested diffs for AlbumMetadata
        elif isinstance(diff, list):
            console.print(f"{' ' * indent}- [blue]{attr}:[/blue]")
            render_diffs(diff, indent + 2)


def sync_file(
    filename: str,
    *,
    file_transport: FileTransport,
    initial_path: str,
    dry_run: Optional[bool] = False,
) -> None:
    logger = get_logger()

    file_basename = file_transport.get_basename_from_path(filename)

    stored_metadata = get_file_metadata(key=file_basename)

    loaded_file = file_transport.load_file(filename, initial_path)
    cleanup = lambda: file_transport.cleanup_local_file_if_needed(loaded_file)

    file_metadata = read_file_metadata(loaded_file)
    file_metadata.key = file_transport.get_basename_from_path(loaded_file)

    diffs = diff_metadata(stored_metadata, file_metadata)

    if not diffs:
        logger.debug(f"Metadata for {filename} is already up to date, skipping.")
        cleanup()
        return

    if stored_metadata is not None:
        render_diffs(diffs)
        if dry_run:
            logger.info(
                f"Would update metadata for {filename} to match stored metadata."
            )
        else:
            logger.info(f"Updating metadata for {filename} to match stored metadata.")
            write_file_metadata(loaded_file, stored_metadata)
            file_transport.save_file(loaded_file, filename, initial_path)
        cleanup()
        return

    if file_metadata is not None:
        if dry_run:
            logger.info(f"Would store metadata for {filename} from file metadata.")
        else:
            logger.info(f"Storing metadata for {filename} from file metadata.")
            upsert_album_metadata(file_metadata.album)
            upsert_track_metadata(file_metadata)

    cleanup()


def cmd_sync_metadata(args: argparse.Namespace) -> None:
    """
    Handle the 'sync-metadata' command.

    This command syncs the stored metadata with the files.
    - If there is stored metadata for the file it updates the file's metadata tags to match the stored metadata, overwriting any existing tags.
    - If there is no stored metadata for the file it reads the metadata tags from the file and stores it in the metadata store.
    """

    setup_logging(verbose=args.verbose)

    sync = not args.no_sync
    dry_run = args.dry_run

    path = validate_path_or_exit(args.path or DEFAULT_PATH)
    file_transport = get_file_transport_for_args(args)

    # Pull metadata from git if configured
    if sync:
        pull_metadata()

    files = list(file_transport.list_files(path))

    with Progress(*PROGRESS_COLUMNS) as progress:
        task = progress.add_task("Syncing metadata...", total=len(files), filename="")

        for filename in files:
            progress.update(task, filename=filename, refresh=True)

            sync_file(
                filename,
                file_transport=file_transport,
                initial_path=path,
                dry_run=dry_run,
            )

            progress.advance(task)

    if sync and not dry_run:
        push_metadata()
