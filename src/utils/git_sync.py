"""Git synchronization for metadata files.

This module handles syncing metadata.csv and albums.csv with a remote git repository.
"""

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from filelock import FileLock

from src.utils.config import (
    get_or_create_config_dir,
    load_config,
    save_config,
)
from src.utils.logging import get_logger


def get_git_repo_dir() -> Path:
    """Get path to the git repository directory."""
    return get_or_create_config_dir() / "metadata-repo"


def _get_repo_lock() -> FileLock:
    """Get file lock for git repository operations."""
    lock_path = get_git_repo_dir().parent / ".git-sync.lock"
    return FileLock(str(lock_path), timeout=30)


def get_sync_repo() -> Optional[str]:
    """Get the configured sync repository URL."""
    config = load_config()
    return config.get("sync_repo")


def set_sync_repo(repo_url: str) -> None:
    """Set the sync repository URL."""
    logger = get_logger()
    config = load_config()
    config["sync_repo"] = repo_url
    save_config(config)
    logger.info(f"Sync repository configured: {repo_url}")


def _run_git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command in the specified directory."""
    return subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=check,
    )


def _ensure_repo_cloned(repo_url: str) -> Path:
    """Ensure the git repository is cloned locally."""
    logger = get_logger()
    repo_dir = get_git_repo_dir()

    if repo_dir.exists():
        # Check if it's a valid git repo
        git_dir = repo_dir / ".git"
        if git_dir.exists():
            return repo_dir
        # Not a git repo, remove and re-clone
        shutil.rmtree(repo_dir)

    # Clone the repository
    logger.info(f"Cloning metadata repository from {repo_url}...")
    result = subprocess.run(
        ["git", "clone", repo_url, str(repo_dir)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to clone repository: {result.stderr}")

    return repo_dir


def _sync_file_to_repo(filename: str, repo_dir: Path) -> None:
    """Sync a file from config dir to repo dir."""
    config_dir = get_or_create_config_dir()
    src = config_dir / filename
    dst = repo_dir / filename

    if src.exists():
        shutil.copy2(src, dst)


def _sync_file_from_repo(filename: str, repo_dir: Path) -> None:
    """Sync a file from repo dir to config dir."""
    config_dir = get_or_create_config_dir()
    src = repo_dir / filename
    dst = config_dir / filename

    if src.exists():
        shutil.copy2(src, dst)


def pull_metadata() -> bool:
    """Pull latest metadata from the configured git repository.

    Returns True if sync was performed, False if no repo configured.
    """
    logger = get_logger()
    repo_url = get_sync_repo()
    if not repo_url:
        return False

    with _get_repo_lock():
        repo_dir = _ensure_repo_cloned(repo_url)

        # Pull latest changes
        logger.info("Pulling latest metadata...")
        result = _run_git(["pull", "--rebase"], cwd=repo_dir, check=False)
        if result.returncode != 0:
            logger.warning(f"git pull failed: {result.stderr}")
            # Try to continue anyway - might be a fresh repo with no remote commits

        # Copy files from repo to config dir
        _sync_file_from_repo("metadata.csv", repo_dir)
        _sync_file_from_repo("albums.csv", repo_dir)

        logger.info("Metadata synced from repository")
        return True


def push_metadata() -> bool:
    """Push metadata changes to the configured git repository.

    Returns True if sync was performed, False if no repo configured.
    """
    logger = get_logger()
    repo_url = get_sync_repo()
    if not repo_url:
        return False

    with _get_repo_lock():
        repo_dir = _ensure_repo_cloned(repo_url)

        # Copy files from config dir to repo
        _sync_file_to_repo("metadata.csv", repo_dir)
        _sync_file_to_repo("albums.csv", repo_dir)

        # Check if there are changes
        result = _run_git(["status", "--porcelain"], cwd=repo_dir)
        if not result.stdout.strip():
            logger.info("No metadata changes to push")
            return True

        # Add, commit, and push
        logger.info("Pushing metadata changes...")
        _run_git(["add", "metadata.csv", "albums.csv"], cwd=repo_dir)

        result = _run_git(
            ["commit", "-m", "Update metadata from song-classifier"],
            cwd=repo_dir,
            check=False
        )
        if result.returncode != 0 and "nothing to commit" not in result.stdout:
            logger.warning(f"git commit failed: {result.stderr}")
            return False

        result = _run_git(["push"], cwd=repo_dir, check=False)
        if result.returncode != 0:
            logger.warning(f"git push failed: {result.stderr}")
            logger.warning("Changes committed locally but not pushed. Push manually later.")
            return False

        logger.info("Metadata pushed to repository")
        return True
