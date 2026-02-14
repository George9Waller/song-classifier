from typing import Optional

from rich.console import Console

from src.data.models import TrackMetadata, AlbumMetadata
from src.data import get_file_metadata, upsert_album_metadata, upsert_track_metadata
from src.utils.file_metadata import read_file_metadata, write_file_metadata
from src.utils.file_transport import FileTransport
from src.utils.logging import get_logger


def diff_metadata(
    stored: Optional[TrackMetadata | AlbumMetadata],
    file: Optional[TrackMetadata | AlbumMetadata],
) -> list[dict]:
    metadata_class = stored or file

    # This should never happen as this method is only called when at least one metadata source is present
    if metadata_class is None:
        return []

    diffs = []
    for attr, field in metadata_class.__dataclass_fields__.items():
        if attr == "key":
            continue

        if field.type.__name__ in {TrackMetadata.__name__, AlbumMetadata.__name__}:
            nested_diffs = diff_metadata(
                getattr(stored, attr, None), getattr(file, attr, None)
            )
            if nested_diffs:
                diffs.append((attr, nested_diffs))
        else:
            stored_value = getattr(stored, attr, None)
            file_value = getattr(file, attr, None)
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
    if file_metadata is not None:
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
            file_transport.save_file(loaded_file, initial_path, filename)
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
