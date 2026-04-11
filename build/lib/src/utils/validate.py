import argparse
import sys
from typing import Callable

from src.constants import DEFAULT_PATH
from src.utils.ai_metadata import MissingAPIKeyError, validate_api_key
from src.utils.file_transport import get_file_transport_for_args
from src.utils.logging import get_logger
from src.utils.path import validate_path_or_exit


def has_openai_api_key_set(func: Callable) -> Callable:
    """Decorator to check if OpenAI API key is set before executing the function."""

    def wrapper(args: argparse.Namespace, *other_args, **kwargs):
        logger = get_logger()

        # Validate API key early
        if not getattr(args, "dry_run", False):
            try:
                validate_api_key()
            except MissingAPIKeyError as e:
                logger.error(str(e))
                sys.exit(1)

        return func(args, *other_args, **kwargs)

    return wrapper


def validate_path(func: Callable) -> Callable:
    """Decorator to check if the provided path is valid before executing the function."""

    def wrapper(args: argparse.Namespace, *other_args, **kwargs):
        file_transport = get_file_transport_for_args(args)
        path = args.path or DEFAULT_PATH

        # Validate path
        path = validate_path_or_exit(path, file_transport=file_transport)

        return func(
            args, *other_args, file_transport=file_transport, path=path, **kwargs
        )

    return wrapper
