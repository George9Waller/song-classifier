from dataclasses import dataclass
from typing import Optional


@dataclass
class AlbumMetadata:
    """Metadata for an album."""

    name: str
    artist: str

    def to_csv_row(self) -> dict[str, str]:
        """Convert to CSV-compatible dict."""
        return {"name": self.name, "artist": self.artist}

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> "AlbumMetadata":
        """Reconstruct from CSV row."""
        return cls(name=row["name"], artist=row["artist"])


@dataclass
class TrackMetadata:
    """Metadata for a track."""

    key: str
    track: str
    artist: str
    album: AlbumMetadata
    genre: str
    date: Optional[str]

    def to_csv_row(self) -> dict[str, str]:
        """Flatten to CSV-compatible dict with album_name and album_artist."""
        return {
            "key": self.key,
            "track": self.track,
            "artist": self.artist,
            "album_name": self.album.name,
            "album_artist": self.album.artist,
            "genre": self.genre,
            "date": self.date or "",
        }

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> "TrackMetadata":
        """Reconstruct from flattened CSV row."""
        return cls(
            key=row["key"],
            track=row["track"],
            artist=row["artist"],
            album=AlbumMetadata(name=row["album_name"], artist=row["album_artist"]),
            genre=row["genre"],
            date=row["date"] or None,
        )
