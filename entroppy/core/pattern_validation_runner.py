"""Pattern validation runners for single-threaded and parallel execution."""

from collections import defaultdict
from multiprocessing import Pool
from typing import TYPE_CHECKING, Any, Callable

from loguru import logger
from tqdm import tqdm

from entroppy.core.boundaries import BoundaryIndex, BoundaryType
from entroppy.core.pattern_conflicts import (
    check_pattern_redundant_with_other_patterns,
    check_pattern_would_incorrectly_match_other_corrections,
)
from entroppy.core.pattern_extraction import find_prefix_patterns, find_suffix_patterns
from entroppy.core.pattern_indexes import CorrectionIndex, SourceWordIndex, ValidationIndexes
from entroppy.core.pattern_validation import (
    check_pattern_conflicts,
    validate_pattern_for_all_occurrences,
)
from entroppy.core.pattern_validation_worker import (
    PatternValidationContext,
    _validate_single_pattern_worker,
    init_pattern_validation_worker,
)
from entroppy.core.types import Correction, MatchDirection
from entroppy.utils.debug import is_debug_correction

from .pattern_logging import (
    is_debug_pattern,
    log_pattern_candidate,
    process_accepted_pattern,
    process_rejected_pattern,
)

if TYPE_CHECKING:
    from entroppy.utils.debug import DebugTypoMatcher


def _build_validation_indexes(
    validation_set: set[str],
    source_words: set[str],
    match_direction: MatchDirection,
    corrections: list[Correction],
) -> ValidationIndexes:
    """Build all validation indexes needed for pattern validation.

    Args:
        validation_set: Set of valid words
        source_words: Set of source words
        match_direction: Platform match direction
        corrections: List of corrections to analyze

    Returns:
        ValidationIndexes containing all built indexes
    """
    return ValidationIndexes(
        validation_index=BoundaryIndex(validation_set),
        source_word_index=SourceWordIndex(source_words, match_direction),
        correction_index=CorrectionIndex(corrections),
    )


def _extract_debug_typos(
    debug_typo_matcher: "DebugTypoMatcher | None",
) -> tuple[set[str], set[str]] | None:
    """Extract debug typos sets from debug typo matcher.

    Args:
        debug_typo_matcher: Matcher for debug typos (with wildcards/boundaries)

    Returns:
        Tuple of (exact_patterns, wildcard_patterns) or None if no matcher provided.
        exact_patterns: Patterns to match exactly (no wildcards)
        wildcard_patterns: Core patterns from wildcard patterns (for substring matching)
    """
    if debug_typo_matcher:
        # Extract exact patterns (for exact matching)
        exact_patterns = set(debug_typo_matcher.exact_patterns)

        # Extract wildcard pattern cores (for substring matching)
        # Get cores from all wildcard patterns (remove * and boundary markers)
        wildcard_patterns = set()
        for pattern in (
            debug_typo_matcher.wildcard_originals
            + debug_typo_matcher.left_wildcard_originals
            + debug_typo_matcher.right_wildcard_originals
            + debug_typo_matcher.both_wildcard_originals
        ):
            # Remove boundary markers and wildcards to get core pattern
            core = pattern.strip(":").replace("*", "")
            if core:  # Only add non-empty cores
                wildcard_patterns.add(core)

        return (exact_patterns, wildcard_patterns)
    return None


def _extract_and_merge_patterns(
    corrections: list[Correction],
    debug_typos_exact: set[str],
    debug_typos_wildcard: set[str],
    verbose: bool,
    is_in_graveyard: Callable[[str, str, BoundaryType], bool] | None = None,
    pattern_cache: (
        dict[tuple[str, str, BoundaryType, bool], list[tuple[str, str, BoundaryType, int]]] | None
    ) = None,
) -> dict[tuple[str, str, BoundaryType], list[Correction]]:
    """Extract prefix and suffix patterns and merge them.

    Args:
        corrections: List of corrections to analyze
        debug_typos_exact: Set of exact debug typo patterns (for exact matching)
        debug_typos_wildcard: Set of wildcard debug typo pattern cores (for substring matching)
        verbose: Whether to print verbose output
        is_in_graveyard: Optional function to check if a pattern is in graveyard
            (prevents infinite loops by skipping already-rejected patterns)
        pattern_cache: Optional cache for pattern extraction results

    Returns:
        Dictionary mapping pattern keys to their occurrences
    """
    # Combine for backward compatibility with existing pattern extraction functions
    debug_typos_set = (
        debug_typos_exact | debug_typos_wildcard
        if (debug_typos_exact or debug_typos_wildcard)
        else None
    )

    # Extract BOTH prefix and suffix patterns
    # Both types are useful regardless of match direction:
    # - Prefix patterns: match at start of words (e.g., "teh" → "the")
    # - Suffix patterns: match at end of words (e.g., "toin" → "tion")
    prefix_patterns = find_prefix_patterns(
        corrections,
        debug_typos=debug_typos_set,
        debug_typos_exact=debug_typos_exact,
        debug_typos_wildcard=debug_typos_wildcard,
        verbose=verbose,
        is_in_graveyard=is_in_graveyard,
        pattern_cache=pattern_cache,
    )
    suffix_patterns = find_suffix_patterns(
        corrections,
        debug_typos=debug_typos_set,
        debug_typos_exact=debug_typos_exact,
        debug_typos_wildcard=debug_typos_wildcard,
        verbose=verbose,
        is_in_graveyard=is_in_graveyard,
        pattern_cache=pattern_cache,
    )

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

    return found_patterns


def _validate_single_pattern_single_threaded(
    typo_pattern: str,
    word_pattern: str,
    boundary: BoundaryType,
    occurrences: list[Correction],
    min_typo_length: int,
    validation_set: set[str],
    source_words: set[str],
    match_direction: MatchDirection,
    corrections: list[Correction],
    indexes: ValidationIndexes,
    debug_typo_matcher: "DebugTypoMatcher | None",
    verbose: bool,
) -> tuple[bool, str | None]:
    """Validate a single pattern in single-threaded mode.

    Args:
        typo_pattern: The typo pattern to validate
        word_pattern: The word pattern
        boundary: The boundary type
        occurrences: List of occurrences for this pattern
        min_typo_length: Minimum typo length
        validation_set: Set of valid words
        source_words: Set of source words
        match_direction: Platform match direction
        corrections: All corrections to check against
        indexes: Validation indexes
        debug_typo_matcher: Matcher for debug typos
        verbose: Whether to print verbose output

    Returns:
        Tuple of (is_valid, error_message). is_valid is True if pattern passes,
        False otherwise. error_message is None if valid, otherwise contains reason.
    """
    # Skip patterns with only one occurrence (already filtered, but keep for safety)
    if len(occurrences) < 2:
        if verbose and debug_typo_matcher:
            if is_debug_pattern(typo_pattern, occurrences, debug_typo_matcher):
                logger.debug(
                    f"[PATTERN GENERALIZATION] Skipping pattern "
                    f"'{typo_pattern}' → '{word_pattern}': "
                    f"only {len(occurrences)} occurrence (need 2+)"
                )
        return False, "Too few occurrences"

    # Reject patterns that are too short
    if len(typo_pattern) < min_typo_length:
        return False, f"Too short (< {min_typo_length})"

    # Validate that pattern works correctly for all occurrences
    is_valid, validation_error = validate_pattern_for_all_occurrences(
        typo_pattern, word_pattern, occurrences, boundary
    )
    if not is_valid:
        return False, validation_error or "Validation failed"

    # Extract target words from occurrences (prevents predictive corrections)
    target_words = {word for _, word, _ in occurrences}

    # Check for conflicts with validation words or source/target words
    is_safe, conflict_error = check_pattern_conflicts(
        typo_pattern,
        validation_set,
        source_words,
        match_direction,
        indexes.validation_index,
        boundary,
        indexes.source_word_index,
        target_words=target_words,
    )
    if not is_safe:
        return False, conflict_error or "Conflict detected"

    # Check if pattern would incorrectly match other corrections
    is_safe, incorrect_match_error = check_pattern_would_incorrectly_match_other_corrections(
        typo_pattern,
        word_pattern,
        corrections,
        occurrences,
        correction_index=indexes.correction_index,
    )
    if not is_safe:
        return False, incorrect_match_error or "Incorrect match"

    return True, None


def _handle_pattern_rejection(
    typo_pattern: str,
    word_pattern: str,
    boundary: BoundaryType,
    occurrences: list[Correction],
    error_message: str | None,
    is_debug_pattern_flag: bool,
    has_debug_occurrence: bool,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
    rejected_patterns: list[tuple[str, str, BoundaryType, str]],
) -> bool:
    """Handle pattern rejection.

    Args:
        typo_pattern: The typo pattern
        word_pattern: The word pattern
        boundary: The boundary type
        occurrences: List of occurrences
        error_message: Error message for rejection
        is_debug_pattern_flag: Whether this is a debug pattern
        has_debug_occurrence: Whether any occurrence is being debugged
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos
        rejected_patterns: List to append rejected patterns to

    Returns:
        True if pattern should be skipped (rejected), False otherwise
    """
    reason = error_message or "Unknown error"
    if error_message == "Too few occurrences":
        return True  # Skip silently if already filtered
    process_rejected_pattern(
        typo_pattern,
        word_pattern,
        boundary,
        reason,
        occurrences,
        is_debug_pattern_flag,
        has_debug_occurrence,
        debug_words,
        debug_typo_matcher,
        rejected_patterns,
    )
    return True


def _handle_redundant_pattern(
    typo_pattern: str,
    word_pattern: str,
    boundary: BoundaryType,
    occurrences: list[Correction],
    patterns: list[Correction],
    is_debug_pattern_flag: bool,
    has_debug_occurrence: bool,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
    rejected_patterns: list[tuple[str, str, BoundaryType, str]],
) -> bool:
    """Check and handle redundant pattern.

    Args:
        typo_pattern: The typo pattern
        word_pattern: The word pattern
        boundary: The boundary type
        occurrences: List of occurrences
        patterns: List of already-accepted patterns
        is_debug_pattern_flag: Whether this is a debug pattern
        has_debug_occurrence: Whether any occurrence is being debugged
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos
        rejected_patterns: List to append rejected patterns to

    Returns:
        True if pattern is redundant (should be skipped), False otherwise
    """
    is_redundant, redundancy_error, blocking_pattern = check_pattern_redundant_with_other_patterns(
        typo_pattern,
        word_pattern,
        boundary,
        patterns,
    )
    if is_redundant:
        reason = redundancy_error or "Redundant with shorter pattern"
        # Enhanced debug logging for redundancy rejection
        if is_debug_pattern_flag and blocking_pattern:
            blocking_typo, blocking_word, _ = blocking_pattern
            logger.debug(
                f"[PATTERN GENERALIZATION] Pattern '{typo_pattern}' → '{word_pattern}' "
                f"rejected as redundant: shorter pattern '{blocking_typo}' → '{blocking_word}' "
                f"already handles this case"
            )
        process_rejected_pattern(
            typo_pattern,
            word_pattern,
            boundary,
            reason,
            occurrences,
            is_debug_pattern_flag,
            has_debug_occurrence,
            debug_words,
            debug_typo_matcher,
            rejected_patterns,
        )
        return True
    return False


def _run_single_threaded_validation(
    patterns_to_validate: dict[tuple[str, str, BoundaryType], list[Correction]],
    min_typo_length: int,
    validation_set: set[str],
    source_words: set[str],
    match_direction: MatchDirection,
    corrections: list[Correction],
    indexes: ValidationIndexes,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
    verbose: bool,
) -> tuple[
    list[Correction],
    set[Correction],
    dict[Correction, list[Correction]],
    list[tuple[str, str, BoundaryType, str]],
]:
    """Run pattern validation in single-threaded mode.

    Args:
        patterns_to_validate: Dictionary of patterns to validate
        min_typo_length: Minimum typo length
        validation_set: Set of valid words
        source_words: Set of source words
        match_direction: Platform match direction
        corrections: All corrections to check against
        indexes: Validation indexes
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos
        verbose: Whether to print verbose output

    Returns:
        Tuple of (patterns, corrections_to_remove, pattern_replacements, rejected_patterns)
    """
    patterns: list[Correction] = []
    corrections_to_remove: set[Correction] = set()
    pattern_replacements: dict[Correction, list[Correction]] = {}
    rejected_patterns: list[tuple[str, str, BoundaryType, str]] = []

    if verbose:
        patterns_iter: list[tuple[tuple[str, str, BoundaryType], list[Correction]]] = list(
            tqdm(
                patterns_to_validate.items(),
                desc="    Validating patterns",
                unit="pattern",
                leave=False,
            )
        )
    else:
        patterns_iter = list(patterns_to_validate.items())

    _process_patterns_single_threaded(
        patterns_iter,
        min_typo_length,
        validation_set,
        source_words,
        match_direction,
        corrections,
        indexes,
        debug_words,
        debug_typo_matcher,
        patterns,
        pattern_replacements,
        corrections_to_remove,
        rejected_patterns,
    )

    return patterns, corrections_to_remove, pattern_replacements, rejected_patterns


def _process_patterns_single_threaded(
    patterns_iter: list[tuple[tuple[str, str, BoundaryType], list[Correction]]],
    min_typo_length: int,
    validation_set: set[str],
    source_words: set[str],
    match_direction: MatchDirection,
    corrections: list[Correction],
    indexes: ValidationIndexes,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
    patterns: list[Correction],
    pattern_replacements: dict[Correction, list[Correction]],
    corrections_to_remove: set[Correction],
    rejected_patterns: list[tuple[str, str, BoundaryType, str]],
) -> None:
    """Process patterns in single-threaded validation loop.

    Args:
        patterns_iter: Iterator over patterns to validate
        min_typo_length: Minimum typo length
        validation_set: Set of valid words
        source_words: Set of source words
        match_direction: Platform match direction
        corrections: All corrections to check against
        indexes: Validation indexes
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos
        patterns: List to append accepted patterns to
        pattern_replacements: Dict to store pattern replacements
        corrections_to_remove: Set to add corrections to remove to
        rejected_patterns: List to append rejected patterns to
    """
    for (typo_pattern, word_pattern, boundary), occurrences in patterns_iter:
        # Check if any of the occurrences involve debug items (for logging)
        has_debug_occurrence = any(
            is_debug_correction(occ, debug_words, debug_typo_matcher) for occ in occurrences
        )

        # Debug logging for pattern candidates
        is_debug_pattern_flag = is_debug_pattern(typo_pattern, occurrences, debug_typo_matcher)
        # Only log if this pattern wasn't already filtered by graveyard check
        # (patterns_to_validate should already be filtered, but log anyway for debugging)
        log_pattern_candidate(typo_pattern, word_pattern, occurrences, debug_typo_matcher)

        # Validate the pattern
        # pylint: disable=duplicate-code
        # False positive: Similar parameter lists are expected when calling the same function
        # from different contexts (orchestration vs validation runner). This is not duplicate
        # code that should be refactored - it's the same function call with the same parameters.
        is_valid, error_message = _validate_single_pattern_single_threaded(
            typo_pattern,
            word_pattern,
            boundary,
            occurrences,
            min_typo_length,
            validation_set,
            source_words,
            match_direction,
            corrections,
            indexes,
            debug_typo_matcher,
            False,  # verbose not needed in loop
        )

        if not is_valid:
            if _handle_pattern_rejection(
                typo_pattern,
                word_pattern,
                boundary,
                occurrences,
                error_message,
                is_debug_pattern_flag,
                has_debug_occurrence,
                debug_words,
                debug_typo_matcher,
                rejected_patterns,
            ):
                continue

        # Check if pattern is redundant with already-accepted patterns
        if _handle_redundant_pattern(
            typo_pattern,
            word_pattern,
            boundary,
            occurrences,
            patterns,
            is_debug_pattern_flag,
            has_debug_occurrence,
            debug_words,
            debug_typo_matcher,
            rejected_patterns,
        ):
            continue

        # Pattern passed all checks - accept it
        # pylint: disable=duplicate-code
        # False positive: Similar parameter lists are intentional - we pass parameters
        # from processing code to logging functions, which is the correct design pattern
        # for separating processing logic from debug logging.
        process_accepted_pattern(
            typo_pattern,
            word_pattern,
            boundary,
            occurrences,
            has_debug_occurrence,
            debug_words,
            debug_typo_matcher,
            patterns,
            pattern_replacements,
            corrections_to_remove,
        )


def _run_parallel_validation(
    patterns_to_validate: dict[tuple[str, str, BoundaryType], list[Correction]],
    validation_set: set[str],
    source_words: set[str],
    match_direction: MatchDirection,
    min_typo_length: int,
    debug_words: set[str],
    corrections: list[Correction],
    jobs: int,
    verbose: bool,
) -> tuple[
    list[Correction],
    set[Correction],
    dict[Correction, list[Correction]],
    list[tuple[str, str, BoundaryType, str]],
]:
    """Run pattern validation in parallel mode.

    Args:
        patterns_to_validate: Dictionary of patterns to validate
        validation_set: Set of valid words
        source_words: Set of source words
        match_direction: Platform match direction
        min_typo_length: Minimum typo length
        debug_words: Set of words to debug
        corrections: All corrections to check against
        jobs: Number of parallel workers
        verbose: Whether to print verbose output

    Returns:
        Tuple of (patterns, corrections_to_remove, pattern_replacements, rejected_patterns)
    """
    patterns = []
    corrections_to_remove = set()
    pattern_replacements = {}
    rejected_patterns = []

    if verbose:
        logger.info(f"  Using {jobs} parallel workers for pattern validation")

    # Create context for workers
    context = PatternValidationContext(
        validation_set=frozenset(validation_set),
        source_words=frozenset(source_words),
        match_direction=match_direction.value,
        min_typo_length=min_typo_length,
        debug_words=frozenset(debug_words),
        corrections=tuple(corrections),
    )

    if verbose:
        logger.info("  Initializing workers and building indexes...")

    with Pool(
        processes=jobs,
        initializer=init_pattern_validation_worker,
        initargs=(context,),
    ) as pool:
        pattern_items = list(patterns_to_validate.items())
        results_iter = pool.imap_unordered(_validate_single_pattern_worker, pattern_items)

        # Wrap with progress bar if verbose
        if verbose:
            results_wrapped: Any = tqdm(
                results_iter,
                total=len(pattern_items),
                desc="    Validating patterns",
                unit="pattern",
                leave=False,
            )
        else:
            results_wrapped = results_iter

        for (
            is_accepted,
            pattern,
            pattern_corrections_to_remove,
            rejected_pattern,
        ) in results_wrapped:
            if is_accepted and pattern:
                patterns.append(pattern)
                pattern_key = pattern
                pattern_replacements[pattern_key] = pattern_corrections_to_remove
                for correction in pattern_corrections_to_remove:
                    corrections_to_remove.add(correction)
            elif rejected_pattern:
                rejected_patterns.append(rejected_pattern)

    # Post-process to remove redundant patterns (parallel validation can't check during validation)
    return _remove_redundant_patterns_post_process(
        patterns, pattern_replacements, corrections_to_remove, rejected_patterns, debug_words
    )


def _remove_redundant_patterns_post_process(
    patterns: list[Correction],
    pattern_replacements: dict[Correction, list[Correction]],
    corrections_to_remove: set[Correction],
    rejected_patterns: list[tuple[str, str, BoundaryType, str]],
    debug_words: set[str],
) -> tuple[
    list[Correction],
    set[Correction],
    dict[Correction, list[Correction]],
    list[tuple[str, str, BoundaryType, str]],
]:
    """Post-process parallel validation results to remove redundant patterns.

    Args:
        patterns: List of accepted patterns from parallel validation
        pattern_replacements: Dict mapping patterns to their replacement corrections
        corrections_to_remove: Set of corrections to remove
        rejected_patterns: List of rejected patterns
        debug_words: Set of words to debug

    Returns:
        Tuple of (non_redundant_patterns, corrections_to_remove,
        non_redundant_replacements, rejected_patterns)
    """
    # Sort patterns by length (shorter first) to ensure we check shorter patterns first
    patterns_sorted = sorted(patterns, key=lambda p: len(p[0]))
    non_redundant_patterns: list[Correction] = []
    non_redundant_replacements: dict[Correction, list[Correction]] = {}
    debug_typo_matcher = None  # Not available in parallel mode, but needed for logging

    for pattern in patterns_sorted:
        typo_pattern, word_pattern, boundary = pattern
        occurrences = pattern_replacements.get(pattern, [])
        has_debug_occurrence = any(
            is_debug_correction(occ, debug_words, debug_typo_matcher) for occ in occurrences
        )
        is_debug_pattern_flag = is_debug_pattern(typo_pattern, occurrences, debug_typo_matcher)

        # Check if this pattern is redundant with already-accepted patterns
        is_redundant, redundancy_error, blocking_pattern = (
            check_pattern_redundant_with_other_patterns(
                typo_pattern,
                word_pattern,
                boundary,
                non_redundant_patterns,
            )
        )
        if is_redundant:
            reason = redundancy_error or "Redundant with shorter pattern"
            # Enhanced debug logging for redundancy rejection
            if is_debug_pattern_flag and blocking_pattern:
                blocking_typo, blocking_word, _ = blocking_pattern
                logger.debug(
                    f"[PATTERN GENERALIZATION] Pattern '{typo_pattern}' → '{word_pattern}' "
                    f"rejected as redundant: shorter pattern '{blocking_typo}' → '{blocking_word}' "
                    f"already handles this case"
                )
            process_rejected_pattern(
                typo_pattern,
                word_pattern,
                boundary,
                reason,
                occurrences,
                is_debug_pattern_flag,
                has_debug_occurrence,
                debug_words,
                debug_typo_matcher,
                rejected_patterns,
            )
            # Remove corrections that would have been replaced by this redundant pattern
            for correction in occurrences:
                corrections_to_remove.discard(correction)
        else:
            non_redundant_patterns.append(pattern)
            non_redundant_replacements[pattern] = occurrences

    return (
        non_redundant_patterns,
        corrections_to_remove,
        non_redundant_replacements,
        rejected_patterns,
    )
