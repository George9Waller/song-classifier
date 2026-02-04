# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
uv venv
uv pip install -e ".[dev]"

# Run the application
song-classifier [COMMAND] [OPTIONS]

# Or run directly without installing
uv run -m src.cli [COMMAND] [OPTIONS]

# Run tests
uv run pytest tests/ -v

# Environment
export OPENAI_API_KEY=your_key_here
```

## Project Structure

```
song-classifier/
├── src/
│   ├── __init__.py
│   ├── cli.py              # CLI entry point (argparse with subcommands)
│   ├── main.py             # Core async classify_filename() orchestration
│   ├── data/
│   │   ├── __init__.py     # CSV read/write, get/upsert functions
│   │   └── models.py       # TrackMetadata, AlbumMetadata dataclasses
│   └── utils/
│       ├── __init__.py
│       ├── config.py       # XDG config paths, WebDAV credentials
│       ├── constants.py    # Magic strings (PROCESSED_MARKER, etc.)
│       ├── logging.py      # Logging configuration
│       ├── git_sync.py     # Git repository sync with file locking
│       ├── file_transport.py  # LocalTransport, WebdavTransport
│       ├── file_metadata.py   # Mutagen read/write for audio formats
│       ├── ai_metadata.py     # Async OpenAI prompt building and parsing
│       └── ui_confirm.py      # Textual TUI for metadata review
├── tests/
│   ├── __init__.py
│   ├── conftest.py         # Pytest fixtures
│   ├── test_models.py
│   ├── test_data.py
│   ├── test_ai_metadata.py
│   ├── test_file_transport.py
│   └── test_integration.py
├── pyproject.toml
├── README.md
└── CLAUDE.md
```

## Architecture

CLI tool that auto-tags music files using OpenAI to infer metadata from filenames.

### Data Flow

```
cli.py orchestrates (async):
  git_sync.pull_metadata()   → sync from remote git repo (if configured)
  FileTransport.list_files() → iterate audio files (filtered by extension)

  For each file:
    FileTransport.load_file()  → get local copy (downloads if WebDAV)
    read_file_metadata()       → extract existing tags via mutagen
    parse_metadata_with_ai()   → async OpenAI infers metadata from filename
    confirm_metadata()         → Textual TUI for user review/edit
    upsert_*_metadata()        → persist to CSV databases
    write_file_metadata()      → write tags back to audio file
    FileTransport.save_file()  → upload if WebDAV

  git_sync.push_metadata()   → commit and push changes (if configured)
```

### Key Abstractions

**FileTransport** (`src/utils/file_transport.py`): Factory that returns `LocalTransport` or `WebdavTransport`. Both implement `list_files()`, `load_file()`, `save_file()`. Filters to audio files only. WebDAV supports authentication via config or environment variables.

**TrackMetadata/AlbumMetadata** (`src/data/models.py`): Core dataclasses passed through the entire pipeline. `TrackMetadata.key` is the original filename. Include `to_csv_row()` and `from_csv_row()` methods for CSV serialization.

**Audio format handlers** (`src/utils/file_metadata.py`): Format-specific read/write functions (`_from_mp3`, `_write_mp3`, etc.) using mutagen. Files are marked as processed via a comment tag containing `PROCESSED_MARKER`.

**Git sync** (`src/utils/git_sync.py`): Handles cloning, pulling, and pushing metadata to a configured git repository. Uses file locking to prevent race conditions.

### AI Metadata Inference

`ai_metadata.py` builds a detailed prompt with:
- Album selection rules (festivals → "Various Artists", series → no year, single-artist → "{Artist} Sets")
- Known albums from albums.csv for snapping to existing entries
- Track title formatting rules

Uses `gpt-5-nano` model (configurable). Response is parsed as JSON into `TrackMetadata`. Client is injectable for testing.

### Configuration & Data Storage

All data stored in `~/.config/song-classifier/`:
- `config.json`: Configuration (sync repo URL, WebDAV credentials)
- `metadata.csv`: All processed tracks (key, track, artist, album_name, album_artist, genre, date)
- `albums.csv`: Album catalog used for AI suggestions (name, artist)
- `metadata-repo/`: Git repository clone (if sync configured)
- `temp/`: Temporary files for WebDAV downloads

### Supported Audio Formats

MP3, FLAC, M4A/MP4, OGG, Opus, WAV, AIFF - defined in `AUDIO_EXTENSIONS` in `file_transport.py`.

### CLI Commands

```
song-classifier process [PATH] [OPTIONS]

Arguments:
  PATH                    Directory to scan (default: current directory)

Options:
  --webdav HOST           WebDAV host URL
  --webdav-user USER      WebDAV username (or WEBDAV_USERNAME env var)
  --webdav-password PASS  WebDAV password (or WEBDAV_PASSWORD env var)
  --no-skip-processed     Process already-processed files
  --no-skip-in-metadata   Process files already in metadata.csv
  --no-sync               Skip git sync
  --dry-run               Show what would be done without making changes
  -V, --verbose           Enable verbose output

song-classifier config show
  Show current configuration

song-classifier config set-sync-repo URL
  Configure git repository URL for syncing metadata

song-classifier config set-webdav --user USER --password PASS
  Configure WebDAV credentials

Global options:
  -v, --version           Show version and exit
```

Legacy CLI syntax (without subcommands) is still supported for backward compatibility.
