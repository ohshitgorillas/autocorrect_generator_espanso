"""Logging configuration for EntropPy using loguru."""

import sys
from loguru import logger


def setup_logger(verbose: bool = False, debug: bool = False) -> None:
    """Configure loguru logger based on verbose and debug flags.

    Args:
        verbose: Enable INFO level messages
        debug: Enable DEBUG level messages (overrides verbose)
    """
    # Remove default handler
    logger.remove()

    # Determine log level
    if debug:
        level = "DEBUG"
    elif verbose:
        level = "INFO"
    else:
        level = "WARNING"

    # Add handler with appropriate format
    # For INFO and above: simple format without timestamp
    # For DEBUG: detailed format with timestamp and location
    if debug:
        format_str = (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        )
    else:
        format_str = "<level>{message}</level>"

    logger.add(
        sys.stderr,
        format=format_str,
        level=level,
        colorize=True,
    )
