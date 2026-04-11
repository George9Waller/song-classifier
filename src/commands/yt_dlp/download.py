import argparse

from src.data.playlists import load_playlist_by_name, load_playlists, save_playlists
from src.utils.logging import get_logger, setup_logging
from src.utils.yt_dlp import download_playlist_items, get_playlist_info
from src.utils.git_sync import sync_metadata


@sync_metadata
def cmd_yt_dlp_download(args: argparse.Namespace) -> None:
    """
    Handle the 'yt-dlp show' command.

    This command lists all configured YouTube playlists that are set up for downloading and processing.
    """
    setup_logging(verbose=args.verbose)
    logger = get_logger()

    playlist = load_playlist_by_name(args.name)
    if not playlist:
        logger.error(f"No playlist with the name '{args.name}' exists.")
        return

    refreshed_playlist = get_playlist_info(playlist.id)
    total_items = refreshed_playlist.total if refreshed_playlist else playlist.total

    start_index = args.start_index or playlist.current_index
    if start_index >= (total_items - 1):
        logger.info(f"Playlist '{playlist.name}' is already fully downloaded.")
        return

    logger.info(f"Downloading YouTube playlist: {playlist.name} ({playlist.url})")
    logger.info(f"Starting from index {start_index} out of {total_items} items.")

    success = download_playlist_items(playlist.id, start_index=start_index)

    if success:
        logger.info(f"Finished downloading playlist '{playlist.name}'.")
        playlist.current_index = total_items - 1
        save_playlists(
            [p if p.name != playlist.name else playlist for p in load_playlists()]
        )

    else:
        logger.error(f"Failed to download playlist '{playlist.name}'.")
