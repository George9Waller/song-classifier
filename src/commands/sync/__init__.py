import argparse
import os
import shutil
import sys

from rich.progress import Progress

from src.constants import DEFAULT_PATH
from src.utils.file_transport import (
    FileTransport,
    LocalTransport,
    TransportType,
    WebdavTransport,
    get_file_transport_for_args,
)
from src.utils.logging import get_logger, setup_logging
from src.utils.path import validate_path_or_exit
from src.utils.progress import PROGRESS_COLUMNS


def get_dest_transport(args: argparse.Namespace) -> FileTransport:
    """Create the destination FileTransport from CLI args."""
    dest_webdav = getattr(args, "dest_webdav", None)
    if dest_webdav:
        return FileTransport(
            transport_type=TransportType.WEBDAV,
            webdav_host=dest_webdav,
            webdav_username=getattr(args, "dest_webdav_user", None),
            webdav_password=getattr(args, "dest_webdav_password", None),
        )
    return FileTransport(transport_type=TransportType.LOCAL)


def sync_file(
    relative_path: str,
    *,
    source_transport,
    source_root: str,
    dest_transport,
    dest_root: str,
    existing_dest_files: set[str],
    dry_run: bool,
) -> bool:
    """Sync a single file from source to destination.

    Returns True if the file was copied (or would be in dry-run), False if skipped or failed.
    """
    logger = get_logger()

    if relative_path in existing_dest_files:
        logger.debug(f"Skipping {relative_path} (already exists at destination)")
        return False

    if dry_run:
        logger.info(f"Would copy {relative_path}")
        return True

    local_path = None
    try:
        local_path = source_transport.load_file(relative_path, source_root)

        if isinstance(dest_transport, WebdavTransport):
            dest_transport.save_file(local_path, dest_root, relative_path)
        else:
            dest_path = os.path.join(dest_root, relative_path)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            shutil.copy2(local_path, dest_path)

        logger.info(f"Copied {relative_path}")
        return True
    except OSError as e:
        logger.error(f"Failed to copy {relative_path}: {e}")
        return False
    finally:
        if local_path:
            source_transport.cleanup_local_file_if_needed(local_path)


def cmd_sync(args: argparse.Namespace) -> None:
    """
    Handle the 'sync' command.

    This command syncs files between 2 locations. It can be used to sync files between:
    - 2 different local directories / removable media
    - a local directory and a remote WebDAV storage
    - a remote WebDAV storage and a local directory
    - 2 remote WebDAV storages (source and destination each have their own WebDAV flags)
    """
    setup_logging(verbose=args.verbose)
    logger = get_logger()

    if not getattr(args, "dest", None):
        logger.error("Destination path is required (--dest)")
        sys.exit(1)

    dry_run = args.dry_run

    # Source transport and path
    source_transport = get_file_transport_for_args(args)
    if isinstance(source_transport, LocalTransport):
        source_path = validate_path_or_exit(
            args.path or DEFAULT_PATH, file_transport=source_transport
        )
    else:
        source_path = args.path or DEFAULT_PATH

    # Destination transport and path
    dest_transport = get_dest_transport(args)
    if isinstance(dest_transport, LocalTransport):
        os.makedirs(args.dest, exist_ok=True)
        dest_path = validate_path_or_exit(args.dest, file_transport=dest_transport)
    else:
        dest_path = args.dest

    # Pre-collect existing destination files for skip check
    existing_dest_files: set[str] = set()
    try:
        for f in dest_transport.list_files(dest_path):
            existing_dest_files.add(f)
    except Exception:
        pass  # Destination might be empty or not yet created

    copied = 0
    skipped = 0

    with Progress(*PROGRESS_COLUMNS) as progress:
        task = progress.add_task("Syncing files...", filename="")

        for filename in source_transport.list_files(source_path):
            progress.update(task, filename=filename, refresh=True)

            if sync_file(
                filename,
                source_transport=source_transport,
                source_root=source_path,
                dest_transport=dest_transport,
                dest_root=dest_path,
                existing_dest_files=existing_dest_files,
                dry_run=dry_run,
            ):
                copied += 1
            else:
                skipped += 1

            progress.advance(task)

    action = "Would copy" if dry_run else "Copied"
    logger.info(f"{action} {copied} files, skipped {skipped} files")
