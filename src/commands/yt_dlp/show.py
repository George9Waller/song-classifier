import argparse

from rich import print
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from src.data.playlists import load_playlists
from src.utils.logging import get_logger, setup_logging


def cmd_yt_dlp_show(args: argparse.Namespace) -> None:
    """
    Handle the 'yt-dlp show' command.

    This command lists all configured YouTube playlists that are set up for downloading and processing.
    """
    setup_logging(verbose=args.verbose)
    logger = get_logger()

    playlists = load_playlists()

    if not playlists:
        logger.warning(
            "No YouTube playlists configured. Use 'yt-dlp add' to add a playlist."
        )
        return

    logger.info("Configured YouTube Playlists:")

    for playlist in playlists:
        md = Markdown(
            f"URL: {playlist.url}\n\nDownloaded: {playlist.current_index + 1}/{playlist.total}\n"
        )
        print(
            Panel(
                md,
                title=Text(playlist.name, style="purple"),
                title_align="left",
                padding=1,
                expand=False,
            )
        )
