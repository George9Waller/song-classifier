import argparse

from src.utils.git_sync import get_sync_repo
from src.utils.logging import setup_logging
from src.utils.config import (
    get_or_create_config_dir,
    get_webdav_credentials,
)


def cmd_config_show(args: argparse.Namespace) -> None:
    """Handle the 'config show' subcommand."""
    setup_logging(verbose=False)
    print(f"Config directory: {get_or_create_config_dir()}")
    repo = get_sync_repo()
    print(f"Sync repository: {repo or '(not configured)'}")
    webdav_user, webdav_pass = get_webdav_credentials()
    print(f"WebDAV username: {webdav_user or '(not configured)'}")
    print(f"WebDAV password: {'***' if webdav_pass else '(not configured)'}")
