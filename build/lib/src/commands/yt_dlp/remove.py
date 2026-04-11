import argparse

from src.data.playlists import load_playlist_by_name, load_playlists, save_playlists
from src.utils.git_sync import sync_metadata
from src.utils.logging import get_logger, setup_logging


@sync_metadata
def cmd_yt_dlp_remove(args: argparse.Namespace) -> None:
    """
    Handle the 'yt-dlp remove' command.

    This command removes a YouTube playlist from the configuration by name, preventing it from being downloaded and processed.
    """
    setup_logging(verbose=args.verbose)
    logger = get_logger()

    playlist_name = args.name

    if not playlist_name:
        logger.error("The name argument is required to remove a YouTube playlist.")
        return

    # Check for duplicate name
    existing_playlist = load_playlist_by_name(playlist_name)
    if not existing_playlist:
        logger.error(f"No playlist with the name '{playlist_name}' exists.")
        return

    # Remove the playlist
    updated_playlists = [p for p in load_playlists() if p.name != playlist_name]
    save_playlists(updated_playlists)

    logger.info(f"Removed YouTube playlist: {playlist_name}")
