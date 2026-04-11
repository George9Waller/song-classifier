import sys

from src.utils.file_transport import FileTransport
from src.utils.logging import get_logger


def validate_path(path: str, *, file_transport: FileTransport) -> str:
    """Validate and normalize a directory path.

    Args:
        path: Path to validate.

    Returns:
        Absolute, normalized path.

    Raises:
        ValueError: If path is invalid.
    """
    return file_transport.validate_path(path)


def validate_path_or_exit(path: str, *, file_transport: FileTransport) -> str:
    logger = get_logger()

    try:
        valid_path = validate_path(path, file_transport=file_transport)
        logger.debug(f"Validated path: {valid_path}")
        return valid_path
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
