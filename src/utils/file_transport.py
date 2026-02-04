"""File transport abstraction for local and WebDAV file systems."""

import os
import posixpath
from enum import Enum
from typing import Generator, Optional

from webdav3 import client

# Supported audio file extensions
AUDIO_EXTENSIONS = {'.mp3', '.flac', '.m4a', '.mp4', '.opus', '.ogg', '.wav', '.aiff', '.aif'}


def is_audio_file(path: str) -> bool:
    """Check if a file has a supported audio extension."""
    _, ext = os.path.splitext(path.lower())
    return ext in AUDIO_EXTENSIONS


class TransportType(Enum):
    """Transport type for file operations."""

    LOCAL = "LOCAL"
    WEBDAV = "WEBDAV"


class FileTransport:
    """Factory for creating file transport instances."""

    cleanup_local_files = False

    def __new__(
        cls,
        transport_type: TransportType,
        webdav_host: Optional[str] = None,
        webdav_username: Optional[str] = None,
        webdav_password: Optional[str] = None,
    ):
        """Create appropriate transport based on type."""
        match transport_type:
            case TransportType.LOCAL:
                return LocalTransport()
            case TransportType.WEBDAV:
                return WebdavTransport(
                    webdav_host=webdav_host,
                    username=webdav_username,
                    password=webdav_password,
                )
            case _:
                raise NotImplementedError("Unrecognised transport_type")

    def list_files(self, path: str, initial_path: Optional[str] = None) -> Generator[str, None, None]:
        """List audio files in the given path."""
        raise NotImplementedError

    def load_file(self, path: str, initial_path: str) -> str:
        """Load file to local path, returns local file path."""
        raise NotImplementedError

    def save_file(self, local_path: str, remote_base_path: str, relative_path: str) -> Optional[str]:
        """Save local file to remote location."""
        raise NotImplementedError


class WebdavTransport:
    """WebDAV file transport implementation."""

    cleanup_local_files = True

    def __init__(
        self,
        webdav_host: Optional[str],
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        """Initialize WebDAV transport.

        Args:
            webdav_host: WebDAV server URL.
            username: Optional username for authentication.
            password: Optional password for authentication.
        """
        if not webdav_host:
            raise ValueError("webdav_host must be provided for WebdavTransport")

        # Get credentials from config/env if not provided
        if username is None or password is None:
            from src.utils.config import get_webdav_credentials
            config_user, config_pass = get_webdav_credentials()
            username = username or config_user
            password = password or config_pass

        self.webdav_config = {
            "webdav_hostname": webdav_host,
            "webdav_login": username,
            "webdav_password": password,
        }

    def list_files(self, path: str, initial_path: Optional[str] = None) -> Generator[str, None, None]:
        """List audio files recursively on WebDAV server."""
        initial_path = initial_path or path

        webdav_client = client.Client(self.webdav_config)
        remote_files = webdav_client.list(path, get_info=True)
        for file in remote_files:
            if file["isdir"]:
                # Use posixpath for WebDAV paths (always forward slashes)
                yield from self.list_files(
                    path=posixpath.join(path, file["name"]), initial_path=initial_path
                )
            else:
                relative_path = file["path"].replace(initial_path, "").lstrip("/")
                if is_audio_file(relative_path):
                    yield relative_path

    def load_file(self, path: str, initial_path: str) -> str:
        """Download file from WebDAV to local temp directory."""
        from src.utils.config import get_or_create_temp_dir

        # Create local path if required
        local_path = os.path.join(str(get_or_create_temp_dir()), path)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        webdav_client = client.Client(self.webdav_config)
        # Use posixpath for remote path construction
        remote_path = posixpath.join(initial_path, path)
        webdav_client.download_sync(
            remote_path=remote_path,
            local_path=local_path
        )
        return local_path

    def save_file(self, local_path: str, remote_base_path: str, relative_path: str) -> str:
        """Upload file to WebDAV server."""
        webdav_client = client.Client(self.webdav_config)
        # Use posixpath for remote path construction
        remote_path = posixpath.join(remote_base_path, relative_path)
        webdav_client.upload_sync(
            remote_path=remote_path,
            local_path=local_path,
        )
        return remote_path


class LocalTransport:
    """Local filesystem transport implementation."""

    cleanup_local_files = False

    def list_files(self, path: str, initial_path: Optional[str] = None) -> Generator[str, None, None]:
        """List audio files recursively in local directory."""
        initial_path = initial_path or path

        for entry in os.listdir(path):
            full_path = os.path.join(path, entry)
            if os.path.isdir(full_path):
                yield from self.list_files(
                    path=full_path, initial_path=initial_path
                )
            elif is_audio_file(entry):
                relative_path = full_path.replace(initial_path, "").lstrip(os.sep)
                yield relative_path

    def load_file(self, path: str, initial_path: str) -> str:
        """Return full local path (no copy needed)."""
        return os.path.join(initial_path, path)

    def save_file(self, local_path: str, remote_base_path: str, relative_path: str) -> None:
        """No-op for local transport (file already in place)."""
        pass
