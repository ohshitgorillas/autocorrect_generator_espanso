"""QMK output generation logic."""

import os
import sys

from loguru import logger

from entroppy.core import BoundaryType, Config, Correction
from entroppy.platforms.qmk.formatting import format_boundary_markers
from entroppy.utils import Constants


def format_correction_line(typo: str, word: str, boundary: BoundaryType) -> str:
    """Format a single correction line with QMK boundary markers."""
    formatted_typo = format_boundary_markers(typo, boundary)
    return f"{formatted_typo}{Constants.QMK_OUTPUT_SEPARATOR}{word}"


def sort_corrections(lines: list[str]) -> list[str]:
    """Sort correction lines alphabetically by correction word."""
    return sorted(lines, key=lambda line: line.split(Constants.QMK_OUTPUT_SEPARATOR)[1])


def determine_output_path(output_path: str | None) -> str | None:
    """Determine final output file path."""
    if not output_path:
        return None

    if os.path.isdir(output_path) or not output_path.endswith(".txt"):
        return os.path.join(output_path, "autocorrect.txt")
    return output_path


def generate_output(corrections: list[Correction], output_path: str | None, config: Config) -> None:
    """
    Generate QMK text output.

    Format:
    typo -> correction
    :typo -> correction
    typo: -> correction
    :typo: -> correction

    Sorted alphabetically by correction word.
    """
    lines = [format_correction_line(typo, word, boundary) for typo, word, boundary in corrections]

    lines = sort_corrections(lines)

    output_file = determine_output_path(output_path)

    if output_file:
        try:
            os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
        except PermissionError:
            logger.error(f"✗ Permission denied creating output directory: {output_file}")
            logger.error("  Please check directory permissions and try again")
            raise
        except OSError as e:
            logger.error(f"✗ OS error creating output directory {output_file}: {e}")
            raise

        try:
            with open(output_file, "w", encoding="utf-8") as f:
                for line in lines:
                    f.write(line + "\n")
        except PermissionError:
            logger.error(f"✗ Permission denied writing file: {output_file}")
            logger.error("  Please check file permissions and try again")
            raise
        except OSError as e:
            logger.error(f"✗ OS error writing file {output_file}: {e}")
            raise
        except Exception as e:
            logger.error(f"✗ Unexpected error writing file {output_file}: {e}")
            raise

        if config.verbose:
            logger.info(f"  Wrote {len(lines)} corrections to: {output_file}")
    else:
        try:
            for line in lines:
                logger.info(line)
        except (OSError, IOError) as e:
            logger.error(f"✗ Error writing to stdout: {e}")
            raise
