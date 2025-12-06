"""Pattern generalization for typo corrections."""

from typing import TYPE_CHECKING, Callable

from loguru import logger

from entroppy.core.boundaries import BoundaryType
from entroppy.core.patterns.logging import is_debug_pattern
from entroppy.core.patterns.validation import (
    build_validation_indexes,
    extract_and_merge_patterns,
    extract_debug_typos,
    run_parallel_validation,
    run_single_threaded_validation,
)
from entroppy.core.types import Correction, MatchDirection

if TYPE_CHECKING:
    from entroppy.utils.debug import DebugTypoMatcher


def _extract_debug_typos_sets(
    debug_typo_matcher: "DebugTypoMatcher | None",
) -> tuple[set[str], set[str]]:
    """Extract debug typos into exact and wildcard sets."""
    debug_typos_result = extract_debug_typos(debug_typo_matcher)
    if debug_typos_result is not None:
        exact, wildcard = debug_typos_result
        return exact, wildcard
    return set(), set()


def _filter_graveyard_patterns(
    patterns_to_validate: dict,
    is_in_graveyard: Callable[[str, str, BoundaryType], bool] | None,
    debug_typo_matcher: "DebugTypoMatcher | None",
    verbose: bool,
) -> dict:
    """Filter out patterns already in graveyard to prevent infinite loops."""
    if is_in_graveyard is None:
        return patterns_to_validate

    filtered_patterns = {}
    skipped_count = 0
    for (typo, word, boundary), occurrences in patterns_to_validate.items():
        if is_in_graveyard(typo, word, boundary):
            skipped_count += 1
            # Debug log for patterns being skipped
            if debug_typo_matcher and is_debug_pattern(typo, occurrences, debug_typo_matcher):
                logger.debug(
                    f"[GRAVEYARD FILTER] Skipping pattern already in graveyard: "
                    f"'{typo}' → '{word}' ({boundary.value})"
                )
        else:
            filtered_patterns[(typo, word, boundary)] = occurrences

    if skipped_count > 0 and verbose:
        logger.debug(f"Filtered {skipped_count} patterns already in graveyard")

    return filtered_patterns


def _run_validation(
    patterns_to_validate: dict,
    validation_set: set[str],
    source_words: set[str],
    match_direction: MatchDirection,
    min_typo_length: int,
    debug_words: set[str],
    corrections: list[Correction],
    indexes,
    debug_typo_matcher: "DebugTypoMatcher | None",
    jobs: int,
    verbose: bool,
) -> tuple[
    list[Correction],
    set[Correction],
    dict[Correction, list[Correction]],
    list[tuple[str, str, BoundaryType, str]],
]:
    """Run validation using parallel or single-threaded approach."""
    if jobs > 1 and len(patterns_to_validate) > 10:
        return run_parallel_validation(
            patterns_to_validate,
            validation_set,
            source_words,
            match_direction,
            min_typo_length,
            debug_words,
            corrections,
            jobs,
            verbose,
        )
    # pylint: disable=duplicate-code
    # False positive: Similar parameter lists are expected when calling the same function
    # from different contexts (orchestration vs validation runner). This is not duplicate
    # code that should be refactored - it's the same function call with the same parameters.
    return run_single_threaded_validation(
        patterns_to_validate,
        min_typo_length,
        validation_set,
        source_words,
        match_direction,
        corrections,
        indexes,
        debug_words,
        debug_typo_matcher,
        verbose,
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
    jobs: int = 1,
    is_in_graveyard: Callable[[str, str, BoundaryType], bool] | None = None,
    pattern_cache: (
        dict[
            tuple[str, str, BoundaryType, bool],
            list[tuple[str, str, BoundaryType, int]],
        ]
        | None
    ) = None,
) -> tuple[
    list[Correction],
    set[Correction],
    dict[Correction, list[Correction]],
    list[tuple[str, str, BoundaryType, str]],
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
        jobs: Number of parallel workers to use (1 = sequential)
        is_in_graveyard: Optional function to check if a pattern is in graveyard
            (prevents infinite loops by skipping already-rejected patterns)
        pattern_cache: Optional cache for pattern extraction results

    Returns:
        Tuple of (patterns, corrections_to_remove, pattern_replacements, rejected_patterns)
        where rejected_patterns is a list of (typo_pattern, word_pattern, boundary, reason) tuples
    """
    if debug_words is None:
        debug_words = set()

    # Build validation indexes
    indexes = build_validation_indexes(validation_set, source_words, match_direction, corrections)

    # Extract debug typos for pattern extraction logging
    debug_typos_exact, debug_typos_wildcard = _extract_debug_typos_sets(debug_typo_matcher)

    # Extract and merge prefix/suffix patterns
    found_patterns = extract_and_merge_patterns(
        corrections,
        debug_typos_exact,
        debug_typos_wildcard,
        verbose,
        is_in_graveyard,
        pattern_cache,
    )

    # Filter out patterns with only one occurrence before validation
    patterns_to_validate = {k: v for k, v in found_patterns.items() if len(v) >= 2}

    # Filter out patterns already in graveyard to prevent infinite loops
    patterns_to_validate = _filter_graveyard_patterns(
        patterns_to_validate, is_in_graveyard, debug_typo_matcher, verbose
    )

    # Choose parallel or single-threaded validation
    return _run_validation(
        patterns_to_validate,
        validation_set,
        source_words,
        match_direction,
        min_typo_length,
        debug_words,
        corrections,
        indexes,
        debug_typo_matcher,
        jobs,
        verbose,
    )
