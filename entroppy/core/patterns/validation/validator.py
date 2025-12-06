"""Pattern validation and conflict checking."""

import functools
from typing import TYPE_CHECKING

from entroppy.core.boundaries import (
    BoundaryIndex,
    BoundaryType,
    is_substring_of_any,
    would_trigger_at_end,
    would_trigger_at_start,
)
from entroppy.core.types import MatchDirection

if TYPE_CHECKING:
    from entroppy.core.patterns.indexes import SourceWordIndex


# Cache for pattern validation results
@functools.lru_cache(maxsize=10000)
def _cached_would_corrupt(
    typo_pattern: str, source_word: str, match_direction: MatchDirection
) -> bool:
    """Cached version of _would_corrupt_source_word for fallback cases.

    Args:
        typo_pattern: The typo pattern to check
        source_word: The source word to check against
        match_direction: The match direction

    Returns:
        True if the pattern would corrupt the source word, False otherwise
    """
    return _would_corrupt_source_word(typo_pattern, source_word, match_direction)


def _validate_pattern_result(
    typo_pattern: str,
    word_pattern: str,
    full_typo: str,
    full_word: str,
    boundary: BoundaryType,
) -> tuple[bool, str]:
    """Validate that a pattern produces the expected result for a specific case.

    Args:
        typo_pattern: The typo pattern to validate
        word_pattern: The word pattern to validate
        full_typo: The full typo string
        full_word: The full correct word
        boundary: The boundary type (LEFT/RIGHT indicates prefix/suffix,
            NONE/BOTH need pattern position)

    Returns:
        Tuple of (is_valid, expected_result)
    """
    # Determine if pattern is prefix or suffix based on boundary
    # RIGHT boundary = suffix pattern (matches at end)
    # LEFT boundary = prefix pattern (matches at start)
    # NONE/BOTH boundaries: need to check if pattern appears at start or end of typo
    if boundary == BoundaryType.RIGHT:
        # SUFFIX pattern: typo_pattern at end
        remaining_prefix = full_typo[: -len(typo_pattern)]
        expected_result = remaining_prefix + word_pattern
    elif boundary == BoundaryType.LEFT:
        # PREFIX pattern: typo_pattern at start
        remaining_suffix = full_typo[len(typo_pattern) :]
        expected_result = word_pattern + remaining_suffix
    else:
        # NONE or BOTH boundary: check if pattern appears at start or end
        # Try suffix first (more common), then prefix
        if full_typo.endswith(typo_pattern):
            # SUFFIX pattern
            remaining_prefix = full_typo[: -len(typo_pattern)]
            expected_result = remaining_prefix + word_pattern
        elif full_typo.startswith(typo_pattern):
            # PREFIX pattern
            remaining_suffix = full_typo[len(typo_pattern) :]
            expected_result = word_pattern + remaining_suffix
        else:
            # Pattern doesn't match - validation fails
            return False, f"Pattern '{typo_pattern}' not found in '{full_typo}'"

    return expected_result == full_word, expected_result


def _would_corrupt_source_word(
    typo_pattern: str,
    source_word: str,
    match_direction: MatchDirection,
) -> bool:
    """Check if a pattern would corrupt a source word.

    For RTL: checks if pattern appears at word boundaries at the start
    For LTR: checks if pattern appears at word boundaries at the end

    Args:
        typo_pattern: The typo pattern to check
        source_word: The source word to check against
        match_direction: The match direction (RTL for prefix, LTR for suffix)

    Returns:
        True if the pattern would corrupt the source word, False otherwise
    """
    idx = source_word.find(typo_pattern)
    while idx != -1:
        if match_direction == MatchDirection.RIGHT_TO_LEFT:
            # PREFIX pattern: check if there's a word boundary before
            if idx == 0 or not source_word[idx - 1].isalpha():
                return True
        else:
            # SUFFIX pattern: check if there's a word boundary after
            char_after_idx = idx + len(typo_pattern)
            if char_after_idx >= len(source_word) or not source_word[char_after_idx].isalpha():
                return True
        # Look for next occurrence
        idx = source_word.find(typo_pattern, idx + 1)

    return False


def validate_pattern_for_all_occurrences(
    typo_pattern: str,
    word_pattern: str,
    occurrences: list[tuple[str, str, BoundaryType]],
    boundary: BoundaryType,
) -> tuple[bool, str | None]:
    """Validate that a pattern works correctly for all its occurrences.

    Args:
        typo_pattern: The typo pattern to validate
        word_pattern: The word pattern to validate
        occurrences: List of (full_typo, full_word, boundary) tuples
        boundary: The boundary type of the pattern (determines if prefix or suffix)

    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.
    """
    for full_typo, full_word, _ in occurrences:
        is_valid, expected_result = _validate_pattern_result(
            typo_pattern, word_pattern, full_typo, full_word, boundary
        )
        if not is_valid:
            error_msg = (
                f"Creates '{expected_result}' instead of '{full_word}' for typo '{full_typo}'"
            )
            return False, error_msg
    return True, None


def _find_example_prefix_match(
    typo_pattern: str, validation_index: BoundaryIndex, validation_set: set[str]
) -> str | None:
    """Find an example validation word that starts with the typo pattern.

    Args:
        typo_pattern: The typo pattern to check
        validation_index: Pre-built index for validation_set
        validation_set: Set of validation words

    Returns:
        An example word that starts with the pattern, or None if not found
    """
    if typo_pattern in validation_index.prefix_index:
        matching_words = validation_index.prefix_index[typo_pattern]
        # Exclude exact match and return first example
        for word in matching_words:
            if word != typo_pattern and word in validation_set:
                return word
    return None


def _find_example_suffix_match(
    typo_pattern: str, validation_index: BoundaryIndex, validation_set: set[str]
) -> str | None:
    """Find an example validation word that ends with the typo pattern.

    Args:
        typo_pattern: The typo pattern to check
        validation_index: Pre-built index for validation_set
        validation_set: Set of validation words

    Returns:
        An example word that ends with the pattern, or None if not found
    """
    if typo_pattern in validation_index.suffix_index:
        matching_words = validation_index.suffix_index[typo_pattern]
        # Exclude exact match and return first example
        for word in matching_words:
            if word != typo_pattern and word in validation_set:
                return word
    return None


def _check_validation_word_conflicts(
    typo_pattern: str, validation_set: set[str]
) -> tuple[bool, str | None]:
    """Check if pattern conflicts with validation words."""
    if typo_pattern in validation_set:
        return False, f"Conflicts with validation word '{typo_pattern}'"
    return True, None


def _check_end_trigger_conflict(
    typo_pattern: str,
    boundary: BoundaryType,
    validation_index: BoundaryIndex,
    validation_set: set[str],
) -> tuple[bool, str | None]:
    """Check if pattern would trigger at end of validation words."""
    # Skip this check for LEFT and BOTH boundaries (they don't match at word end)
    if boundary in (BoundaryType.LEFT, BoundaryType.BOTH):
        return True, None

    if would_trigger_at_end(typo_pattern, validation_index):
        example_word = _find_example_suffix_match(typo_pattern, validation_index, validation_set)
        if example_word:
            return (
                False,
                f"Would trigger at end of validation words (e.g., '{example_word}')",
            )
        return False, "Would trigger at end of validation words"

    return True, None


def _check_start_trigger_conflict(
    typo_pattern: str,
    boundary: BoundaryType,
    validation_index: BoundaryIndex,
    validation_set: set[str],
) -> tuple[bool, str | None]:
    """Check if pattern would trigger at start of validation words."""
    # Skip this check for RIGHT and BOTH boundaries (they don't match at word start)
    if boundary in (BoundaryType.RIGHT, BoundaryType.BOTH):
        return True, None

    if would_trigger_at_start(typo_pattern, validation_index):
        example_word = _find_example_prefix_match(typo_pattern, validation_index, validation_set)
        if example_word:
            return (
                False,
                f"Would trigger at start of validation words (e.g., '{example_word}')",
            )
        return False, "Would trigger at start of validation words"

    return True, None


def _check_none_boundary_substring_conflict(
    typo_pattern: str,
    boundary: BoundaryType,
    validation_index: BoundaryIndex,
    validation_set: set[str],
) -> tuple[bool, str | None]:
    """Check if NONE boundary pattern appears as substring in validation words."""
    if boundary != BoundaryType.NONE:
        return True, None

    if is_substring_of_any(typo_pattern, validation_index):
        # Find an example validation word containing the pattern
        example_word = None
        for word in validation_set:
            if typo_pattern in word and typo_pattern != word:
                example_word = word
                break
        if example_word:
            return (
                False,
                f"Would falsely trigger on correctly spelled word '{example_word}'",
            )
        return False, "Would falsely trigger on correctly spelled words"

    return True, None


def _check_target_word_corruption(
    typo_pattern: str,
    target_words: set[str] | None,
    match_direction: MatchDirection,
) -> tuple[bool, str | None]:
    """Check if pattern would corrupt target words."""
    if not target_words:
        return True, None

    would_corrupt_target = any(
        _cached_would_corrupt(typo_pattern, target_word, match_direction)
        for target_word in target_words
    )
    if would_corrupt_target:
        return False, "Would corrupt target words"

    return True, None


def _check_source_word_corruption(
    typo_pattern: str,
    source_words: set[str],
    match_direction: MatchDirection,
    source_word_index: "SourceWordIndex | None",
) -> tuple[bool, str | None]:
    """Check if pattern would corrupt source words."""
    if source_word_index is not None:
        # Use optimized index lookup
        would_corrupt_source = source_word_index.would_corrupt(typo_pattern, match_direction)
    else:
        # Fallback to linear search (for backward compatibility or when index not available)
        would_corrupt_source = any(
            _cached_would_corrupt(typo_pattern, source_word, match_direction)
            for source_word in source_words
        )

    if would_corrupt_source:
        return False, "Would corrupt source words"

    return True, None


def check_pattern_conflicts(
    typo_pattern: str,
    validation_set: set[str],
    source_words: set[str],
    match_direction: MatchDirection,
    validation_index: BoundaryIndex,
    boundary: BoundaryType,
    source_word_index: "SourceWordIndex | None" = None,
    target_words: set[str] | None = None,
) -> tuple[bool, str | None]:
    """Check if a pattern conflicts with validation words or would corrupt source/target words.

    Args:
        typo_pattern: The typo pattern to check
        validation_set: Set of valid words
        source_words: Set of source words
        match_direction: The match direction
        validation_index: Pre-built index for validation_set (must match validation_set)
        boundary: The boundary type of the pattern (determines which checks to skip)
        source_word_index: Optional pre-built index for source_words (for optimization)
        target_words: Optional set of target words to check against
            (prevents predictive corrections)

    Returns:
        Tuple of (is_safe, error_message). error_message is None if safe.
    """
    # Check if pattern conflicts with validation words
    is_safe, error = _check_validation_word_conflicts(typo_pattern, validation_set)
    if not is_safe:
        return is_safe, error

    # Check if pattern would trigger at end of validation words
    is_safe, error = _check_end_trigger_conflict(
        typo_pattern, boundary, validation_index, validation_set
    )
    if not is_safe:
        return is_safe, error

    # Check if pattern would trigger at start of validation words
    is_safe, error = _check_start_trigger_conflict(
        typo_pattern, boundary, validation_index, validation_set
    )
    if not is_safe:
        return is_safe, error

    # Check if pattern appears as substring in validation words (for NONE boundary)
    is_safe, error = _check_none_boundary_substring_conflict(
        typo_pattern, boundary, validation_index, validation_set
    )
    if not is_safe:
        return is_safe, error

    # Check if pattern would corrupt target words (highest priority)
    is_safe, error = _check_target_word_corruption(typo_pattern, target_words, match_direction)
    if not is_safe:
        return is_safe, error

    # Check if pattern would corrupt source words
    is_safe, error = _check_source_word_corruption(
        typo_pattern, source_words, match_direction, source_word_index
    )
    if not is_safe:
        return is_safe, error

    return True, None
