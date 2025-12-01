"""Pattern generalization for typo corrections."""

from loguru import logger

from entroppy.core.boundaries import BoundaryIndex
from entroppy.core.types import Correction
from entroppy.core.pattern_extraction import find_prefix_patterns, find_suffix_patterns
from entroppy.core.pattern_validation import (
    SourceWordIndex,
    _log_pattern_acceptance,
    _log_pattern_rejection,
    check_pattern_conflicts,
    validate_pattern_for_all_occurrences,
)
from entroppy.platforms.base import MatchDirection
from entroppy.utils.debug import (  # pylint: disable=unused-import
    DebugTypoMatcher,
    is_debug_correction,
    log_if_debug_correction,
)


def generalize_patterns(
    corrections: list[Correction],
    validation_set: set[str],
    source_words: set[str],
    min_typo_length: int,
    match_direction: MatchDirection,
    verbose: bool = False,
    debug_words: set[str] | None = None,
    debug_typo_matcher: "DebugTypoMatcher | None" = None,
) -> tuple[
    list[Correction],
    set[Correction],
    dict[Correction, list[Correction]],
    list[tuple[str, str, str]],
]:
    """Find repeated patterns, create generalized rules, and return corrections to be removed.

    Args:
        corrections: List of corrections to analyze
        validation_set: Set of valid words
        source_words: Set of source words
        min_typo_length: Minimum typo length
        match_direction: Platform match direction
        verbose: Whether to print verbose output
        debug_words: Set of words to debug (exact matches)
        debug_typo_matcher: Matcher for debug typos (with wildcards/boundaries)

    Returns:
        Tuple of (patterns, corrections_to_remove, pattern_replacements, rejected_patterns)
    """
    if debug_words is None:
        debug_words = set()

    patterns = []
    corrections_to_remove = set()
    pattern_replacements = {}
    rejected_patterns = []

    # Build boundary index for efficient validation checks
    validation_index = BoundaryIndex(validation_set)

    # Build source word index for efficient corruption checks
    source_word_index = SourceWordIndex(source_words, match_direction)

    # Choose pattern finding strategy based on match direction
    if match_direction == MatchDirection.RIGHT_TO_LEFT:
        # RTL matching (QMK): look for prefix patterns (LEFT boundary)
        found_patterns = find_prefix_patterns(corrections)
        pattern_type = "prefix"
    else:
        # LTR matching (Espanso): look for suffix patterns (RIGHT boundary)
        found_patterns = find_suffix_patterns(corrections)
        pattern_type = "suffix"

    if verbose:
        logger.info(f"Generalizing {len(found_patterns)} {pattern_type} patterns...")

    for (typo_pattern, word_pattern, boundary), occurrences in found_patterns.items():
        # Skip patterns with only one occurrence (not worth generalizing)
        if len(occurrences) < 2:
            continue

        # Check if any of the occurrences involve debug items (for logging)
        has_debug_occurrence = any(
            is_debug_correction(occ, debug_words, debug_typo_matcher) for occ in occurrences
        )

        # Reject patterns that are too short
        if len(typo_pattern) < min_typo_length:
            reason = f"Too short (< {min_typo_length})"
            rejected_patterns.append((typo_pattern, word_pattern, reason))
            _log_pattern_rejection(
                typo_pattern,
                word_pattern,
                boundary,
                f"{reason}, would have replaced {len(occurrences)} corrections",
                has_debug_occurrence,
                debug_words,
                debug_typo_matcher,
            )
            continue

        # Validate that pattern works correctly for all occurrences
        is_valid, validation_error = validate_pattern_for_all_occurrences(
            typo_pattern, word_pattern, occurrences, match_direction
        )
        if not is_valid:
            rejected_patterns.append((typo_pattern, word_pattern, validation_error))
            _log_pattern_rejection(
                typo_pattern,
                word_pattern,
                boundary,
                validation_error,
                has_debug_occurrence,
                debug_words,
                debug_typo_matcher,
            )
            continue

        # Check for conflicts with validation words or source words
        is_safe, conflict_error = check_pattern_conflicts(
            typo_pattern,
            validation_set,
            source_words,
            match_direction,
            validation_index,
            source_word_index,
        )
        if not is_safe:
            rejected_patterns.append((typo_pattern, word_pattern, conflict_error))
            _log_pattern_rejection(
                typo_pattern,
                word_pattern,
                boundary,
                conflict_error,
                has_debug_occurrence,
                debug_words,
                debug_typo_matcher,
            )
            continue

        # Pattern passed all checks - accept it
        patterns.append((typo_pattern, word_pattern, boundary))
        pattern_key = (typo_pattern, word_pattern, boundary)
        pattern_replacements[pattern_key] = occurrences

        # Log pattern acceptance for debug
        _log_pattern_acceptance(
            typo_pattern,
            word_pattern,
            boundary,
            occurrences,
            has_debug_occurrence,
            debug_words,
            debug_typo_matcher,
        )

        # Mark original corrections for removal
        for typo, word, orig_boundary in occurrences:
            corrections_to_remove.add((typo, word, orig_boundary))
            # Log individual replacements for debug items
            correction = (typo, word, orig_boundary)
            log_if_debug_correction(
                correction,
                f"Will be replaced by pattern: {typo_pattern} → {word_pattern}",
                debug_words,
                debug_typo_matcher,
                "Stage 4",
            )

    return patterns, corrections_to_remove, pattern_replacements, rejected_patterns
