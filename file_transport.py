import os
from enum import Enum
from typing import Generator, List

from webdav3 import client


class TransportType(Enum):
    LOCAL = "LOCAL"
    WEBDAV = "WEBDAV"


class FileTransport:
    cleanup_local_files = False

    def __new__(self, transport_type):
        match transport_type:
            case TransportType.LOCAL:
                return LocalTransport()
            case TransportType.WEBDAV:
                return WebdavTransport()
            case _:
                raise NotImplementedError("Unrecognised transport_type")

    @classmethod
    def list_files(path, initial_path=None) -> Generator[List[str]]:
        raise NotImplementedError

    @classmethod
    def load_file(path, initial_path) -> str:
        raise NotImplementedError

    @classmethod
    def save_file(local_path, remote_base_path, relative_path) -> str:
        raise NotImplementedError


class WebdavTransport:
    cleanup_local_files = True
    WEBDAV_CONFIG = {
        "webdav_hostname": "http://k:btuHmfcU3.YK@10.0.1.14/",
        "webdav_login": None,
        "webdav_password": None,
    }

    @classmethod
    def list_files(cls, path, initial_path=None):
        initial_path = initial_path or path

        webdav_client = client.Client(cls.WEBDAV_CONFIG)
        remote_files = webdav_client.list(path, get_info=True)
        for file in remote_files:
            if file["isdir"]:
                yield from cls.list_files(
                    path=os.path.join(path, file["name"]), initial_path=initial_path
                )
            else:
                relative_path = file["path"].replace(initial_path, "").lstrip("/")
                yield relative_path

    @classmethod
    def load_file(cls, path, initial_path):
        # Create local path if required
        local_path = os.path.join("temp", path)
        try:
            os.makedirs(os.path.dirname(local_path))
        except Exception:
            pass

        webdav_client = client.Client(cls.WEBDAV_CONFIG)
        webdav_client.download_sync(
            remote_path=os.path.join(initial_path, path),
            local_path=local_path
        )
        return local_path

    @classmethod
    def save_file(cls, local_path, remote_base_path, relative_path):
        webdav_client = client.Client(cls.WEBDAV_CONFIG)
        remote_path = os.path.join(remote_base_path, relative_path)
        webdav_client.upload_sync(
            remote_path=remote_path,
            local_path=local_path,
        )
        return remote_path


class LocalTransport:
    cleanup_local_files = False

    @classmethod
    def list_files(cls, path, initial_path=None):
        initial_path = initial_path or path

        paths = os.listdir(initial_path)
        for path in paths:
            if os.path.isdir(path):
                yield from cls.list_files(
                    path=path, initial_path=initial_path
                )
            else:
                relative_path = path.replace(initial_path, "").lstrip("/")
                yield relative_path

    @classmethod
    def load_file(cls, path, initial_path):
        # no need to make a local copy for a local file
        return os.path.join(initial_path, path)

    @classmethod
    def save_file(cls, local_path, remote_base_path, relative_path):
        # no need to save the file to a remote source for a local file
        pass
