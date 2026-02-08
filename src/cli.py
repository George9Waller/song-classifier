"""CLI entry point for song-classifier."""

import argparse

from src.commands.config import cmd_config_show, cmd_config_set_webdav, cmd_config_set_sync_repo
from src.commands.process import cmd_process
from src.utils.git_sync import set_sync_repo
from src.utils.logging import setup_logging

__version__ = "0.1.0"


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
        "-y", "--yes",
        action="store_true",
        help="Automatically confirm all metadata without confirming in a UI (use with caution)",
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
        legacy_parser.add_argument(
            "-y", "--yes",
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
