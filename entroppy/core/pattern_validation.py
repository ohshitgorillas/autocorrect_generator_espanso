"""Pattern validation and conflict checking."""

from typing import TYPE_CHECKING

from entroppy.core.boundaries import BoundaryType, would_trigger_at_end
from entroppy.platforms.base import MatchDirection
from entroppy.utils import log_debug_correction

if TYPE_CHECKING:
    from entroppy.utils import DebugTypoMatcher


def _validate_pattern_result(
    typo_pattern: str,
    word_pattern: str,
    full_typo: str,
    full_word: str,
    match_direction: MatchDirection,
) -> tuple[bool, str]:
    """Validate that a pattern produces the expected result for a specific case.

    Args:
        typo_pattern: The typo pattern to validate
        word_pattern: The word pattern to validate
        full_typo: The full typo string
        full_word: The full correct word
        match_direction: The match direction (RTL for prefix, LTR for suffix)

    Returns:
        Tuple of (is_valid, expected_result)
    """
    if match_direction == MatchDirection.RIGHT_TO_LEFT:
        # PREFIX pattern: typo_pattern at start
        remaining_suffix = full_typo[len(typo_pattern) :]
        expected_result = word_pattern + remaining_suffix
    else:
        # SUFFIX pattern: typo_pattern at end
        remaining_prefix = full_typo[: -len(typo_pattern)]
        expected_result = remaining_prefix + word_pattern

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


def _log_pattern_rejection(
    typo_pattern: str,
    word_pattern: str,
    boundary: BoundaryType,
    reason: str,
    has_debug_occurrence: bool,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
) -> None:
    """Log pattern rejection for debug purposes.

    Args:
        typo_pattern: The rejected typo pattern
        word_pattern: The rejected word pattern
        boundary: The boundary type
        reason: Reason for rejection
        has_debug_occurrence: Whether any occurrences involve debug items
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos
    """
    if has_debug_occurrence:
        pattern_correction = (typo_pattern, word_pattern, boundary)
        log_debug_correction(
            pattern_correction,
            f"Pattern rejected - {reason}",
            debug_words,
            debug_typo_matcher,
            "Stage 4",
        )


def _log_pattern_acceptance(
    typo_pattern: str,
    word_pattern: str,
    boundary: BoundaryType,
    occurrences: list[tuple[str, str, BoundaryType]],
    has_debug_occurrence: bool,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
) -> None:
    """Log pattern acceptance for debug purposes.

    Args:
        typo_pattern: The accepted typo pattern
        word_pattern: The accepted word pattern
        boundary: The boundary type
        occurrences: List of corrections this pattern replaces
        has_debug_occurrence: Whether any occurrences involve debug items
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos
    """
    if has_debug_occurrence:
        pattern_correction = (typo_pattern, word_pattern, boundary)
        replaced_strs = [f"{t}→{w}" for t, w, _ in occurrences[:3]]
        if len(occurrences) > 3:
            replaced_strs.append(f"... and {len(occurrences) - 3} more")
        log_debug_correction(
            pattern_correction,
            f"Pattern ACCEPTED - replaces {len(occurrences)} corrections: {', '.join(replaced_strs)}",
            debug_words,
            debug_typo_matcher,
            "Stage 4",
        )


def validate_pattern_for_all_occurrences(
    typo_pattern: str,
    word_pattern: str,
    occurrences: list[tuple[str, str, BoundaryType]],
    match_direction: MatchDirection,
) -> tuple[bool, str | None]:
    """Validate that a pattern works correctly for all its occurrences.

    Args:
        typo_pattern: The typo pattern to validate
        word_pattern: The word pattern to validate
        occurrences: List of (full_typo, full_word, boundary) tuples
        match_direction: The match direction

    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.
    """
    for full_typo, full_word, _ in occurrences:
        is_valid, expected_result = _validate_pattern_result(
            typo_pattern, word_pattern, full_typo, full_word, match_direction
        )
        if not is_valid:
            error_msg = (
                f"Creates '{expected_result}' instead of " f"'{full_word}' for typo '{full_typo}'"
            )
            return False, error_msg
    return True, None


def check_pattern_conflicts(
    typo_pattern: str,
    validation_set: set[str],
    source_words: set[str],
    match_direction: MatchDirection,
) -> tuple[bool, str | None]:
    """Check if a pattern conflicts with validation words or would corrupt source words.

    Args:
        typo_pattern: The typo pattern to check
        validation_set: Set of valid words
        source_words: Set of source words
        match_direction: The match direction

    Returns:
        Tuple of (is_safe, error_message). error_message is None if safe.
    """
    # Check if pattern conflicts with validation words
    if typo_pattern in validation_set:
        return False, f"Conflicts with validation word '{typo_pattern}'"

    # Check if pattern would trigger at end of validation words
    if would_trigger_at_end(typo_pattern, validation_set):
        return False, "Would trigger at end of validation words"

    # Check if pattern would corrupt source words
    would_corrupt_source = any(
        _would_corrupt_source_word(typo_pattern, source_word, match_direction)
        for source_word in source_words
    )
    if would_corrupt_source:
        return False, "Would corrupt source words"

    return True, None
