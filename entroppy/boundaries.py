"""Boundary detection for typo corrections."""

from .config import BoundaryType


def parse_boundary_markers(pattern: str) -> tuple[str, BoundaryType | None]:
    """Parse boundary markers from a pattern string.

    Supports the following formats:
    - :pattern: -> (pattern, BoundaryType.BOTH)
    - :pattern -> (pattern, BoundaryType.LEFT)
    - pattern: -> (pattern, BoundaryType.RIGHT)
    - pattern -> (pattern, None)

    Args:
        pattern: The pattern string with optional boundary markers

    Returns:
        Tuple of (core_pattern, boundary_type)
    """
    if not pattern:
        return pattern, None

    starts_with_colon = pattern.startswith(":")
    ends_with_colon = pattern.endswith(":")

    # Determine boundary type
    if starts_with_colon and ends_with_colon:
        boundary_type = BoundaryType.BOTH
        core_pattern = pattern[1:-1]
    elif starts_with_colon:
        boundary_type = BoundaryType.LEFT
        core_pattern = pattern[1:]
    elif ends_with_colon:
        boundary_type = BoundaryType.RIGHT
        core_pattern = pattern[:-1]
    else:
        boundary_type = None
        core_pattern = pattern

    return core_pattern, boundary_type


def _check_typo_in_wordset(typo: str, word_set: set[str], check_type: str) -> bool:
    """Check if typo matches any word in the set based on check type.

    Args:
        typo: The typo string to check
        word_set: Set of words to check against
        check_type: Type of check - 'substring', 'prefix', or 'suffix'

    Returns:
        True if typo matches any word according to check_type
    """
    for word in word_set:
        if typo == word:
            continue
        if check_type == 'substring' and typo in word:
            return True
        elif check_type == 'prefix' and word.startswith(typo):
            return True
        elif check_type == 'suffix' and word.endswith(typo):
            return True
    return False


def is_substring_of_any(typo: str, word_set: set[str]) -> bool:
    """Check if typo is a substring of any word."""
    return _check_typo_in_wordset(typo, word_set, 'substring')


def would_trigger_at_start(typo: str, validation_set: set[str]) -> bool:
    """Check if typo appears as prefix."""
    return _check_typo_in_wordset(typo, validation_set, 'prefix')


def would_trigger_at_end(typo: str, validation_set: set[str]) -> bool:
    """Check if typo appears as suffix."""
    return _check_typo_in_wordset(typo, validation_set, 'suffix')


def determine_boundaries(
    typo: str,
    validation_set: set[str],
    source_words: set[str],
) -> BoundaryType | None:
    """Determine what boundaries are needed for a typo.

    Args:
        typo: The typo string
        validation_set: Set of valid words
        source_words: Set of source words

    Returns:
        BoundaryType indicating what boundaries are needed, or None if correction should be skipped
    """
    # Check if typo appears as substring in other contexts
    is_substring_source = is_substring_of_any(typo, source_words)
    is_substring_validation = is_substring_of_any(typo, validation_set)

    if not is_substring_source and not is_substring_validation:
        return BoundaryType.NONE

    appears_as_prefix = would_trigger_at_start(typo, validation_set)
    appears_as_suffix = would_trigger_at_end(typo, validation_set)

    if not appears_as_prefix and not appears_as_suffix:
        return BoundaryType.BOTH
    if appears_as_suffix and not appears_as_prefix:
        return BoundaryType.LEFT
    if appears_as_prefix and not appears_as_suffix:
        return BoundaryType.RIGHT
    return BoundaryType.BOTH
