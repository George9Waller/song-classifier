"""Logging configuration for song-classifier."""

import logging
import sys
from typing import Optional

_logger: Optional[logging.Logger] = None


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure and return the application logger.

    Args:
        verbose: If True, set log level to DEBUG, otherwise INFO.

    Returns:
        Configured logger instance.
    """
    global _logger

    if _logger is not None:
        # Update level if already configured
        _logger.setLevel(logging.DEBUG if verbose else logging.INFO)
        return _logger

    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    _logger = logging.getLogger("song-classifier")
    _logger.setLevel(level)

    return _logger


def get_logger() -> logging.Logger:
    """Get the application logger, creating with defaults if needed.

    Returns:
        Logger instance.
    """
    global _logger
    if _logger is None:
        _logger = setup_logging(verbose=False)
    return _logger
