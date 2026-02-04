from dataclasses import dataclass
from typing import Optional


@dataclass
class AlbumMetadata:
    name: str
    artist: str


@dataclass
class TrackMetadata:
    key: str
    track: str
    artist: str
    album: AlbumMetadata
    genre: str
    date: Optional[str]
