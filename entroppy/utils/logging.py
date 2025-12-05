"""Logging configuration for EntropPy using loguru."""

from pathlib import Path
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


def add_log_file_handler(log_file: str | Path, verbose: bool = False, debug: bool = False) -> None:
    """Add a file handler to the existing logger configuration.

    This function adds a file handler without removing existing handlers,
    allowing logs to be written to both stderr and a file.

    Args:
        log_file: Path to log file
        verbose: Enable INFO level messages
        debug: Enable DEBUG level messages (overrides verbose)
    """
    # Determine log level
    if debug:
        level = "DEBUG"
    elif verbose:
        level = "INFO"
    else:
        level = "WARNING"

    # File format (no color codes)
    if debug:
        file_format_str = (
            "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
        )
    else:
        file_format_str = "{message}"

    # Ensure directory exists
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Add file handler
    logger.add(
        log_path,
        format=file_format_str,
        level=level,
        colorize=False,
        encoding="utf-8",
    )
