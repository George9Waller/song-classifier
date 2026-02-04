import json
import os
import re
from typing import Any, Dict, Optional

from openai import OpenAI

from models import AlbumMetadata, TrackMetadata
from data import get_album_metadata


def _ensure_openai_client() -> "OpenAI":
    api_key = os.environ.get("OPENAI_API_KEY")
    return OpenAI(api_key=api_key)


def _build_prompt(filename: str, existing: Optional[TrackMetadata]) -> str:
    existing_json = None
    if existing:
        existing_json = json.dumps(
            {
                "track": existing.track,
                "artist": existing.artist,
                "album": {"name": existing.album.name, "artist": existing.album.artist},
                "genre": existing.genre,
                "date": existing.date,
            }
        )
    existing_section = (
        f"Existing tags (may be empty):\n{existing_json}\n\n" if existing_json else ""
    )

    # Provide guidance for album selection and known albums for snapping.
    known_albums_list = [
        {"name": a.name, "artist": a.artist} for a in get_album_metadata()
    ]

    return (
        "You are a music metadata expert. Given an audio filename, infer the most likely track metadata.\n"
        "Return STRICT JSON only with this exact schema and no extra keys: \n"
        "{\n"
        "  \"track\": string,\n"
        "  \"artist\": string,\n"
        "  \"album\": { \"name\": string, \"artist\": string },\n"
        "  \"genre\": string,\n"
        "  \"date\": string | null  // ISO-8601 yyyy or yyyy-mm-dd if known, else null\n"
        "}\n\n"
        "Album selection rules (do NOT guess from filename beyond these rules):\n"
        "- If the content is a festival/event, the album should be the festival name with the year (e.g., 'Coachella 2022'). The album artist is 'Various Artists'.\n"
        "- If the content is part of an ongoing series (e.g., 'Radio 1 Essential Mix', 'Radio 1 Dance Presents'), the album should be that series name (no year), album artist 'Various Artists'.\n"
        "- Otherwise, for a single-artist set/event, use '{Artist} Sets' as the album name and set album artist to that artist.\n"
        "- If your chosen album name exactly matches one of the known albums provided, use that name and its album artist as-is.\n\n"
        "Track title rules:\n"
        "- If the content is a festival/event, set the track title to exactly the artist name (no venue/city/year in the title).\n"
        "- If the content is part of a series (e.g., 'Essential Mix'), set the track title to '{Artist} {Year}' if a year is known, otherwise just '{Artist}'.\n"
        "- Otherwise, choose a concise, human-friendly title; avoid repeating the album name in the track title.\n\n"
        f"Known albums: {json.dumps(known_albums_list)}\n\n"
        "Heuristics:\n"
        "- Normalize separators like underscores and dashes to spaces.\n"
        "- If city/country/year present, consider it for date or parentheses in track.\n"
        "- If artist is unclear, infer the most probable from the string tokens.\n"
        "- Prefer widely used genre bucket (e.g., 'House', 'Techno', 'Pop').\n"
        "- If truly unknown, use null or a plausible guess rather than placeholders.\n\n"
        f"Filename: {filename}\n"
        f"{existing_section}"
        "Output: JSON only."
    )


def _extract_json(text: str) -> str:
    fenced = re.sub(r"^```[a-zA-Z]*\n|\n```$", "", text.strip())
    if fenced.startswith("{") and fenced.endswith("}"):
        return fenced
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return match.group(0)
    return text


def parse_metadata_with_ai(filename: str, existing: Optional[TrackMetadata] = None) -> TrackMetadata:
    client = _ensure_openai_client()

    prompt = _build_prompt(filename, existing)

    completion = client.chat.completions.create(
        model="gpt-5-nano",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that returns strict JSON only."},
            {"role": "user", "content": prompt},
        ],
        temperature=1,
    )

    content = completion.choices[0].message.content or "{}"
    json_str = _extract_json(content)

    try:
        data: Dict[str, Any] = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse JSON from model: {exc}\nRaw: {content}")

    album_data = data.get("album") or {}
    ai_album = AlbumMetadata(
        name=album_data.get("name") or "",
        artist=album_data.get("artist") or (data.get("artist") or ""),
    )

    track = data.get("track") or ""
    artist = data.get("artist") or ai_album.artist
    genre = data.get("genre") or ""
    date = data.get("date")

    # No post-processing: rely on the model following the provided rules and known album list
    return TrackMetadata(
        key=filename,
        track=track,
        artist=artist,
        album=ai_album,
        genre=genre,
        date=date,
    )
