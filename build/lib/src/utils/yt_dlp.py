import re
import subprocess
from typing import Optional

from src.data.models import YouTubePlaylistConfig
from src.utils.logging import get_logger

BASE_URL = "https://www.youtube.com/playlist?list="
PLAYLIST_ITEMS_ARG = "--playlist-items"


def _get_playlist_url(playlist_id: str) -> str:
    """Construct the full YouTube playlist URL from the playlist ID."""
    return BASE_URL + playlist_id


def get_playlist_info(playlist_id: str) -> Optional[YouTubePlaylistConfig]:
    """Get playlist info from config by ID."""

    logger = get_logger()
    url = _get_playlist_url(playlist_id)

    result_bytes = subprocess.run(
        ["yt-dlp", url, PLAYLIST_ITEMS_ARG, "0:0"], capture_output=True
    )
    result = result_bytes.stdout.decode("utf-8")

    is_error = result_bytes.stderr.decode("utf-8").strip() != ""
    if is_error:
        logger.error(f"Error fetching playlist info for ID {playlist_id}: {result}")
        return None

    name = re.search(r"(playlist|Playlist):\s*(.+)", result)
    total = re.search(r"\d+ items of (\d+)", result.lower())

    if not (name and total):
        logger.error(f"Failed to parse playlist info for ID {playlist_id}: {result}")
        return None

    return YouTubePlaylistConfig(
        name=name.group(2).strip(),
        url=url,
        id=playlist_id,
        current_index=0,
        total=int(total.group(1)),
    )


def download_playlist_items(playlist_id: str, *, start_index: int) -> bool:
    """Download playlist items starting from the specified index."""
    logger = get_logger()

    playlist_url = _get_playlist_url(playlist_id)

    result = subprocess.run(
        [
            "yt-dlp",
            playlist_url,
            PLAYLIST_ITEMS_ARG,
            f"{start_index}:",
            "--extract-audio",
            "--audio-format",
            "opus",
            "--audio-quality",
            "0",
            "--embed-thumbnail",
            "--embed-metadata",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        logger.error(f"yt-dlp failed with error: {result.stderr}")
        return False

    logger.info(f"yt-dlp output: {result.stdout}")
    return True
