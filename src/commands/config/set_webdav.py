import argparse

from src.utils.config import set_webdav_credentials
from src.utils.logging import setup_logging


def cmd_config_set_webdav(args: argparse.Namespace) -> None:
    """Handle the 'config set-webdav' subcommand."""
    logger = setup_logging(verbose=False)
    set_webdav_credentials(args.user, args.password)
    logger.info("WebDAV credentials saved")
