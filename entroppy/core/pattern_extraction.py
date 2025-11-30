"""Pattern extraction from typo corrections."""

from collections import defaultdict

from entroppy.core.boundaries import BoundaryType
from entroppy.core.types import Correction

# Minimum length for the non-pattern part when extracting patterns
# This prevents extracting nonsensical patterns that are too short
_MIN_OTHER_PART_LENGTH = 2


def _extract_pattern_parts(
    typo: str, word: str, length: int, is_suffix: bool
) -> tuple[str, str, str, str]:
    """Extract pattern parts from typo and word.

    Args:
        typo: The typo string
        word: The correct word string
        length: Length of pattern to extract
        is_suffix: True for suffix patterns, False for prefix patterns

    Returns:
        Tuple of (typo_pattern, word_pattern, other_part_typo, other_part_word)
    """
    if is_suffix:
        # Extract suffix patterns
        typo_pattern = typo[-length:]
        word_pattern = word[-length:]
        other_part_typo = typo[:-length]
        other_part_word = word[:-length]
    else:
        # Extract prefix patterns
        typo_pattern = typo[:length]
        word_pattern = word[:length]
        other_part_typo = typo[length:]
        other_part_word = word[length:]

    return typo_pattern, word_pattern, other_part_typo, other_part_word


def _find_patterns(
    corrections: list[Correction],
    boundary_type: BoundaryType,
    is_suffix: bool,
) -> dict[tuple[str, str, BoundaryType], list[tuple[str, str, BoundaryType]]]:
    """Find common patterns (prefix or suffix) in corrections.

    Args:
        corrections: List of corrections to analyze
        boundary_type: Boundary type to filter by (LEFT for prefix, RIGHT for suffix)
        is_suffix: True for suffix patterns, False for prefix patterns

    Returns:
        Dict mapping (typo_pattern, word_pattern, boundary) to list of
        (full_typo, full_word, original_boundary) tuples that match this pattern.
    """
    patterns = defaultdict(list)
    # Group corrections by word length to make comparison more efficient
    corrections_by_len = defaultdict(list)
    for typo, word, boundary in corrections:
        corrections_by_len[len(word)].append((typo, word, boundary))

    for length_group in corrections_by_len.values():
        for typo, word, boundary in length_group:
            # Only extract patterns from corrections with matching boundary type
            if boundary != boundary_type:
                continue

            max_pattern_length = len(word) - _MIN_OTHER_PART_LENGTH

            for length in range(2, max_pattern_length + 1):
                if len(typo) < length:
                    continue

                typo_pattern, word_pattern, other_part_typo, other_part_word = (
                    _extract_pattern_parts(typo, word, length, is_suffix)
                )

                # Skip if patterns are identical (useless pattern)
                if typo_pattern == word_pattern:
                    continue
                # Ensure the other parts match before considering a pattern valid
                if other_part_typo != other_part_word:
                    continue

                pattern_key = (typo_pattern, word_pattern, boundary)
                patterns[pattern_key].append((typo, word, boundary))

    return patterns


def find_suffix_patterns(
    corrections: list[Correction],
) -> dict[tuple[str, str, BoundaryType], list[tuple[str, str, BoundaryType]]]:
    """Find common suffix patterns (for RIGHT boundaries).

    Returns a dict mapping (typo_suffix, word_suffix, boundary) to list of
    (full_typo, full_word, original_boundary) tuples that match this pattern.
    """
    return _find_patterns(corrections, BoundaryType.RIGHT, is_suffix=True)


def find_prefix_patterns(
    corrections: list[Correction],
) -> dict[tuple[str, str, BoundaryType], list[tuple[str, str, BoundaryType]]]:
    """Find common prefix patterns (for LEFT boundaries).

    Returns a dict mapping (typo_prefix, word_prefix, boundary) to list of
    (full_typo, full_word, original_boundary) tuples that match this pattern.
    """
    return _find_patterns(corrections, BoundaryType.LEFT, is_suffix=False)
