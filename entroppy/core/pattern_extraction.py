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

    Optimized implementation that groups corrections by their "other part"
    (the part that doesn't change) to eliminate redundant pattern length checks.

    Args:
        corrections: List of corrections to analyze
        boundary_type: Boundary type to filter by (LEFT for prefix, RIGHT for suffix)
        is_suffix: True for suffix patterns, False for prefix patterns

    Returns:
        Dict mapping (typo_pattern, word_pattern, boundary) to list of
        (full_typo, full_word, original_boundary) tuples that match this pattern.
    """
    patterns = defaultdict(list)

    # Filter corrections by boundary type first
    filtered_corrections = [
        (typo, word, boundary) for typo, word, boundary in corrections if boundary == boundary_type
    ]

    if not filtered_corrections:
        return patterns

    # Group corrections by word length for efficient processing
    corrections_by_len = defaultdict(list)
    for typo, word, boundary in filtered_corrections:
        corrections_by_len[len(word)].append((typo, word, boundary))

    for length_group in corrections_by_len.values():
        # Optimized approach: Group corrections by their "other part" at each pattern length
        # This allows us to find patterns shared by multiple corrections more efficiently
        # Instead of checking all lengths for each correction individually, we group first
        # and then process groups together

        # Build a map: (other_part_typo, other_part_word, length) -> list of corrections
        # This groups corrections that share the same "other part" at the same length
        other_part_groups: dict[
            tuple[str, str, int], list[tuple[str, str, BoundaryType, str, str]]
        ] = defaultdict(list)

        # First pass: Extract all valid patterns and group by other_part
        for typo, word, boundary in length_group:
            max_pattern_length = len(word) - _MIN_OTHER_PART_LENGTH

            # Check all valid pattern lengths (preserving original behavior)
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

                # Group by other_part to find patterns shared by multiple corrections
                other_part_key = (other_part_typo, other_part_word, length)
                other_part_groups[other_part_key].append(
                    (typo, word, boundary, typo_pattern, word_pattern)
                )

        # Second pass: Extract patterns from groups
        # This allows us to process corrections with the same other_part together
        for (
            other_part_typo,
            other_part_word,
            length,
        ), group_corrections in other_part_groups.items():
            # Group by actual pattern (typo_pattern, word_pattern) to find common patterns
            pattern_groups = defaultdict(list)
            for typo, word, boundary, typo_pattern, word_pattern in group_corrections:
                pattern_key = (typo_pattern, word_pattern, boundary)
                pattern_groups[pattern_key].append((typo, word, boundary))

            # Add all patterns found
            for pattern_key, matches in pattern_groups.items():
                patterns[pattern_key].extend(matches)

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
