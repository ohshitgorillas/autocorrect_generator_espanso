"""Boundary detection for typo corrections."""

from .config import BoundaryType


def is_substring_of_any(typo: str, word_set: set[str]) -> bool:
    """Check if typo is a substring of any word."""
    for word in word_set:
        if typo in word and typo != word:
            return True
    return False


def would_trigger_at_start(typo: str, validation_set: set[str]) -> bool:
    """Check if typo appears as prefix."""
    for word in validation_set:
        if word.startswith(typo) and word != typo:
            return True
    return False


def would_trigger_at_end(typo: str, validation_set: set[str]) -> bool:
    """Check if typo appears as suffix."""
    for word in validation_set:
        if word.endswith(typo) and word != typo:
            return True
    return False


def determine_boundaries(
    typo: str,
    validation_set: set[str],
    source_words: set[str],
) -> BoundaryType | None:
    """Determine what boundaries are needed for a typo."""
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
