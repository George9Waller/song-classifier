import argparse

from src.editor import run_editor
from src.utils.git_sync import sync_metadata
from src.utils.logging import get_logger, setup_logging


@sync_metadata
def cmd_editor(args: argparse.Namespace) -> None:
    """
    Handle the 'editor' command.

    This command opens the interactive editor for managing metadata.
    """
    setup_logging(verbose=args.verbose)
    logger = get_logger()

    logger.info("Opening interactive editor...")
    run_editor()
