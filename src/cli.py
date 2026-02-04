"""CLI entry point for song-classifier."""

import argparse
import asyncio
import os
import sys
from typing import Union

from src.utils.ai_metadata import MissingAPIKeyError, validate_api_key
from src.utils.config import (
    get_or_create_config_dir,
    get_webdav_credentials,
    set_webdav_credentials,
)
from src.utils.file_transport import FileTransport, LocalTransport, WebdavTransport, TransportType
from src.utils.git_sync import get_sync_repo, set_sync_repo, pull_metadata, push_metadata
from src.utils.logging import setup_logging, get_logger
from src.main import classify_filename

__version__ = "0.1.0"


def validate_path(path: str) -> str:
    """Validate and normalize a directory path.

    Args:
        path: Path to validate.

    Returns:
        Absolute, normalized path.

    Raises:
        ValueError: If path is invalid.
    """
    path = os.path.abspath(path)
    if not os.path.exists(path):
        raise ValueError(f"Path does not exist: {path}")
    if not os.path.isdir(path):
        raise ValueError(f"Path is not a directory: {path}")
    # Resolve symlinks and check for path traversal
    real_path = os.path.realpath(path)
    return real_path


async def process_files(
    files: list[str],
    base_path: str,
    file_transport: Union[LocalTransport, WebdavTransport],
    skip_processed: bool,
    skip_in_metadata: bool,
    dry_run: bool,
    verbose: bool,
) -> int:
    """Process a list of audio files.

    Args:
        files: List of relative file paths.
        base_path: Base directory path.
        file_transport: Transport for file operations.
        skip_processed: Skip already-processed files.
        skip_in_metadata: Skip files already in metadata.csv.
        dry_run: Show what would be done without making changes.
        verbose: Enable verbose output.

    Returns:
        Number of files processed.
    """
    logger = get_logger()
    total = len(files)
    processed = 0

    for i, filename in enumerate(files, 1):
        logger.info(f"[{i}/{total}] {filename}")
        result = await classify_filename(
            filename,
            base_path,
            file_transport=file_transport,
            skip_processed_files=skip_processed,
            skip_files_in_metadata=skip_in_metadata,
            dry_run=dry_run,
        )
        if result is not None:
            processed += 1

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
    try:
        path = validate_path(args.path or ".")
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)

    transport_type = TransportType.WEBDAV if args.webdav else TransportType.LOCAL
    skip_processed = not args.no_skip_processed
    skip_in_metadata = not args.no_skip_in_metadata

    # Pull metadata from git if configured
    if not args.no_sync:
        pull_metadata()

    # Create transport with optional WebDAV credentials
    webdav_user = args.webdav_user if hasattr(args, "webdav_user") else None
    webdav_pass = args.webdav_password if hasattr(args, "webdav_password") else None

    file_transport = FileTransport(
        transport_type,
        webdav_host=args.webdav,
        webdav_username=webdav_user,
        webdav_password=webdav_pass,
    )

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
                args.verbose,
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


def cmd_config_show(args: argparse.Namespace) -> None:
    """Handle the 'config show' subcommand."""
    setup_logging(verbose=False)
    print(f"Config directory: {get_or_create_config_dir()}")
    repo = get_sync_repo()
    print(f"Sync repository: {repo or '(not configured)'}")
    webdav_user, webdav_pass = get_webdav_credentials()
    print(f"WebDAV username: {webdav_user or '(not configured)'}")
    print(f"WebDAV password: {'***' if webdav_pass else '(not configured)'}")


def cmd_config_set_sync_repo(args: argparse.Namespace) -> None:
    """Handle the 'config set-sync-repo' subcommand."""
    setup_logging(verbose=False)
    set_sync_repo(args.url)


def cmd_config_set_webdav(args: argparse.Namespace) -> None:
    """Handle the 'config set-webdav' subcommand."""
    logger = setup_logging(verbose=False)
    set_webdav_credentials(args.user, args.password)
    logger.info("WebDAV credentials saved")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="song-classifier",
        description="Auto-tag music files using AI to infer metadata from filenames",
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Process command (default behavior)
    process_parser = subparsers.add_parser(
        "process",
        help="Process audio files in a directory",
    )
    process_parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Directory to scan (default: current directory)",
    )
    process_parser.add_argument(
        "--webdav",
        metavar="HOST",
        help="WebDAV host URL to use instead of local filesystem",
    )
    process_parser.add_argument(
        "--webdav-user",
        metavar="USER",
        help="WebDAV username (or set WEBDAV_USERNAME env var)",
    )
    process_parser.add_argument(
        "--webdav-password",
        metavar="PASS",
        help="WebDAV password (or set WEBDAV_PASSWORD env var)",
    )
    process_parser.add_argument(
        "--no-skip-processed",
        action="store_true",
        help="Process files even if marked as processed",
    )
    process_parser.add_argument(
        "--no-skip-in-metadata",
        action="store_true",
        help="Process files even if in metadata.csv",
    )
    process_parser.add_argument(
        "--no-sync",
        action="store_true",
        help="Skip git sync even if a repository is configured",
    )
    process_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    process_parser.add_argument(
        "-V", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    process_parser.set_defaults(func=cmd_process)

    # Config command group
    config_parser = subparsers.add_parser("config", help="Configuration management")
    config_subparsers = config_parser.add_subparsers(dest="config_command", help="Config commands")

    # config show
    config_show_parser = config_subparsers.add_parser("show", help="Show current configuration")
    config_show_parser.set_defaults(func=cmd_config_show)

    # config set-sync-repo
    config_sync_parser = config_subparsers.add_parser(
        "set-sync-repo",
        help="Configure git repository URL for syncing metadata",
    )
    config_sync_parser.add_argument("url", help="Git repository URL")
    config_sync_parser.set_defaults(func=cmd_config_set_sync_repo)

    # config set-webdav
    config_webdav_parser = config_subparsers.add_parser(
        "set-webdav",
        help="Configure WebDAV credentials",
    )
    config_webdav_parser.add_argument("--user", help="WebDAV username")
    config_webdav_parser.add_argument("--password", help="WebDAV password")
    config_webdav_parser.set_defaults(func=cmd_config_set_webdav)

    args = parser.parse_args()

    # Handle no command (default to process for backward compatibility)
    if args.command is None:
        # Check if any legacy arguments were passed
        # Re-parse with process as default
        legacy_parser = argparse.ArgumentParser(
            prog="song-classifier",
            description="Auto-tag music files using AI to infer metadata from filenames",
        )
        legacy_parser.add_argument(
            "path",
            nargs="?",
            default=None,
            help="Directory to scan (default: current directory)",
        )
        legacy_parser.add_argument(
            "-v", "--version",
            action="version",
            version=f"%(prog)s {__version__}",
        )
        legacy_parser.add_argument(
            "--webdav",
            metavar="HOST",
            help="WebDAV host URL to use instead of local filesystem",
        )
        legacy_parser.add_argument(
            "--webdav-user",
            metavar="USER",
            help="WebDAV username",
        )
        legacy_parser.add_argument(
            "--webdav-password",
            metavar="PASS",
            help="WebDAV password",
        )
        legacy_parser.add_argument(
            "--no-skip-processed",
            action="store_true",
            help="Process files even if marked as processed",
        )
        legacy_parser.add_argument(
            "--no-skip-in-metadata",
            action="store_true",
            help="Process files even if in metadata.csv",
        )
        legacy_parser.add_argument(
            "--sync-repo",
            metavar="URL",
            help="Configure git repository URL for syncing metadata (stored in config)",
        )
        legacy_parser.add_argument(
            "--no-sync",
            action="store_true",
            help="Skip git sync even if a repository is configured",
        )
        legacy_parser.add_argument(
            "--show-config",
            action="store_true",
            help="Show current configuration and exit",
        )
        legacy_parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without making changes",
        )
        legacy_parser.add_argument(
            "-V", "--verbose",
            action="store_true",
            help="Enable verbose output",
        )

        args = legacy_parser.parse_args()

        # Handle legacy --sync-repo
        if args.sync_repo:
            setup_logging(verbose=False)
            set_sync_repo(args.sync_repo)
            return

        # Handle legacy --show-config
        if args.show_config:
            cmd_config_show(args)
            return

        # Default to process command
        cmd_process(args)
        return

    # Handle config command without subcommand
    if args.command == "config" and (not hasattr(args, "config_command") or args.config_command is None):
        cmd_config_show(args)
        return

    # Execute the command
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
