import argparse

from src.data.playlists import load_playlists, save_playlists
from src.utils.git_sync import sync_metadata
from src.utils.logging import get_logger, setup_logging
from src.utils.yt_dlp import get_playlist_info


@sync_metadata
def cmd_yt_dlp_add(args: argparse.Namespace) -> None:
    """
    Handle the 'yt-dlp add' command.

    This command adds a YouTube playlist to the configuration, allowing it to be downloaded and processed later.
    """
    setup_logging(verbose=args.verbose)
    logger = get_logger()

    playlist_id = args.id

    if not playlist_id:
        logger.error("The id argument is required to add a YouTube playlist.")
        return

    info = get_playlist_info(playlist_id)
    if not info:
        logger.error(f"Failed to retrieve information for playlist ID: {playlist_id}")
        return

    # Check for duplicate name
    existing_playlists = load_playlists()
    if any(p.name == info.name for p in existing_playlists):
        logger.error(f"A playlist with the name '{info.name}' already exists.")
        return

    # Add new playlist
    save_playlists(existing_playlists + [info])

    logger.info(f"Added YouTube playlist: {info.name} ({info.url})")
