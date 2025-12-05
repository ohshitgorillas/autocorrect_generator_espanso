"""QMK output generation logic."""

import os

from loguru import logger

from entroppy.core import BoundaryType, Config, Correction
from entroppy.platforms.qmk.formatting import format_boundary_markers
from entroppy.utils import Constants
from entroppy.utils.helpers import ensure_directory_exists, write_file_safely


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
    """Generate QMK text output.

    Format:
    typo -> correction
    :typo -> correction
    typo: -> correction
    :typo: -> correction

    Sorted alphabetically by correction word.
    """
    # Deduplicate corrections (same typo, word, boundary)
    seen = set()
    unique_corrections = []
    for correction in corrections:
        if correction not in seen:
            seen.add(correction)
            unique_corrections.append(correction)

    lines = [
        format_correction_line(typo, word, boundary) for typo, word, boundary in unique_corrections
    ]

    lines = sort_corrections(lines)

    output_file = determine_output_path(output_path)

    if output_file:
        # Ensure parent directory exists
        parent_dir = os.path.dirname(output_file) or "."
        ensure_directory_exists(parent_dir)

        # Write file with consistent error handling
        def write_content(f):
            for line in lines:
                f.write(line + "\n")

        write_file_safely(output_file, write_content, "writing QMK output file")

        if config.verbose:
            logger.info(f"  Wrote {len(lines)} corrections to: {output_file}")
    else:
        try:
            for line in lines:
                logger.info(line)
        except (OSError, IOError) as e:
            logger.error(f"✗ Error writing to stdout: {e}")
            raise
