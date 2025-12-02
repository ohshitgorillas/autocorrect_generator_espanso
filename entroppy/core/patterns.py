"""Pattern generalization for typo corrections."""

from collections import defaultdict
from typing import TYPE_CHECKING

from loguru import logger

from entroppy.core.boundaries import BoundaryIndex
from entroppy.core.types import Correction
from entroppy.core.pattern_extraction import find_prefix_patterns, find_suffix_patterns
from entroppy.core.pattern_validation import (
    SourceWordIndex,
    _log_pattern_acceptance,
    _log_pattern_rejection,
    check_pattern_conflicts,
    check_pattern_would_incorrectly_match_other_corrections,
    validate_pattern_for_all_occurrences,
)
from entroppy.platforms.base import MatchDirection
from entroppy.utils.debug import (
    is_debug_correction,
    log_if_debug_correction,
)

if TYPE_CHECKING:
    from entroppy.utils.debug import DebugTypoMatcher


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

    # Extract debug typos for pattern extraction logging
    debug_typos_set: set[str] | None = None
    if debug_typo_matcher:
        # Extract exact patterns from matcher for debug logging
        debug_typos_set = set(debug_typo_matcher.exact_patterns)

    # Extract BOTH prefix and suffix patterns
    # Both types are useful regardless of match direction:
    # - Prefix patterns: match at start of words (e.g., "teh" → "the")
    # - Suffix patterns: match at end of words (e.g., "toin" → "tion")
    prefix_patterns = find_prefix_patterns(corrections, debug_typos=debug_typos_set)
    suffix_patterns = find_suffix_patterns(corrections, debug_typos=debug_typos_set)

    # Combine both pattern types into single dict
    # If same pattern key exists in both, merge the occurrences
    found_patterns = defaultdict(list)
    for pattern_key, occurrences in prefix_patterns.items():
        found_patterns[pattern_key].extend(occurrences)
    for pattern_key, occurrences in suffix_patterns.items():
        # Merge occurrences if pattern already exists, otherwise add new
        if pattern_key in found_patterns:
            # Deduplicate: same correction might appear in both prefix and suffix patterns
            existing_typos = set(found_patterns[pattern_key])
            for occ in occurrences:
                if occ not in existing_typos:
                    found_patterns[pattern_key].append(occ)
        else:
            found_patterns[pattern_key].extend(occurrences)

    if verbose:
        logger.info(
            f"Found {len(prefix_patterns)} prefix and {len(suffix_patterns)} "
            f"suffix pattern candidates ({len(found_patterns)} unique patterns)..."
        )
        logger.info("Generalizing patterns...")

    for (typo_pattern, word_pattern, boundary), occurrences in found_patterns.items():
        # Skip patterns with only one occurrence (not worth generalizing)
        if len(occurrences) < 2:
            if verbose and debug_typo_matcher:
                # Check if this pattern matches any debug typos
                if any(
                    debug_typo.lower() in typo_pattern.lower()
                    or any(debug_typo.lower() in occ[0].lower() for occ in occurrences)
                    for debug_typo in debug_typo_matcher.exact_patterns
                ):
                    logger.debug(
                        f"[PATTERN GENERALIZATION] Skipping pattern "
                        f"'{typo_pattern}' → '{word_pattern}': "
                        f"only {len(occurrences)} occurrence (need 2+)"
                    )
            continue

        # Check if any of the occurrences involve debug items (for logging)
        has_debug_occurrence = any(
            is_debug_correction(occ, debug_words, debug_typo_matcher) for occ in occurrences
        )

        # Debug logging for pattern candidates
        is_debug_pattern = False
        if debug_typo_matcher:
            is_debug_pattern = any(
                debug_typo.lower() in typo_pattern.lower()
                or any(debug_typo.lower() in occ[0].lower() for occ in occurrences)
                for debug_typo in debug_typo_matcher.exact_patterns
            )
            if is_debug_pattern:
                logger.debug(
                    f"[PATTERN GENERALIZATION] Processing pattern candidate: "
                    f"'{typo_pattern}' → '{word_pattern}' ({len(occurrences)} occurrences)"
                )

        # Reject patterns that are too short
        if len(typo_pattern) < min_typo_length:
            reason = f"Too short (< {min_typo_length})"
            rejected_patterns.append((typo_pattern, word_pattern, reason))
            if is_debug_pattern:
                logger.debug(
                    f"[PATTERN GENERALIZATION] REJECTED: "
                    f"'{typo_pattern}' → '{word_pattern}': {reason}"
                )
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
        # Use boundary to determine if pattern is prefix or suffix, not match_direction
        is_valid, validation_error = validate_pattern_for_all_occurrences(
            typo_pattern, word_pattern, occurrences, boundary
        )
        if not is_valid:
            rejected_patterns.append((typo_pattern, word_pattern, validation_error))
            if is_debug_pattern:
                logger.debug(
                    f"[PATTERN GENERALIZATION] REJECTED: '{typo_pattern}' → '{word_pattern}': "
                    f"{validation_error}"
                )
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

        # Extract target words from occurrences (prevents predictive corrections)
        target_words = {word for _, word, _ in occurrences}

        # Check for conflicts with validation words or source/target words
        is_safe, conflict_error = check_pattern_conflicts(
            typo_pattern,
            validation_set,
            source_words,
            match_direction,
            validation_index,
            source_word_index,
            target_words=target_words,
        )
        if not is_safe:
            rejected_patterns.append((typo_pattern, word_pattern, conflict_error))
            if is_debug_pattern:
                logger.debug(
                    f"[PATTERN GENERALIZATION] REJECTED: '{typo_pattern}' → '{word_pattern}': "
                    f"{conflict_error}"
                )
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

        # Check if pattern would incorrectly match other corrections
        # This is critical for QMK where patterns can incorrectly match longer typos
        is_safe, incorrect_match_error = check_pattern_would_incorrectly_match_other_corrections(
            typo_pattern,
            word_pattern,
            corrections,  # All corrections to check against
            occurrences,  # Corrections this pattern replaces (exclude from check)
        )
        if not is_safe:
            rejected_patterns.append((typo_pattern, word_pattern, incorrect_match_error))
            if is_debug_pattern:
                logger.debug(
                    f"[PATTERN GENERALIZATION] REJECTED: '{typo_pattern}' → '{word_pattern}': "
                    f"{incorrect_match_error}"
                )
            _log_pattern_rejection(
                typo_pattern,
                word_pattern,
                boundary,
                incorrect_match_error,
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
