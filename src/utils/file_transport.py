"""File transport abstraction for local and WebDAV file systems."""

import argparse
import os
import posixpath
import xml.etree.ElementTree as ET
from enum import Enum
from typing import Generator, Iterable, Optional
from urllib.parse import quote as urlquote
from urllib.parse import unquote, urlsplit, urlunsplit

import requests
from requests.adapters import HTTPAdapter

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

    def walk(self, path: str) -> Iterable[tuple[str, list[str], list[str]]]:
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

        parsed_host = urlsplit(webdav_host)
        if not parsed_host.scheme:
            parsed_host = urlsplit(f"http://{webdav_host}")

        if username is None or password is None:
            from src.utils.config import get_webdav_credentials

            config_user, config_pass = get_webdav_credentials()
            username = username or config_user
            password = password or config_pass

        # Allow credentials to be embedded in the URL as a fallback.
        username = username or parsed_host.username
        password = password or parsed_host.password

        hostname = parsed_host.hostname
        if not hostname:
            raise ValueError("webdav_host must include a hostname")

        netloc = hostname
        if parsed_host.port:
            netloc = f"{netloc}:{parsed_host.port}"

        self.base_url = urlunsplit(
            (
                parsed_host.scheme or "http",
                netloc,
                parsed_host.path.rstrip("/"),
                "",
                "",
            )
        )
        self.auth = (username, password) if username and password else None
        self.timeout = 30

        self.session = requests.Session()
        adapter = HTTPAdapter(max_retries=3)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    @staticmethod
    def get_basename_from_path(path: str) -> str:
        return posixpath.basename(path)

    @staticmethod
    def get_parent_directory(path: str) -> str:
        return posixpath.dirname(path)

    @staticmethod
    def _normalize_remote_path(path: str, *, directory: bool = False) -> str:
        """Normalize a remote path for WebDAV requests."""
        cleaned = path.strip()
        if not cleaned:
            cleaned = "/"
        elif not cleaned.startswith("/"):
            cleaned = f"/{cleaned}"

        cleaned = posixpath.normpath(cleaned)
        if cleaned == ".":
            cleaned = "/"

        if directory and cleaned != "/" and not cleaned.endswith("/"):
            cleaned = f"{cleaned}/"
        return cleaned

    def _build_url(self, remote_path: str) -> str:
        """Build a fully-qualified URL for a remote WebDAV path."""
        normalized = self._normalize_remote_path(
            remote_path, directory=remote_path.endswith("/") or remote_path == "/"
        )
        quoted = urlquote(normalized, safe="/")
        if quoted == "/":
            return f"{self.base_url}/"
        return f"{self.base_url.rstrip('/')}{quoted}"

    def _request(
        self,
        method: str,
        remote_path: str,
        *,
        headers: Optional[dict[str, str]] = None,
        data=None,
        stream: bool = False,
    ) -> requests.Response:
        """Execute a WebDAV request and normalize transport failures."""
        try:
            return self.session.request(
                method=method,
                url=self._build_url(remote_path),
                auth=self.auth,
                headers=headers,
                timeout=self.timeout,
                data=data,
                stream=stream,
                verify=True,
            )
        except requests.RequestException as e:
            raise OSError(f"WebDAV request failed for '{remote_path}': {e}") from e

    @staticmethod
    def _is_ok_status(status_code: int, expected: set[int]) -> bool:
        return status_code in expected

    def _require_success(
        self, response: requests.Response, remote_path: str, *, expected: set[int]
    ) -> requests.Response:
        """Raise if the response status is not one of the expected values."""
        if self._is_ok_status(response.status_code, expected):
            return response
        raise OSError(
            f"WebDAV request failed for '{remote_path}' with status "
            f"{response.status_code}: {response.text}"
        )

    def _propfind(self, remote_path: str, *, depth: str) -> requests.Response:
        """Execute a PROPFIND request."""
        headers = {"Depth": depth, "Accept": "*/*", "Content-Type": "text/xml"}
        response = self._request("PROPFIND", remote_path, headers=headers)
        return self._require_success(response, remote_path, expected={200, 207})

    def _hrefs_from_propfind(
        self, response: requests.Response
    ) -> list[tuple[str, bool]]:
        """Parse a PROPFIND response into hrefs and directory flags."""
        root = ET.fromstring(response.content)
        ns = {"D": "DAV:"}
        items: list[tuple[str, bool]] = []

        for node in root.findall("D:response", ns):
            href_node = node.find("D:href", ns)
            if href_node is None or not href_node.text:
                continue

            prop = node.find("D:propstat/D:prop", ns)
            if prop is None:
                prop = node.find("D:prop", ns)

            is_dir = False
            if prop is not None:
                is_dir = prop.find("D:resourcetype/D:collection", ns) is not None

            items.append((href_node.text, is_dir))

        return items

    def _remote_path_from_href(self, href: str) -> str:
        """Convert a WebDAV href to a normalized remote path."""
        path = urlsplit(href).path
        if not path:
            return "/"
        return self._normalize_remote_path(unquote(path))

    def validate_path(self, path: str) -> str:
        if self.is_dir(path):
            return path
        raise ValueError(f"Path '{path}' is not a directory on WebDAV server")

    def is_dir(self, path: str) -> bool:
        """Check if the given remote path is a directory."""
        remote_path = self._normalize_remote_path(path, directory=True)
        try:
            response = self._propfind(remote_path, depth="0")
        except OSError:
            return False

        root = ET.fromstring(response.content)
        return root.find(".//{DAV:}collection") is not None

    def list_files(
        self, path: str, initial_path: Optional[str] = None
    ) -> Generator[str, None, None]:
        """List audio files recursively on WebDAV server."""
        initial_path = initial_path or path
        normalized_initial = self._normalize_remote_path(initial_path)
        normalized_path = self._normalize_remote_path(path, directory=True)

        try:
            response = self._propfind(normalized_path, depth="1")
        except OSError:
            return

        for href, is_dir in self._hrefs_from_propfind(response):
            child_path = self._remote_path_from_href(href)
            if self._normalize_remote_path(child_path) == normalized_path.rstrip("/"):
                continue

            relative_path = child_path
            if relative_path.startswith(normalized_initial):
                relative_path = relative_path[len(normalized_initial) :]
            relative_path = relative_path.lstrip("/")

            if not relative_path:
                continue

            if is_dir:
                yield from self.list_files(
                    path=child_path, initial_path=normalized_initial
                )
            elif is_audio_file(relative_path):
                yield relative_path

    def load_file(self, path: str, initial_path: str) -> str:
        """Download file from WebDAV to local temp directory."""
        from src.utils.config import get_or_create_temp_dir

        local_path = os.path.join(str(get_or_create_temp_dir()), path)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        remote_path = posixpath.join(initial_path, path)
        response = self._request("GET", remote_path, stream=True)
        self._require_success(response, remote_path, expected={200})

        with open(local_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
        return local_path

    def save_file(
        self, local_path: str, remote_base_path: str, relative_path: str
    ) -> str:
        """Upload file to WebDAV server."""
        remote_path = posixpath.join(remote_base_path, relative_path)
        remote_dir = posixpath.dirname(remote_path)
        self.mkdir_recursive(remote_dir)

        with open(local_path, "rb") as f:
            response = self._request("PUT", remote_path, data=f)
        self._require_success(response, remote_path, expected={200, 201, 204})
        return remote_path

    def mkdir_recursive(self, directory_path: str) -> None:
        """Create a directory hierarchy on the WebDAV server."""
        normalized = self._normalize_remote_path(directory_path, directory=True)
        if normalized == "/":
            return True

        parts = [part for part in normalized.strip("/").split("/") if part]
        current = ""
        for part in parts:
            current = f"{current}/{part}"
            response = self._request(
                "MKCOL",
                current,
                headers={"Accept": "*/*", "Connection": "Keep-Alive"},
            )
            if response.status_code in (200, 201, 204, 405):
                continue
            if response.status_code == 409:
                continue
            raise OSError(
                f"Failed to create WebDAV directory '{current}' with status "
                f"{response.status_code}: {response.text}"
            )
        return True

    def move_file(
        self, original_path: str, new_path: str, initial_path: Optional[str] = None
    ) -> None:
        """Move file to new location on WebDAV server."""
        original_full_path = posixpath.join(initial_path or "", original_path)
        new_full_path = posixpath.join(initial_path or "", new_path)

        dest_dir = posixpath.dirname(new_full_path)
        self.mkdir_recursive(dest_dir)

        response = self._request(
            "MOVE",
            original_full_path,
            headers={
                "Destination": self._build_url(new_full_path),
                "Overwrite": "T",
                "Accept": "*/*",
            },
        )
        self._require_success(response, original_full_path, expected={200, 201, 204})

    def walk(self, path: str, initial_path: Optional[str] = None):
        """Walk through files in the given path on WebDAV server."""
        full_path = posixpath.join(initial_path or "", path)

        try:
            response = self._propfind(
                self._normalize_remote_path(full_path, directory=True), depth="1"
            )
        except OSError:
            return

        dirs = []
        files = []
        for href, is_dir in self._hrefs_from_propfind(response):
            child_path = self._remote_path_from_href(href)
            if self._normalize_remote_path(child_path) == self._normalize_remote_path(
                full_path
            ):
                continue

            name = posixpath.basename(child_path.rstrip("/"))
            if is_dir:
                dirs.append(name)
            else:
                files.append(name)

        yield full_path, dirs, files

        for dir in dirs:
            yield from self.walk(
                path=posixpath.join(path, dir), initial_path=initial_path
            )

    def delete_directory_if_exists(self, path: str) -> None:
        """Delete directory if it exists (used for cleanup of empty directories)."""
        logger = get_logger()

        full_path = self._normalize_remote_path(path, directory=True)
        try:
            if not self.is_dir(full_path):
                return

            for filename in EXCLUDED_FILENAMES_FOR_EMPTY_DIRECTORY_DELETION:
                excluded_file_path = posixpath.join(full_path, filename)
                try:
                    response = self._request("DELETE", excluded_file_path)
                    self._require_success(
                        response, excluded_file_path, expected={200, 202, 204, 404}
                    )
                except OSError:
                    pass

            response = self._request("DELETE", full_path)
            self._require_success(response, full_path, expected={200, 202, 204, 404})
        except OSError as e:
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
