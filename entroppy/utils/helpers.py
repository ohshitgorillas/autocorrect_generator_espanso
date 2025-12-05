"""Shared utility functions for the autocorrect generator."""

import functools
import os
from pathlib import Path
import re
from re import Pattern
from typing import Callable, TextIO

from loguru import logger
from wordfreq import word_frequency as _word_frequency


def compile_wildcard_regex(pattern: str) -> Pattern:
    """Converts a simple wildcard pattern (* syntax) to a compiled regex object.

    e.g., 'in*' -> '^in.*$', '*in' -> '^.*in$', '*teh*' -> '^.*teh.*$'
    """
    parts = [re.escape(part) for part in pattern.split("*")]
    regex_str = ".*".join(parts)
    return re.compile(f"^{regex_str}$")


def expand_file_path(filepath: str | None) -> str | None:
    """Expand user home directory in file path.

    This reduces code duplication by centralizing the os.path.expanduser() call.

    Args:
        filepath: File path (may contain ~)

    Returns:
        Expanded file path string, or None if filepath is None
    """
    if not filepath:
        return None
    return os.path.expanduser(filepath)


@functools.lru_cache(maxsize=None)
def cached_word_frequency(word: str, lang: str = "en") -> float:
    """Cached wrapper for word_frequency to avoid repeated lookups.

    This function caches word frequency lookups to improve performance when
    the same words are looked up multiple times across different stages of
    the pipeline (e.g., collision resolution, typo filtering, QMK ranking).

    Args:
        word: The word to look up
        lang: Language code (default: "en")

    Returns:
        Word frequency as a float

    Note:
        The cache persists across the entire pipeline execution, providing
        significant performance improvements for large datasets with many
        repeated word lookups.
    """
    return float(_word_frequency(word, lang))


def ensure_directory_exists(dir_path: str | Path) -> None:
    """Create directory if it doesn't exist, with consistent error handling.

    This reduces code duplication by centralizing directory creation with
    standardized error handling for PermissionError and OSError.

    Args:
        dir_path: Directory path to create (may be string or Path)

    Raises:
        PermissionError: If directory creation is denied
        OSError: If directory creation fails for other OS-related reasons
    """
    dir_str = str(dir_path)
    try:
        os.makedirs(dir_str, exist_ok=True)
    except PermissionError:
        logger.error(f"✗ Permission denied creating output directory: {dir_str}")
        logger.error("  Please check directory permissions and try again")
        raise
    except OSError as e:
        logger.error(f"✗ OS error creating output directory {dir_str}: {e}")
        raise


def write_file_safely(
    file_path: str | Path,
    content_writer: Callable[[TextIO], None],
    operation_name: str = "writing file",
) -> None:
    """Write to a file with consistent error handling.

    This reduces code duplication by centralizing file writing with
    standardized error handling for PermissionError, OSError, and other exceptions.

    Args:
        file_path: Path to the file to write
        content_writer: Callable that takes a file handle and writes content
        operation_name: Description of the operation for error messages

    Raises:
        PermissionError: If file writing is denied
        OSError: If file writing fails for OS-related reasons
        Exception: For any other unexpected errors during writing
    """
    file_str = str(file_path)
    try:
        # Ensure parent directory exists
        parent_dir = os.path.dirname(file_str) or "."
        ensure_directory_exists(parent_dir)

        with open(file_str, "w", encoding="utf-8") as f:
            content_writer(f)
    except PermissionError:
        logger.error(f"✗ Permission denied {operation_name}: {file_str}")
        logger.error("  Please check file permissions and try again")
        raise
    except OSError as e:
        logger.error(f"✗ OS error {operation_name} {file_str}: {e}")
        raise
    except Exception as e:
        logger.error(f"✗ Unexpected error {operation_name} {file_str}: {e}")
        raise
