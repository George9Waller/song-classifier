import argparse

from src.utils.git_sync import get_sync_repo
from src.utils.logging import get_logger, setup_logging
from src.utils.config import (
    get_or_create_config_dir,
    get_webdav_credentials,
)


def cmd_config_show(args: argparse.Namespace) -> None:
    """Handle the 'config show' subcommand."""
    setup_logging(verbose=False)
    logger = get_logger()

    logger.info(f"Config directory: {get_or_create_config_dir()}")
    repo = get_sync_repo()
    logger.info(f"Sync repository: {repo or '(not configured)'}")
    webdav_user, webdav_pass = get_webdav_credentials()
    logger.info(f"WebDAV username: {webdav_user or '(not configured)'}")
    logger.info(f"WebDAV password: {'***' if webdav_pass else '(not configured)'}")
