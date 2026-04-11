"""File transport abstraction for local and WebDAV file systems."""

import argparse
import os
import pathlib
import posixpath
from enum import Enum
from typing import Generator, Iterable, Optional

from requests.adapters import HTTPAdapter
from webdav3 import client, exceptions

from src.constants import EXCLUDED_FILENAMES_FOR_EMPTY_DIRECTORY_DELETION
from src.utils.logging import get_logger


def get_file_transport_for_args(args: argparse.Namespace) -> "FileTransport":
    """Factory function to get the appropriate FileTransport based on CLI args."""
    if args.webdav:
        return FileTransport(
            transport_type=TransportType.WEBDAV,
            webdav_host=args.webdav,
            webdav_username=getattr(args, "webdav_user", None),
            webdav_password=getattr(args, "webdav_password", None),
        )
    else:
        return FileTransport(transport_type=TransportType.LOCAL)


# Supported audio file extensions
AUDIO_EXTENSIONS = {
    ".mp3",
    ".flac",
    ".m4a",
    ".mp4",
    ".opus",
    ".ogg",
    ".wav",
    ".aiff",
    ".aif",
}


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

    @staticmethod
    def get_basename_from_path(path: str) -> str:
        """Extract base file name from path."""
        raise NotImplementedError

    @staticmethod
    def get_parent_directory(path: str) -> str:
        """Extract parent directory from path."""
        raise NotImplementedError

    def is_dir(path: str) -> bool:
        """Check if the given path is a directory."""
        raise NotImplementedError

    def walk(self, path: str) -> Iterable[str, list[str], list[str]]:
        """Walk through files in the given path."""
        raise NotImplementedError

    def list_files(
        self, path: str, initial_path: Optional[str] = None
    ) -> Generator[str, None, None]:
        """List audio files in the given path."""
        raise NotImplementedError

    def load_file(self, path: str, initial_path: str) -> str:
        """Load file to local path, returns local file path."""
        raise NotImplementedError

    def save_file(
        self, local_path: str, remote_base_path: str, relative_path: str
    ) -> Optional[str]:
        """Save local file to remote location."""
        raise NotImplementedError

    def move_file(
        self, original_path: str, new_path: str, initial_path: Optional[str] = None
    ) -> None:
        """Move/rename file from original_path to new_path."""
        raise NotImplementedError

    def delete_directory_if_exists(self, path: str) -> None:
        """Delete directory if it exists (used for cleanup of empty directories)."""
        raise NotImplementedError

    def cleanup_local_file_if_needed(self, local_path: str) -> None:
        """Delete local file if cleanup is enabled for this transport."""
        raise NotImplementedError


class WebdavClient(client.Client):
    http_adapter = HTTPAdapter(max_retries=3)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session.mount("http://", self.http_adapter)


class WebdavTransport:
    """WebDAV file transport implementation."""

    cleanup_local_files = True
    client_class = None

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

        self.client_class = WebdavClient(
            {
                "webdav_hostname": webdav_host,
                "webdav_login": username,
                "webdav_password": password,
            }
        )

    @staticmethod
    def get_basename_from_path(path: str) -> str:
        return posixpath.basename(path)

    @staticmethod
    def get_parent_directory(path: str) -> str:
        return posixpath.dirname(path)

    def validate_path(self, path: str) -> str:
        is_dir = self.client_class.is_dir(path)
        if is_dir:
            return path
        else:
            raise ValueError(f"Path '{path}' is not a directory on WebDAV server")

    def list_files(
        self, path: str, initial_path: Optional[str] = None
    ) -> Generator[str, None, None]:
        """List audio files recursively on WebDAV server."""
        initial_path = initial_path or path

        remote_files = self.client_class.list(path, get_info=True)
        for file in remote_files:
            if file["isdir"]:
                # Use posixpath for WebDAV paths (always forward slashes)
                yield from self.list_files(
                    path=posixpath.join(path, file["name"]), initial_path=initial_path
                )
            else:
                relative_path = (
                    file["path"].replace(initial_path, "", count=1).lstrip("/")
                )
                if is_audio_file(relative_path):
                    yield relative_path

    def load_file(self, path: str, initial_path: str) -> str:
        """Download file from WebDAV to local temp directory."""
        from src.utils.config import get_or_create_temp_dir

        # Create local path if required
        local_path = os.path.join(str(get_or_create_temp_dir()), path)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        # Use posixpath for remote path construction
        remote_path = posixpath.join(initial_path, path)
        self.client_class.download_sync(remote_path=remote_path, local_path=local_path)
        return local_path

    def save_file(
        self, local_path: str, remote_base_path: str, relative_path: str
    ) -> str:
        """Upload file to WebDAV server."""

        # Use posixpath for remote path construction
        remote_path = posixpath.join(remote_base_path, relative_path)

        # Make directory if needed
        remote_dir = posixpath.dirname(remote_path)
        self.mkdir_recursive(remote_dir)

        self.client_class.upload_sync(
            remote_path=remote_path,
            local_path=local_path,
        )
        return remote_path

    def mkdir_recursive(self, directory_path: str) -> None:
        try:
            directory_exists = self.client_class.is_dir(directory_path)
        except exceptions.RemoteResourceNotFound:
            directory_exists = False

        if not directory_exists:
            try:
                directory_success = self.client_class.mkdir(directory_path)
            except exceptions.RemoteParentNotFound:
                path = pathlib.Path(directory_path)
                path_and_parents = list(reversed(path.parents)) + [path]
                parent_path_results = [
                    self.mkdir_recursive(parent.as_posix())
                    for parent in path_and_parents
                ]
                return parent_path_results[-1]

            if not directory_success:
                logger = get_logger()
                logger.warning(
                    f"Failed to create directory '{directory_path}' on WebDAV server."
                )
                return False
        return True

    def move_file(
        self, original_path: str, new_path: str, initial_path: Optional[str] = None
    ) -> None:
        """Move file to new location on WebDAV server."""
        # Use posixpath for remote path construction
        original_full_path = posixpath.join(initial_path or "", original_path)
        new_full_path = posixpath.join(initial_path or "", new_path)

        # Ensure destination directory exists
        dest_dir = posixpath.dirname(new_full_path)
        self.mkdir_recursive(dest_dir)

        try:
            self.client_class.move(
                remote_path_from=original_full_path, remote_path_to=new_full_path
            )
        except exceptions.ResponseErrorCode as e:
            if "target file exists" in e.message.decode("utf-8").lower():
                pass  # Ignore if target file already exists
            else:
                raise

        try:
            self.client_class.clean(
                original_full_path
            )  # Ensure original file is removed after move
        except exceptions.ResponseErrorCode as e:
            if "file not found on disk" in e.message.decode("utf-8").lower():
                pass  # Ignore if original file is already removed
            else:
                logger = get_logger()
                logger.warning(
                    f"Failed to clean original file '{original_full_path}' on WebDAV server: {e}"
                )

    def walk(self, path: str, initial_path: Optional[str] = None):
        """Walk through files in the given path on WebDAV server."""
        # Use posixpath for remote path construction
        full_path = posixpath.join(initial_path or "", path)

        # Get all nested filed and directories under the given path
        try:
            items = self.client_class.list(full_path, get_info=True)
        except exceptions.RemoteResourceNotFound:
            return

        dirs = []
        files = []
        for item in items:
            if item["isdir"]:
                dirs.append(item["name"])
            else:
                files.append(item["name"])

        yield full_path, dirs, files

        for dir in dirs:
            yield from self.walk(
                path=posixpath.join(path, dir), initial_path=initial_path
            )

    def delete_directory_if_exists(self, path: str) -> None:
        """Delete directory if it exists (used for cleanup of empty directories)."""
        logger = get_logger()

        full_path = posixpath.join(path)
        try:
            if self.client_class.is_dir(full_path):
                # Delete excluded files if they exist
                for filename in EXCLUDED_FILENAMES_FOR_EMPTY_DIRECTORY_DELETION:
                    excluded_file_path = posixpath.join(full_path, filename)
                    try:
                        self.client_class.clean(excluded_file_path)
                    except (
                        exceptions.RemoteResourceNotFound,
                        exceptions.ResponseErrorCode,
                    ):
                        pass  # File doesn't exist, ignore

                self.client_class.clean(full_path)
        except exceptions.RemoteResourceNotFound:
            pass  # Directory doesn't exist, ignore
        except exceptions.WebDavException as e:
            logger.warning(f"Failed to delete directory '{path}' on WebDAV server: {e}")

    def cleanup_local_file_if_needed(self, local_path: str) -> None:
        """Delete local file if cleanup is enabled for this transport."""
        if self.cleanup_local_files and os.path.isfile(local_path):
            try:
                os.remove(local_path)
            except OSError as e:
                logger = get_logger()
                logger.warning(f"Failed to delete local file '{local_path}': {e}")


class LocalTransport:
    """Local filesystem transport implementation."""

    cleanup_local_files = False

    @staticmethod
    def get_basename_from_path(path: str) -> str:
        return os.path.basename(path)

    @staticmethod
    def get_parent_directory(path: str) -> str:
        return os.path.dirname(path)

    def validate_path(self, path: str) -> str:
        path = os.path.abspath(path)
        if not os.path.exists(path):
            raise ValueError(f"Path does not exist: {path}")
        if not os.path.isdir(path):
            raise ValueError(f"Path is not a directory: {path}")

        # Resolve symlinks and check for path traversal
        real_path = os.path.realpath(path)
        return real_path

    def walk(self, path: str):
        return os.walk(path)

    def list_files(
        self, path: str, initial_path: Optional[str] = None
    ) -> Generator[str, None, None]:
        """List audio files recursively in local directory."""
        initial_path = initial_path or path

        for entry in os.listdir(path):
            full_path = os.path.join(path, entry)
            if os.path.isdir(full_path):
                yield from self.list_files(path=full_path, initial_path=initial_path)
            elif is_audio_file(entry):
                relative_path = full_path.replace(initial_path, "").lstrip(os.sep)
                yield relative_path

    def load_file(self, path: str, initial_path: str) -> str:
        """Return full local path (no copy needed)."""
        return os.path.join(initial_path, path)

    def save_file(
        self, local_path: str, remote_base_path: str, relative_path: str
    ) -> None:
        """No-op for local transport (file already in place)."""
        pass

    def move_file(
        self, original_path: str, new_path: str, initial_path: Optional[str] = None
    ) -> None:
        """Move file to new location."""
        new_full_path = os.path.join(initial_path or "", new_path)
        os.makedirs(os.path.dirname(new_full_path), exist_ok=True)

        original_full_path = os.path.join(initial_path or "", original_path)
        os.rename(original_full_path, new_full_path)

    def delete_directory_if_exists(self, path: str) -> None:
        """Delete directory if it exists (used for cleanup of empty directories)."""
        logger = get_logger()

        full_path = os.path.join(path)
        if os.path.isdir(full_path):
            # Delete excluded files if they exist
            for filename in EXCLUDED_FILENAMES_FOR_EMPTY_DIRECTORY_DELETION:
                excluded_file_path = os.path.join(full_path, filename)
                if os.path.isfile(excluded_file_path):
                    try:
                        os.remove(excluded_file_path)
                    except OSError as e:
                        logger.warning(
                            f"Failed to delete excluded file '{excluded_file_path}': {e}"
                        )
            try:
                os.rmdir(full_path)
            except OSError as e:
                logger.warning(f"Failed to delete directory '{path}': {e}")

    def cleanup_local_file_if_needed(self, local_path: str) -> None:
        """Delete local file if cleanup is enabled for this transport."""
        if self.cleanup_local_files and os.path.isfile(local_path):
            try:
                os.remove(local_path)
            except OSError as e:
                logger = get_logger()
                logger.warning(f"Failed to delete local file '{local_path}': {e}")
