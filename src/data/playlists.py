import json

from src.data.models import YouTubePlaylistConfig
from src.utils.config import get_or_create_playlists_file_path


def load_playlists() -> list[YouTubePlaylistConfig]:
    """Load YouTube playlist configurations from JSON file."""
    playlists_file = get_or_create_playlists_file_path()
    if not playlists_file.exists():
        return []

    with open(playlists_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        return [YouTubePlaylistConfig(**item) for item in data]


def load_playlist_by_name(name: str) -> YouTubePlaylistConfig | None:
    """Load a single YouTube playlist configuration by name."""
    playlists = load_playlists()
    for playlist in playlists:
        if playlist.name == name:
            return playlist
    return None


def update_playlist(playlist: YouTubePlaylistConfig) -> None:
    """Update a single YouTube playlist configuration."""
    playlists = load_playlists()
    updated_playlists = [p if p.id != playlist.id else playlist for p in playlists]
    save_playlists(updated_playlists)


def save_playlists(playlists: list[YouTubePlaylistConfig]) -> None:
    """Save YouTube playlist configurations to JSON file."""
    playlists_file = get_or_create_playlists_file_path()
    with open(playlists_file, "w", encoding="utf-8") as f:
        json.dump([playlist.__dict__ for playlist in playlists], f, indent=2)
