"""YAML writing helpers for Espanso platform."""

import sys
from typing import TextIO

from loguru import logger
import yaml


def write_yaml_to_stream(
    yaml_output: dict, stream: TextIO, error_context: str = "YAML output"
) -> None:
    """Write YAML output to a stream (file or stdout).

    This helper function eliminates duplication between backend.py (stdout)
    and file_writing.py (file handle) by centralizing the YAML dump logic.

    Args:
        yaml_output: Dictionary to write as YAML
        stream: Output stream (file handle or sys.stdout)
        error_context: Context string for error messages

    Raises:
        yaml.YAMLError: If YAML serialization fails
        OSError: If writing to stream fails (only for stdout)
        IOError: If writing to stream fails (only for stdout)
    """
    try:
        yaml.safe_dump(
            yaml_output,
            stream,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
            width=float("inf"),
        )
    except yaml.YAMLError as e:
        logger.error(f"✗ YAML serialization error {error_context}: {e}")
        raise
    except (OSError, IOError) as e:
        # Only relevant for stdout, but handle gracefully
        if stream is sys.stdout:
            logger.error(f"✗ Error writing to stdout: {e}")
            raise
        # For file handles, let the caller handle it
        raise
