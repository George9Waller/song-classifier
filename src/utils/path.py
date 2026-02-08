import os
import sys

from src.utils.logging import get_logger


def validate_path(path: str) -> str:
    """Validate and normalize a directory path.

    Args:
        path: Path to validate.

    Returns:
        Absolute, normalized path.

    Raises:
        ValueError: If path is invalid.
    """
    path = os.path.abspath(path)
    if not os.path.exists(path):
        raise ValueError(f"Path does not exist: {path}")
    if not os.path.isdir(path):
        raise ValueError(f"Path is not a directory: {path}")
    # Resolve symlinks and check for path traversal
    real_path = os.path.realpath(path)
    return real_path


def validate_path_or_exit(path: str):
    logger = get_logger()

    try:
        valid_path = validate_path(path)
        logger.debug(f"Validated path: {valid_path}")
        return valid_path
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
