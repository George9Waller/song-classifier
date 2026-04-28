"""CLI entry point for song-classifier."""

import argparse

from src.commands.config import (
    cmd_config_show,
    cmd_config_set_webdav,
    cmd_config_set_sync_repo,
)
from src.commands.editor import cmd_editor
from src.commands.organize import cmd_organize
from src.commands.process import cmd_process
from src.commands.sync import cmd_sync
from src.commands.sync_metadata import cmd_sync_metadata
from src.commands.yt_dlp import (
    cmd_yt_dlp_add,
    cmd_yt_dlp_download,
    cmd_yt_dlp_show,
    cmd_yt_dlp_remove,
)
from src.utils.git_sync import set_sync_repo
from src.utils.logging import setup_logging

__version__ = "0.1.0"


FILE_TRANSPORT_ARGUMENTS = [
    (
        "path",
        {
            "nargs": "?",
            "default": None,
            "help": "Directory to scan (default: current directory)",
        },
    ),
    (
        "--webdav",
        {
            "metavar": "HOST",
            "help": "WebDAV base URL to use instead of local filesystem",
        },
    ),
    (
        "--webdav-user",
        {
            "metavar": "USER",
            "help": "WebDAV username (or set WEBDAV_USERNAME env var)",
        },
    ),
    (
        "--webdav-password",
        {
            "metavar": "PASS",
            "help": "WebDAV password (or set WEBDAV_PASSWORD env var)",
        },
    ),
]


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="song-classifier",
        description="Auto-tag music files using AI to infer metadata from filenames",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Process command (default behavior)
    process_parser = subparsers.add_parser(
        "process",
        help="Process audio files in a directory",
    )
    for name, arg in FILE_TRANSPORT_ARGUMENTS:
        process_parser.add_argument(name, **arg)
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
        "-y",
        "--yes",
        action="store_true",
        help="Automatically confirm all metadata without confirming in a UI (use with caution)",
    )
    process_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    process_parser.add_argument(
        "-V",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    process_parser.set_defaults(func=cmd_process)

    # Organize command group
    organize_parser = subparsers.add_parser(
        "organize",
        help="Organize files into Artist/Album/ directory structure based on metadata",
    )
    for name, arg in FILE_TRANSPORT_ARGUMENTS:
        organize_parser.add_argument(name, **arg)
    organize_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    organize_parser.add_argument(
        "-V", "--verbose", action="store_true", help="Enable verbose output"
    )
    organize_parser.set_defaults(func=cmd_organize)

    # Sync metadata command group
    sync_parser = subparsers.add_parser(
        "sync-metadata",
        help="Sync stored metadata with file metadata tags (update file tags to match stored metadata or store file tags if no stored metadata)",
    )
    for name, arg in FILE_TRANSPORT_ARGUMENTS:
        sync_parser.add_argument(name, **arg)
    sync_parser.add_argument(
        "--no-sync",
        action="store_true",
        help="Skip git sync even if a repository is configured",
    )
    sync_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    sync_parser.add_argument(
        "-V", "--verbose", action="store_true", help="Enable verbose output"
    )
    sync_parser.set_defaults(func=cmd_sync_metadata)

    # Sync command (copy files from source to destination)
    sync_files_parser = subparsers.add_parser(
        "sync",
        help="Sync audio files from source to destination (local or WebDAV)",
    )
    for name, arg in FILE_TRANSPORT_ARGUMENTS:
        sync_files_parser.add_argument(name, **arg)
    sync_files_parser.add_argument(
        "--dest",
        required=True,
        metavar="PATH",
        help="Destination directory (local path or WebDAV remote path)",
    )
    sync_files_parser.add_argument(
        "--dest-webdav",
        metavar="HOST",
        help="WebDAV base URL for the destination",
    )
    sync_files_parser.add_argument(
        "--dest-webdav-user",
        metavar="USER",
        help="WebDAV username for destination (or set WEBDAV_USERNAME env var)",
    )
    sync_files_parser.add_argument(
        "--dest-webdav-password",
        metavar="PASS",
        help="WebDAV password for destination (or set WEBDAV_PASSWORD env var)",
    )
    sync_files_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    sync_files_parser.add_argument(
        "-V", "--verbose", action="store_true", help="Enable verbose output"
    )
    sync_files_parser.set_defaults(func=cmd_sync)

    # Config command group
    config_parser = subparsers.add_parser("config", help="Configuration management")
    config_subparsers = config_parser.add_subparsers(
        dest="config_command", help="Config commands"
    )

    # config show
    config_show_parser = config_subparsers.add_parser(
        "show", help="Show current configuration"
    )
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

    # yt-dlp
    yt_dlp_parser = subparsers.add_parser(
        "yt-dlp", help="yt-dlp wrapper commands for managing YouTube playlist syncing"
    )
    yt_dlp_subparsers = yt_dlp_parser.add_subparsers(
        dest="yt_dlp_command", help="yt-dlp commands"
    )

    # yt-dlp add
    yt_dlp_add_parser = yt_dlp_subparsers.add_parser(
        "add", help="Add a new YouTube playlist for syncing"
    )
    yt_dlp_add_parser.add_argument(
        "id", help="YouTube playlist ID (the part after 'list=')"
    )
    yt_dlp_add_parser.add_argument(
        "--no-sync",
        action="store_true",
        help="Skip git sync even if a repository is configured",
    )
    yt_dlp_add_parser.add_argument(
        "-V", "--verbose", action="store_true", help="Enable verbose output"
    )
    yt_dlp_add_parser.set_defaults(func=cmd_yt_dlp_add)

    # yt-dlp show
    yt_dlp_show_parser = yt_dlp_subparsers.add_parser(
        "show", help="Show configured YouTube playlists"
    )
    yt_dlp_show_parser.add_argument(
        "-V", "--verbose", action="store_true", help="Enable verbose output"
    )
    yt_dlp_show_parser.set_defaults(func=cmd_yt_dlp_show)

    # yt-dlp remove
    yt_dlp_remove_parser = yt_dlp_subparsers.add_parser(
        "remove", help="Remove a YouTube playlist from config by name"
    )
    yt_dlp_remove_parser.add_argument(
        "name", help="Name of the YouTube playlist to remove"
    )
    yt_dlp_remove_parser.add_argument(
        "--no-sync",
        action="store_true",
        help="Skip git sync even if a repository is configured",
    )
    yt_dlp_remove_parser.add_argument(
        "-V", "--verbose", action="store_true", help="Enable verbose output"
    )
    yt_dlp_remove_parser.set_defaults(func=cmd_yt_dlp_remove)

    # yt-dlp download
    yt_dlp_download_parser = yt_dlp_subparsers.add_parser(
        "download", help="Download a YouTube playlist by name"
    )
    yt_dlp_download_parser.add_argument(
        "name", help="Name of the YouTube playlist to download"
    )
    yt_dlp_download_parser.add_argument(
        "--start-index",
        type=int,
        help="Start downloading from the specified index (0-based, default is current index for the playlist)",
    )
    yt_dlp_download_parser.add_argument(
        "--no-sync",
        action="store_true",
        help="Skip git sync even if a repository is configured",
    )
    yt_dlp_download_parser.add_argument(
        "-V", "--verbose", action="store_true", help="Enable verbose output"
    )
    yt_dlp_download_parser.set_defaults(func=cmd_yt_dlp_download)

    # editor
    editor_parser = subparsers.add_parser(
        "editor", help="Open the interactive editor for managing metadata"
    )
    editor_parser.add_argument(
        "-V", "--verbose", action="store_true", help="Enable verbose output"
    )
    editor_parser.set_defaults(func=cmd_editor)

    args = parser.parse_args()

    # Handle no command (default to process for backward compatibility)
    if args.command is None:
        # Check if any legacy arguments were passed
        # Re-parse with process as default
        legacy_parser = argparse.ArgumentParser(
            prog="song-classifier",
            description="Auto-tag music files using AI to infer metadata from filenames",
        )
        for name, arg in FILE_TRANSPORT_ARGUMENTS:
            legacy_parser.add_argument(name, **arg)
        legacy_parser.add_argument(
            "-v",
            "--version",
            action="version",
            version=f"%(prog)s {__version__}",
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
            "--organize",
            action="store_true",
            help="Organize files into Artist/Album/ directory structure based on metadata",
        )
        legacy_parser.add_argument(
            "--sync-metadata",
            action="store_true",
            help="Sync stored metadata with file metadata tags (update file tags to match stored metadata or store file tags if no stored metadata)",
        )
        legacy_parser.add_argument(
            "--sync",
            action="store_true",
            help="Sync audio files from source to destination",
        )
        legacy_parser.add_argument(
            "--dest",
            metavar="PATH",
            help="Destination directory (used with --sync)",
        )
        legacy_parser.add_argument(
        "--dest-webdav",
        metavar="HOST",
        help="WebDAV base URL for the destination (used with --sync)",
    )
        legacy_parser.add_argument(
            "--dest-webdav-user",
            metavar="USER",
            help="WebDAV username for destination (used with --sync)",
        )
        legacy_parser.add_argument(
            "--dest-webdav-password",
            metavar="PASS",
            help="WebDAV password for destination (used with --sync)",
        )
        legacy_parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without making changes",
        )
        legacy_parser.add_argument(
            "-V",
            "--verbose",
            action="store_true",
            help="Enable verbose output",
        )
        legacy_parser.add_argument(
            "-y",
            "--yes",
            action="store_true",
            help="Automatically confirm all metadata without confirming in a UI (use with caution)",
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

        if args.organize:
            cmd_organize(args)
            return

        if args.sync:
            cmd_sync(args)
            return

        # Default to process command
        if args.sync_metadata:
            cmd_sync_metadata(args)
            return

        cmd_process(args)
        return

    # Handle config command without subcommand
    if args.command == "config" and (
        not hasattr(args, "config_command") or args.config_command is None
    ):
        cmd_config_show(args)
        return

    # Execute the command
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
