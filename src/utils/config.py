"""Configuration utilities for song-classifier.

Handles XDG-compliant config paths and WebDAV credentials.
"""

import json
import os
from pathlib import Path
from typing import Optional


def get_or_create_config_dir() -> Path:
    """Get or create the config directory using XDG paths."""
    if os.name == 'nt':  # Windows
        base = Path(os.environ.get('APPDATA', Path.home()))
    else:
        base = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    config_dir = base / 'song-classifier'
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_or_create_metadata_file_path() -> Path:
    """Get path to the metadata CSV file."""
    return get_or_create_config_dir() / 'metadata.csv'


def get_or_create_albums_file_path() -> Path:
    """Get path to the albums CSV file."""
    return get_or_create_config_dir() / 'albums.csv'


def get_or_create_temp_dir() -> Path:
    """Get or create the temp directory for WebDAV downloads."""
    temp_dir = get_or_create_config_dir() / 'temp'
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def get_config_file() -> Path:
    """Get path to the song-classifier config file."""
    return get_or_create_config_dir() / "config.json"


def load_config() -> dict:
    """Load configuration from config file."""
    config_file = get_config_file()
    if config_file.exists():
        with open(config_file, "r") as f:
            return json.load(f)
    return {}


def save_config(config: dict) -> None:
    """Save configuration to config file."""
    config_file = get_config_file()
    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)


def get_webdav_credentials() -> tuple[Optional[str], Optional[str]]:
    """Get WebDAV credentials from config or environment.

    Returns:
        Tuple of (username, password), either may be None.
    """
    # Environment variables take precedence
    username = os.environ.get("WEBDAV_USERNAME")
    password = os.environ.get("WEBDAV_PASSWORD")

    if username and password:
        return username, password

    # Fall back to config file
    config = load_config()
    webdav_config = config.get("webdav", {})
    return (
        username or webdav_config.get("username"),
        password or webdav_config.get("password"),
    )


def set_webdav_credentials(username: Optional[str], password: Optional[str]) -> None:
    """Save WebDAV credentials to config file."""
    config = load_config()
    if "webdav" not in config:
        config["webdav"] = {}
    config["webdav"]["username"] = username
    config["webdav"]["password"] = password
    save_config(config)
