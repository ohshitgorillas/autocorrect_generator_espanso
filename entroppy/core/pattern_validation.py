"""Pattern validation and conflict checking."""

import functools
from typing import TYPE_CHECKING

from entroppy.core.boundaries import BoundaryIndex, BoundaryType, would_trigger_at_end
from entroppy.core.types import Correction
from entroppy.platforms.base import MatchDirection
from entroppy.utils.debug import log_debug_correction

if TYPE_CHECKING:
    from entroppy.utils.debug import DebugTypoMatcher


class SourceWordIndex:
    """Index for efficient source word corruption checks.

    Pre-builds indexes of patterns that appear at word boundaries in source words
    to avoid linear searches. For RTL patterns, indexes prefixes at word boundaries.
    For LTR patterns, indexes suffixes at word boundaries.

    Attributes:
        rtl_patterns: Set of patterns that appear at word boundaries (prefixes) for RTL matching
        ltr_patterns: Set of patterns that appear at word boundaries (suffixes) for LTR matching
        source_words: Original source words set for reference
    """

    def __init__(
        self, source_words: set[str] | frozenset[str], match_direction: MatchDirection
    ) -> None:
        """Build indexes from source words for the given match direction.

        Args:
            source_words: Set of source words to build indexes from
            match_direction: Match direction (RTL for prefix patterns, LTR for suffix patterns)
        """
        self.source_words = source_words
        self.rtl_patterns: set[str] = set()
        self.ltr_patterns: set[str] = set()

        for word in source_words:
            if match_direction == MatchDirection.RIGHT_TO_LEFT:
                # RTL: Index all patterns that appear at word boundaries (prefixes)
                # A pattern appears at a boundary if it starts at:
                # - Position 0 (start of word), OR
                # - After a non-alpha character
                for i in range(len(word)):
                    # Check if position i is at a word boundary
                    if i == 0 or not word[i - 1].isalpha():
                        # Extract all substrings starting at this boundary position
                        for j in range(i + 1, len(word) + 1):
                            pattern = word[i:j]
                            self.rtl_patterns.add(pattern)
            else:
                # LTR: Index all patterns that appear at word boundaries (suffixes)
                # A pattern appears at a boundary if it ends at:
                # - End of word, OR
                # - Before a non-alpha character
                for i in range(len(word)):
                    # Extract all substrings ending at position i or later
                    for j in range(i + 1, len(word) + 1):
                        pattern = word[i:j]
                        # Check if this pattern ends at a word boundary
                        if j >= len(word) or not word[j].isalpha():
                            self.ltr_patterns.add(pattern)

    def would_corrupt(self, typo_pattern: str, match_direction: MatchDirection) -> bool:
        """Check if a pattern would corrupt any source word.

        Args:
            typo_pattern: The typo pattern to check
            match_direction: The match direction

        Returns:
            True if the pattern would corrupt any source word, False otherwise
        """
        if match_direction == MatchDirection.RIGHT_TO_LEFT:
            return typo_pattern in self.rtl_patterns
        return typo_pattern in self.ltr_patterns


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
            f"Pattern ACCEPTED - replaces {len(occurrences)} corrections: "
            f"{', '.join(replaced_strs)}",
            debug_words,
            debug_typo_matcher,
            "Stage 4",
        )


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
                f"Creates '{expected_result}' instead of " f"'{full_word}' for typo '{full_typo}'"
            )
            return False, error_msg
    return True, None


def check_pattern_conflicts(
    typo_pattern: str,
    validation_set: set[str],
    source_words: set[str],
    match_direction: MatchDirection,
    validation_index: BoundaryIndex,
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
        source_word_index: Optional pre-built index for source_words (for optimization)
        target_words: Optional set of target words to check against
            (prevents predictive corrections)

    Returns:
        Tuple of (is_safe, error_message). error_message is None if safe.
    """
    # Check if pattern conflicts with validation words
    if typo_pattern in validation_set:
        return False, f"Conflicts with validation word '{typo_pattern}'"

    # Check if pattern would trigger at end of validation words
    if would_trigger_at_end(typo_pattern, validation_index):
        return False, "Would trigger at end of validation words"

    # FIRST: Check if pattern would corrupt target words
    # (highest priority - prevents predictive corrections)
    # This prevents corrections that would trigger when typing the target word correctly
    if target_words:
        would_corrupt_target = any(
            _cached_would_corrupt(typo_pattern, target_word, match_direction)
            for target_word in target_words
        )
        if would_corrupt_target:
            return False, "Would corrupt target words"

    # Check if pattern would corrupt source words
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


def check_pattern_would_incorrectly_match_other_corrections(
    typo_pattern: str,
    word_pattern: str,
    all_corrections: list[Correction],
    pattern_occurrences: list[Correction],
) -> tuple[bool, str | None]:
    """Check if a pattern would incorrectly match other corrections.

    Checks for substring conflicts in BOTH directions regardless of platform or matching direction:
    - SUFFIX conflicts: If pattern appears as suffix of another correction's typo
      (relevant for QMK RTL matching where patterns match at end)
    - PREFIX conflicts: If pattern appears as prefix of another correction's typo
      (relevant for Espanso LTR matching where patterns match at start)

    If applying the pattern would produce a different result than the direct correction,
    the pattern is unsafe and should be rejected.

    Example:
        Pattern: `toin → tion` (suffix pattern)
        Direct correction: `washingtoin → washington`
        Problem: Pattern would match `washingtoin` as suffix and produce
            `washingtion` ≠ `washington`
        Result: Pattern should be rejected

    Args:
        typo_pattern: The typo pattern to check
        word_pattern: The word pattern to check
        all_corrections: All corrections that exist (to check against)
        pattern_occurrences: Corrections that this pattern would replace (exclude from check)

    Returns:
        Tuple of (is_safe, error_message). error_message is None if safe.
    """
    # Build set of corrections that this pattern replaces (to exclude from check)
    pattern_typos = {(typo, word) for typo, word, _ in pattern_occurrences}

    # Check if pattern would incorrectly match other corrections
    # We need to check in both directions regardless of platform/matching direction:
    # 1. For RTL/QMK: Check if pattern appears as SUFFIX (matches at end)
    # 2. For LTR/Espanso: Check if pattern appears as PREFIX (matches at start)
    # This covers all cases where a pattern could incorrectly match a longer correction

    # Check all other corrections
    for other_typo, other_word, _ in all_corrections:
        # Skip corrections that this pattern replaces
        if (other_typo, other_word) in pattern_typos:
            continue

        # Check if pattern appears as SUFFIX of other correction's typo
        # This is relevant for QMK RTL matching (patterns match at end)
        # Also check NONE boundary patterns that could match as suffixes
        if other_typo.endswith(typo_pattern) and other_typo != typo_pattern:
            # Calculate what applying the pattern would produce
            remaining = other_typo[: -len(typo_pattern)]
            pattern_result = remaining + word_pattern

            # If pattern would produce different result, it's unsafe
            if pattern_result != other_word:
                return False, (
                    f"Would incorrectly match '{other_typo}' → '{other_word}' "
                    f"as suffix (would produce '{pattern_result}' instead)"
                )

        # Check if pattern appears as PREFIX of other correction's typo
        # This is relevant for Espanso LTR matching (patterns match at start)
        # Also check NONE boundary patterns that could match as prefixes
        if other_typo.startswith(typo_pattern) and other_typo != typo_pattern:
            # Calculate what applying the pattern would produce
            remaining = other_typo[len(typo_pattern) :]
            pattern_result = word_pattern + remaining

            # If pattern would produce different result, it's unsafe
            if pattern_result != other_word:
                return False, (
                    f"Would incorrectly match '{other_typo}' → '{other_word}' "
                    f"as prefix (would produce '{pattern_result}' instead)"
                )

    return True, None
