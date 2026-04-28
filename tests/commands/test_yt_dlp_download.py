"""Tests for yt-dlp download command."""

from argparse import Namespace
from unittest.mock import MagicMock

from src.commands.yt_dlp.download import cmd_yt_dlp_download
from src.data.models import YouTubePlaylistConfig


class TestYtDlpDownload:
    """Tests for the YouTube playlist download command."""

    def test_download_honors_explicit_zero_start_index(
        self, monkeypatch, config_dir
    ) -> None:
        """Test that an explicit start index of 0 is not ignored."""
        playlist = YouTubePlaylistConfig(
            name="Playlist",
            url="https://www.youtube.com/playlist?list=test",
            id="test",
            current_index=5,
            total=10,
        )
        refreshed = YouTubePlaylistConfig(
            name="Playlist",
            url="https://www.youtube.com/playlist?list=test",
            id="test",
            current_index=0,
            total=10,
        )

        download_mock = MagicMock(return_value=True)
        save_mock = MagicMock()

        monkeypatch.setattr(
            "src.commands.yt_dlp.download.load_playlist_by_name",
            lambda name: playlist if name == "Playlist" else None,
        )
        monkeypatch.setattr(
            "src.commands.yt_dlp.download.get_playlist_info",
            lambda playlist_id: refreshed,
        )
        monkeypatch.setattr(
            "src.commands.yt_dlp.download.download_playlist_items", download_mock
        )
        monkeypatch.setattr("src.commands.yt_dlp.download.save_playlists", save_mock)

        args = Namespace(name="Playlist", start_index=0, verbose=False, no_sync=True)

        cmd_yt_dlp_download(args)

        download_mock.assert_called_once_with("test", start_index=0)
        save_mock.assert_called_once()
        assert playlist.current_index == 9

    def test_download_persists_state_when_playlist_is_already_complete(
        self, monkeypatch, config_dir
    ) -> None:
        """Test that the playlist state is saved on the no-op path."""
        playlist = YouTubePlaylistConfig(
            name="Playlist",
            url="https://www.youtube.com/playlist?list=test",
            id="test",
            current_index=4,
            total=5,
        )
        refreshed = YouTubePlaylistConfig(
            name="Playlist",
            url="https://www.youtube.com/playlist?list=test",
            id="test",
            current_index=0,
            total=5,
        )

        download_mock = MagicMock()
        save_mock = MagicMock()

        monkeypatch.setattr(
            "src.commands.yt_dlp.download.load_playlist_by_name",
            lambda name: playlist if name == "Playlist" else None,
        )
        monkeypatch.setattr(
            "src.commands.yt_dlp.download.get_playlist_info",
            lambda playlist_id: refreshed,
        )
        monkeypatch.setattr(
            "src.commands.yt_dlp.download.download_playlist_items", download_mock
        )
        monkeypatch.setattr("src.commands.yt_dlp.download.save_playlists", save_mock)

        args = Namespace(name="Playlist", start_index=None, verbose=False, no_sync=True)

        cmd_yt_dlp_download(args)

        download_mock.assert_not_called()
        save_mock.assert_called_once()
        assert playlist.current_index == 4
