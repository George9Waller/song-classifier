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
git clone https://github.com/yourusername/song-classifier.git
cd song-classifier

# Create virtual environment and install
uv venv
uv pip install -e .
```

### Set up OpenAI API key

```bash
export OPENAI_API_KEY=your_key_here
```

Add this to your shell profile (`~/.bashrc`, `~/.zshrc`, etc.) to persist across sessions.

## Usage

### Basic usage

```bash
# Process audio files in current directory
song-classifier

# Process audio files in a specific directory
song-classifier ~/Music/sets

# Process files from a WebDAV server
song-classifier /remote/path --webdav http://user:pass@server/
```

### Options

```
song-classifier [PATH] [OPTIONS]

Arguments:
  PATH                    Directory to scan (default: current directory)

Options:
  -v, --version           Show version and exit
  -h, --help              Show help message and exit
  --webdav HOST           WebDAV host URL to use instead of local filesystem
  --no-skip-processed     Process files even if marked as processed
  --no-skip-in-metadata   Process files even if already in metadata.csv
  --sync-repo URL         Configure git repository URL for syncing metadata
  --no-sync               Skip git sync even if a repository is configured
  --show-config           Show current configuration and exit
```

### Git Sync

Song Classifier can sync your metadata database with a git repository. This allows you to:
- Back up your metadata to a remote repository
- Share metadata across multiple machines
- Track changes to your music library over time

#### Configure a sync repository

```bash
# One-time setup: configure your git repository
song-classifier --sync-repo git@github.com:username/music-metadata.git
```

The repository should be an empty or existing git repo. Song Classifier will:
- Clone the repo to `~/.config/song-classifier/metadata-repo/`
- Pull latest changes before processing files
- Push `metadata.csv` and `albums.csv` after processing

#### Disable sync temporarily

```bash
# Process files without syncing
song-classifier ~/Music/sets --no-sync
```

### View configuration

```bash
song-classifier --show-config
```

This shows:
- Config directory location
- Configured sync repository (if any)

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

- **metadata.csv** - Contains all processed tracks with columns: `key`, `track`, `artist`, `album`, `genre`, `date`
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
