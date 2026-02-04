# Song Classifier

A CLI tool that auto-tags music files (DJ sets, live recordings) using AI to infer metadata from filenames.

## Features

- **AI-powered metadata inference** - Uses OpenAI to intelligently parse filenames and suggest track metadata
- **Interactive TUI** - Review and edit suggested metadata before applying
- **Multiple audio formats** - Supports MP3, FLAC, M4A/MP4, OGG, Opus, WAV, AIFF
- **WebDAV support** - Process files directly from a WebDAV server
- **Git sync** - Automatically sync your metadata database with a git repository
- **Skip processed files** - Tracks which files have been processed to avoid duplicates

## Installation

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager (recommended)
- OpenAI API key

### Install from source

```bash
# Clone the repository
git clone https://github.com/George9Waller/song-classifier.git
cd song-classifier

# Create virtual environment and install
uv venv
uv pip install -e .

# Or install with dev dependencies
uv pip install -e ".[dev]"
```

### Install CLI globally

```bash
# Install with pipx for global access
pipx install git+https://github.com/George9Waller/song-classifier.git

# Or with uv
uv tool install git+https://github.com/George9Waller/song-classifier.git
```

### Set up OpenAI API key

```bash
export OPENAI_API_KEY=your_key_here
```

Add this to your shell profile (`~/.bashrc`, `~/.zshrc`, etc.) to persist across sessions.

### Development setup

```bash
# Install in editable mode for development
uv pip install -e ".[dev]"

# Run via uv (recommended - automatically uses the venv)
uv run song-classifier --help

# Or activate the venv first, then run directly
source .venv/bin/activate
song-classifier --help
```

### Linting
This project uses ruff for linting.

```bash
uv run ruff check .
```

### Tests
This project has tests configured with pytest.

```bash
uv run pytest
```

## Usage

### Basic usage

```bash
# Process audio files in current directory
song-classifier process

# Process audio files in a specific directory
song-classifier process ~/Music/sets

# Preview changes without applying (dry-run)
song-classifier process ~/Music/sets --dry-run

# Process files from a WebDAV server
song-classifier process /remote/path --webdav http://server/ --webdav-user USER
```

### Commands

```
song-classifier process [PATH] [OPTIONS]
  Process audio files in a directory

  Options:
    --webdav HOST           WebDAV host URL
    --webdav-user USER      WebDAV username (or WEBDAV_USERNAME env var)
    --webdav-password PASS  WebDAV password (or WEBDAV_PASSWORD env var)
    --no-skip-processed     Process files even if marked as processed
    --no-skip-in-metadata   Process files even if already in metadata.csv
    --no-sync               Skip git sync
    --dry-run               Show what would be done without making changes
    -V, --verbose           Enable verbose/debug output
    -y, --yes               Automatically accept AI metadata without a confirmation UI (use with caution)

song-classifier config show
  Show current configuration

song-classifier config set-sync-repo URL
  Configure git repository for metadata sync

song-classifier config set-webdav --user USER --password PASS
  Configure WebDAV credentials

Global options:
  -v, --version           Show version and exit
  -h, --help              Show help message
```

### Git Sync

Song Classifier can sync your metadata database with a git repository. This allows you to:
- Back up your metadata to a remote repository
- Share metadata across multiple machines
- Track changes to your music library over time

#### Configure a sync repository

```bash
# One-time setup: configure your git repository
song-classifier config set-sync-repo https://github.com/username/set-metadata.git
```

The repository should be an empty or existing git repo. Song Classifier will:
- Clone the repo to `~/.config/song-classifier/metadata-repo/`
- Pull latest changes before processing files
- Push `metadata.csv` and `albums.csv` after processing

#### Disable sync temporarily

```bash
# Process files without syncing
song-classifier process ~/Music/sets --no-sync
```

### View configuration

```bash
song-classifier config show
```

This shows:
- Config directory location
- Configured sync repository (if any)
- WebDAV credentials status

## Configuration

All configuration and data is stored in `~/.config/song-classifier/`:

```
~/.config/song-classifier/
├── config.json       # Configuration (sync repo URL, etc.)
├── metadata.csv      # Track metadata database
├── albums.csv        # Album metadata database
├── metadata-repo/    # Git repository clone (if sync configured)
└── temp/             # Temporary files for WebDAV downloads
```

### Data files

- **metadata.csv** - Contains all processed tracks with columns: `key`, `track`, `artist`, `album_name`, `album_artist`, `genre`, `date`
- **albums.csv** - Album catalog used for AI suggestions with columns: `name`, `artist`

## How it works

1. **Scan** - Recursively finds audio files in the specified directory
2. **Check** - Skips files already processed (unless `--no-skip-processed`)
3. **Download** - For WebDAV, downloads file to temp directory
4. **Read tags** - Extracts any existing metadata from the file
5. **AI inference** - Sends filename to OpenAI to infer metadata
6. **Review** - Opens TUI for you to review and edit the suggested metadata
7. **Save** - Updates the CSV databases and writes tags back to the audio file
8. **Upload** - For WebDAV, uploads the modified file back to the server
9. **Sync** - Commits and pushes metadata changes to git (if configured)

## Supported formats

| Format | Extension | Read | Write |
|--------|-----------|------|-------|
| MP3    | .mp3      | ✓    | ✓     |
| FLAC   | .flac     | ✓    | ✓     |
| AAC    | .m4a, .mp4| ✓    | ✓     |
| Opus   | .opus     | ✓    | ✓     |
| Vorbis | .ogg      | ✓    | ✓     |
| WAV    | .wav      | ✓    | -     |
| AIFF   | .aiff, .aif| ✓   | -     |

## License

MIT
