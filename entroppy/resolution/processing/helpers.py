"""Helper functions for correction processing."""

from collections import defaultdict
from typing import TYPE_CHECKING

from entroppy.core import BoundaryType, Correction
from entroppy.core.boundaries import BoundaryIndex
from entroppy.matching import ExclusionMatcher
from entroppy.resolution.boundaries.selection import choose_boundary_for_typo
from entroppy.resolution.boundaries.utils import (
    _should_skip_short_typo,
    apply_user_word_boundary_override,
)
from entroppy.resolution.exclusion import handle_exclusion
from entroppy.resolution.false_trigger_check import _check_false_trigger_with_details
from entroppy.utils.debug import is_debug_correction, log_if_debug_correction

from .collision_helpers import (
    _log_collision_debug,
    _resolve_collision_by_frequency,
)

if TYPE_CHECKING:
    from entroppy.utils.debug import DebugTypoMatcher


def _prepare_boundary_and_collect_details(
    typo: str,
    word: str,
    boundary: BoundaryType,
    min_typo_length: int,
    min_word_length: int,
    user_words: set[str],
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
    validation_index: BoundaryIndex,
    source_index: BoundaryIndex,
) -> tuple[BoundaryType, dict | None, bool]:
    """Prepare boundary (apply overrides) and collect details, check if should skip.

    This helper function centralizes the common pattern of:
    1. Collecting boundary details (if not in debug mode)
    2. Applying user word boundary override
    3. Checking if typo should be skipped due to length

    Args:
        typo: The typo string
        word: The correct word
        boundary: The initial boundary type
        min_typo_length: Minimum typo length
        min_word_length: Minimum word length
        user_words: Set of user-provided words
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos
        validation_index: Boundary index for validation set
        source_index: Boundary index for source words

    Returns:
        Tuple of (boundary, boundary_details, should_skip).
        boundary is the potentially overridden boundary.
        boundary_details is dict with boundary selection info for later logging, or None.
        should_skip is True if typo should be skipped due to length.
    """
    # Collect boundary details for later logging
    # (only if debug_typo_matcher is None, i.e., in worker)
    boundary_details = None
    if not debug_typo_matcher:
        boundary_details = _collect_boundary_details(
            typo,
            word,
            boundary,
            validation_index,
            source_index,
        )

    # Apply user word boundary override
    boundary = apply_user_word_boundary_override(
        word, boundary, user_words, debug_words, debug_typo_matcher, typo
    )

    # Check if typo should be skipped due to length
    should_skip = _should_skip_short_typo(typo, word, min_typo_length, min_word_length)

    return boundary, boundary_details, should_skip


def _collect_boundary_details(
    typo: str,
    word: str,
    boundary: BoundaryType,
    validation_index: BoundaryIndex,
    source_index: BoundaryIndex,
) -> dict | None:
    """Collect boundary selection details for later logging.

    This reduces code duplication by centralizing the boundary details collection
    logic used in both single-word and collision case processing.

    Args:
        typo: The typo string
        word: The correct word
        boundary: The selected boundary type
        validation_index: Boundary index for validation set
        source_index: Boundary index for source words

    Returns:
        Dictionary with boundary details, or None if details shouldn't be collected
    """
    # pylint: disable=duplicate-code
    # Common logic extracted to _check_false_trigger_with_details().
    # This call pattern appears in boundary_selection.py as well, which is acceptable.
    _, details = _check_false_trigger_with_details(
        typo,
        boundary,
        validation_index,
        source_index,
        target_word=word,
    )
    return {
        "typo": typo,
        "word": word,
        "boundary": boundary.value,
        "details": details,
    }


def _group_words_by_boundary(
    typo: str,
    unique_words: list[str],
    validation_index: BoundaryIndex,
    source_index: BoundaryIndex,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
) -> dict[BoundaryType, list[str]]:
    """Group words by their determined boundary type.

    Args:
        typo: The typo string
        unique_words: List of unique words competing for this typo
        validation_index: Boundary index for validation set
        source_index: Boundary index for source words
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos

    Returns:
        Dictionary mapping boundary type to list of words with that boundary
    """
    word_boundary_map = {}
    for word in unique_words:
        # pylint: disable=duplicate-code
        # Acceptable pattern: This is a function call to choose_boundary_for_typo
        # with standard parameters. The similar code in correction_processor.py calls
        # the same function with the same parameters. This is expected when both places
        # need to determine boundaries for words.
        boundary = choose_boundary_for_typo(
            typo,
            validation_index,
            source_index,
            debug_words=debug_words,
            debug_typo_matcher=debug_typo_matcher,
            word=word,  # CRITICAL: Pass target word!
            debug_messages=None,  # debug_messages - not available in this context
        )
        word_boundary_map[word] = boundary

    by_boundary = defaultdict(list)
    for word, boundary in word_boundary_map.items():
        by_boundary[boundary].append(word)
    return by_boundary


def _process_single_word_boundary_group(
    typo: str,
    word: str,
    boundary: BoundaryType,
    min_typo_length: int,
    min_word_length: int,
    user_words: set[str],
    exclusion_matcher: ExclusionMatcher,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
    validation_index: BoundaryIndex,
    source_index: BoundaryIndex,
) -> tuple[
    Correction | None,
    tuple[str, str, str | None] | None,
    dict | None,
]:
    """Process a single word in a boundary group (no collision within group).

    Args:
        typo: The typo string
        word: The word to process
        boundary: The boundary type for this group
        min_typo_length: Minimum typo length
        min_word_length: Minimum word length
        user_words: Set of user-provided words
        exclusion_matcher: Matcher for exclusion rules
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos
        validation_index: Boundary index for validation set
        source_index: Boundary index for source words

    Returns:
        Tuple of (correction, excluded_info, boundary_details).
        correction is None if skipped or excluded.
        excluded_info is (typo, word, matching_rule) if excluded, None otherwise.
        boundary_details is dict with boundary selection info for later logging, or None.
    """
    # pylint: disable=duplicate-code
    # False positive: This is a call to the shared _prepare_boundary_and_collect_details
    # function. The similar code in correction_processor.py is the same function call,
    # which is expected and not actual duplicate code.
    boundary, boundary_details, should_skip = _prepare_boundary_and_collect_details(
        typo,
        word,
        boundary,
        min_typo_length,
        min_word_length,
        user_words,
        debug_words,
        debug_typo_matcher,
        validation_index,
        source_index,
    )

    if should_skip:
        return None, None, boundary_details

    correction = (typo, word, boundary)
    should_exclude, matching_rule = handle_exclusion(
        correction, exclusion_matcher, debug_words, debug_typo_matcher
    )

    if should_exclude:
        return None, (typo, word, matching_rule), boundary_details

    log_if_debug_correction(
        correction,
        f"Selected (no collision for boundary {boundary.value})",
        debug_words,
        debug_typo_matcher,
        "Stage 3",
    )
    return correction, None, boundary_details


def _process_collision_boundary_group(
    typo: str,
    words_in_group: list[str],
    boundary: BoundaryType,
    freq_ratio: float,
    min_typo_length: int,
    min_word_length: int,
    user_words: set[str],
    exclusion_matcher: ExclusionMatcher,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
    validation_index: BoundaryIndex,
    source_index: BoundaryIndex,
    is_debug_collision: bool,
) -> tuple[
    Correction | None,
    tuple[str, str, str | None] | None,
    tuple[str, list[str], float, BoundaryType] | None,
    dict | None,
]:
    """Process a boundary group with multiple words (collision within group).

    Args:
        typo: The typo string
        words_in_group: List of words in this boundary group
        boundary: The boundary type for this group
        freq_ratio: Minimum frequency ratio for collision resolution
        min_typo_length: Minimum typo length
        min_word_length: Minimum word length
        user_words: Set of user-provided words
        exclusion_matcher: Matcher for exclusion rules
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos
        validation_index: Boundary index for validation set
        source_index: Boundary index for source words
        is_debug_collision: Whether this collision is being debugged

    Returns:
        Tuple of (correction, excluded_info, skipped_collision, boundary_details).
        correction is None if skipped, excluded, or ambiguous.
        excluded_info is (typo, word, matching_rule) if excluded, None otherwise.
        skipped_collision is (typo, words_in_group, ratio, boundary) if ambiguous, None otherwise.
        boundary_details is dict with boundary selection info for later logging, or None.
    """
    # Resolve collision by frequency
    selected_word, ratio = _resolve_collision_by_frequency(words_in_group, freq_ratio)

    if is_debug_collision:
        _log_collision_debug(
            typo,
            words_in_group,
            boundary,
            ratio,
            freq_ratio,
            selected_word is not None,
            debug_typo_matcher,
            None,  # debug_messages - not available in this context
        )

    if selected_word is not None:
        # Can resolve collision for this boundary
        word = selected_word

        # pylint: disable=duplicate-code
        # False positive: This is a call to the shared _prepare_boundary_and_collect_details
        # function. The similar code in correction_processor.py and elsewhere is the same
        # function call, which is expected and not actual duplicate code.
        boundary, boundary_details, should_skip = _prepare_boundary_and_collect_details(
            typo,
            word,
            boundary,
            min_typo_length,
            min_word_length,
            user_words,
            debug_words,
            debug_typo_matcher,
            validation_index,
            source_index,
        )

        if should_skip:
            return None, None, None, boundary_details

        correction = (typo, word, boundary)
        should_exclude, matching_rule = handle_exclusion(
            correction, exclusion_matcher, debug_words, debug_typo_matcher
        )

        if should_exclude:
            return None, (typo, word, matching_rule), None, boundary_details

        log_if_debug_correction(
            correction,
            f"Selected '{word}' over {words_in_group[1:]} "
            f"(boundary {boundary.value}, ratio: {ratio:.2f})",
            debug_words,
            debug_typo_matcher,
            "Stage 3",
        )
        return correction, None, None, boundary_details

    # Ambiguous collision for this boundary only
    is_debug = any(
        is_debug_correction((typo, w, boundary), debug_words, debug_typo_matcher)
        for w in words_in_group
    )
    if is_debug:
        _log_collision_debug(
            typo,
            words_in_group,
            boundary,
            ratio,
            freq_ratio,
            False,
            debug_typo_matcher,
            None,  # debug_messages - not available in this context
        )
    return None, None, (typo, words_in_group, ratio, boundary), None


def _process_boundary_groups(
    typo: str,
    by_boundary: dict[BoundaryType, list[str]],
    freq_ratio: float,
    min_typo_length: int,
    min_word_length: int,
    user_words: set[str],
    exclusion_matcher: ExclusionMatcher,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
    validation_index: BoundaryIndex,
    source_index: BoundaryIndex,
    is_debug_collision: bool,
) -> tuple[
    list[Correction],
    list[tuple[str, str, str | None]],
    list[tuple[str, list[str], float, BoundaryType]],
    list[dict],
]:
    """Process boundary groups for collision case.

    Args:
        typo: The typo string
        by_boundary: Dictionary mapping boundary type to list of words
        freq_ratio: Minimum frequency ratio for collision resolution
        min_typo_length: Minimum typo length
        min_word_length: Minimum word length
        user_words: Set of user-provided words
        exclusion_matcher: Matcher for exclusion rules
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos
        validation_index: Boundary index for validation set
        source_index: Boundary index for source words
        is_debug_collision: Whether this collision is being debugged

    Returns:
        Tuple of (corrections_list, excluded_list, skipped_collisions_list, boundary_details_list)
    """
    all_corrections = []
    all_excluded = []
    all_skipped = []
    all_boundary_details = []

    for boundary, words_in_group in by_boundary.items():
        if len(words_in_group) == 1:
            # No collision for this boundary - single word
            word = words_in_group[0]
            # pylint: disable=duplicate-code
            # False positive: Similar parameter lists are expected when calling helper functions
            # with the same context parameters. This is not duplicate code that should be refactored
            # - it's the same function call with the same parameters from different call sites.
            correction, excluded_info, boundary_details = _process_single_word_boundary_group(
                typo,
                word,
                boundary,
                min_typo_length,
                min_word_length,
                user_words,
                exclusion_matcher,
                debug_words,
                debug_typo_matcher,
                validation_index,
                source_index,
            )
            if boundary_details:
                all_boundary_details.append(boundary_details)
            if excluded_info:
                all_excluded.append(excluded_info)
            elif correction:
                all_corrections.append(correction)
        else:
            # Collision within this boundary group
            # pylint: disable=duplicate-code
            # False positive: Similar parameter lists are expected when calling helper functions
            # with the same context parameters. This is not duplicate code that should be refactored
            # - it's the same function call with the same parameters from different call sites.
            correction, excluded_info, skipped_collision, boundary_details = (
                _process_collision_boundary_group(
                    typo,
                    words_in_group,
                    boundary,
                    freq_ratio,
                    min_typo_length,
                    min_word_length,
                    user_words,
                    exclusion_matcher,
                    debug_words,
                    debug_typo_matcher,
                    validation_index,
                    source_index,
                    is_debug_collision,
                )
            )
            if boundary_details:
                all_boundary_details.append(boundary_details)
            if excluded_info:
                all_excluded.append(excluded_info)
            elif skipped_collision:
                all_skipped.append(skipped_collision)
            elif correction:
                all_corrections.append(correction)

    return all_corrections, all_excluded, all_skipped, all_boundary_details
