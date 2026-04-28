"""Tests for the WebDAV transport implementation."""

from pathlib import Path

import pytest

from src.utils.file_transport import WebdavTransport


class FakeResponse:
    """Minimal response object for mocking WebDAV requests."""

    def __init__(self, status_code: int, text: str = "", content: bytes = b"") -> None:
        self.status_code = status_code
        self.text = text
        self.content = content

    def iter_content(self, chunk_size: int = 65536):
        yield from []


def test_webdav_transport_parses_credentials_from_url() -> None:
    """Test that credentials embedded in the URL are extracted."""
    transport = WebdavTransport("http://k:secret@10.0.1.14/sets")

    assert transport.base_url == "http://10.0.1.14/sets"
    assert transport.auth == ("k", "secret")


def test_webdav_save_file_uses_mkcol_then_put(
    temp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that save_file creates directories and uploads the file."""
    transport = WebdavTransport("http://10.0.1.14/")
    local_file = temp_dir / "track.mp3"
    local_file.write_bytes(b"audio-bytes")

    calls: list[dict[str, object]] = []

    def fake_request(self, *args, **kwargs):
        method = kwargs.get("method", args[0] if args else None)
        url = kwargs.get("url", args[1] if len(args) > 1 else None)
        calls.append({"method": method, "url": url, "kwargs": kwargs})
        if method == "MKCOL":
            return FakeResponse(201)
        if method == "PUT":
            return FakeResponse(201)
        raise AssertionError(f"Unexpected method: {method}")

    monkeypatch.setattr(transport.session, "request", fake_request.__get__(transport.session))

    result = transport.save_file(
        str(local_file),
        "sets",
        "Carl Cox/Essential Mix/track.mp3",
    )

    assert result == "sets/Carl Cox/Essential Mix/track.mp3"
    assert [call["method"] for call in calls] == [
        "MKCOL",
        "MKCOL",
        "MKCOL",
        "PUT",
    ]
    assert calls[-1]["url"] == "http://10.0.1.14/sets/Carl%20Cox/Essential%20Mix/track.mp3"


def test_webdav_list_files_parses_propfind_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that PROPFIND listings are turned into relative audio paths."""
    transport = WebdavTransport("http://10.0.1.14/")

    root_xml = b"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<D:multistatus xmlns:D=\"DAV:\">
  <D:response>
    <D:href>/sets/</D:href>
    <D:propstat><D:prop><D:resourcetype><D:collection/></D:resourcetype></D:prop></D:propstat>
  </D:response>
  <D:response>
    <D:href>/sets/subdir/</D:href>
    <D:propstat><D:prop><D:resourcetype><D:collection/></D:resourcetype></D:prop></D:propstat>
  </D:response>
  <D:response>
    <D:href>/sets/song.mp3</D:href>
    <D:propstat><D:prop><D:resourcetype/></D:prop></D:propstat>
  </D:response>
</D:multistatus>"""

    subdir_xml = b"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<D:multistatus xmlns:D=\"DAV:\">
  <D:response>
    <D:href>/sets/subdir/</D:href>
    <D:propstat><D:prop><D:resourcetype><D:collection/></D:resourcetype></D:prop></D:propstat>
  </D:response>
  <D:response>
    <D:href>/sets/subdir/live.flac</D:href>
    <D:propstat><D:prop><D:resourcetype/></D:prop></D:propstat>
  </D:response>
</D:multistatus>"""

    def fake_request(self, *args, **kwargs):
        method = kwargs.get("method", args[0] if args else None)
        url = kwargs.get("url", args[1] if len(args) > 1 else None)
        if method != "PROPFIND":
            raise AssertionError(f"Unexpected method: {method}")
        if url.endswith("/sets/"):
            return FakeResponse(207, content=root_xml)
        if url.endswith("/sets/subdir/"):
            return FakeResponse(207, content=subdir_xml)
        raise AssertionError(f"Unexpected url: {url}")

    monkeypatch.setattr(transport.session, "request", fake_request.__get__(transport.session))

    files = list(transport.list_files("sets"))

    assert sorted(files) == ["song.mp3", "subdir/live.flac"]
