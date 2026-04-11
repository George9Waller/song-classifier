import argparse

from src.utils.git_sync import set_sync_repo
from src.utils.logging import setup_logging


def cmd_config_set_sync_repo(args: argparse.Namespace) -> None:
    """Handle the 'config set-sync-repo' subcommand."""
    setup_logging(verbose=False)
    set_sync_repo(args.url)
