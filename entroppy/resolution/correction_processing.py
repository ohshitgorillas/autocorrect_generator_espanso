"""Correction processing for single words and collision cases."""

from collections import defaultdict
from typing import TYPE_CHECKING

from entroppy.core import BoundaryType, Correction
from entroppy.core.boundaries import BoundaryIndex
from entroppy.matching import ExclusionMatcher
from entroppy.utils.debug import is_debug_correction, log_debug_typo, log_if_debug_correction
from entroppy.utils.helpers import cached_word_frequency

from .boundary_selection import choose_boundary_for_typo
from .boundary_utils import _should_skip_short_typo, apply_user_word_boundary_override
from .exclusion import handle_exclusion
from .false_trigger_check import _check_false_trigger_with_details

if TYPE_CHECKING:
    from entroppy.utils.debug import DebugTypoMatcher


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


def process_single_word_correction(
    typo: str,
    word: str,
    min_typo_length: int,
    min_word_length: int,
    user_words: set[str],
    exclusion_matcher: ExclusionMatcher,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
    validation_index: BoundaryIndex,
    source_index: BoundaryIndex,
) -> tuple[Correction | None, bool, tuple[str, str, str | None] | None, dict | None]:
    """Process a correction with a single word (no collision).

    Args:
        typo: The typo string
        word: The correct word
        min_typo_length: Minimum typo length
        min_word_length: Minimum word length
        user_words: Set of user-provided words
        exclusion_matcher: Matcher for exclusion rules
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos
        validation_index: Boundary index for validation set
        source_index: Boundary index for source words

    Returns:
        Tuple of (correction, was_skipped_short, excluded_info, boundary_details).
        correction is None if skipped or excluded.
        excluded_info is (typo, word, matching_rule) if excluded, None otherwise.
        boundary_details is dict with boundary selection info for later logging, or None.
    """
    boundary = choose_boundary_for_typo(
        typo,
        validation_index,
        source_index,
        debug_words=debug_words,
        debug_typo_matcher=debug_typo_matcher,
        word=word,
    )

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
    boundary = apply_user_word_boundary_override(
        word, boundary, user_words, debug_words, debug_typo_matcher, typo
    )

    # Check if typo should be skipped due to length
    if _should_skip_short_typo(typo, word, min_typo_length, min_word_length):
        correction_temp = (typo, word, boundary)
        log_if_debug_correction(
            correction_temp,
            f"SKIPPED - typo length {len(typo)} < min_typo_length {min_typo_length} "
            f"(word length {len(word)} > min_word_length {min_word_length})",
            debug_words,
            debug_typo_matcher,
            "Stage 3",
        )
        return None, True, None, boundary_details

    correction = (typo, word, boundary)
    should_exclude, matching_rule = handle_exclusion(
        correction, exclusion_matcher, debug_words, debug_typo_matcher
    )

    if should_exclude:
        return None, False, (typo, word, matching_rule), boundary_details

    # Debug logging for accepted correction
    log_if_debug_correction(
        correction,
        f"Selected (no collision, boundary: {boundary.value})",
        debug_words,
        debug_typo_matcher,
        "Stage 3",
    )

    return correction, False, None, boundary_details


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

    # Apply checks
    if _should_skip_short_typo(typo, word, min_typo_length, min_word_length):
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


def _resolve_collision_by_frequency(
    words_in_group: list[str],
    freq_ratio: float,
) -> tuple[str | None, float]:
    """Resolve collision by frequency analysis.

    Args:
        words_in_group: List of words in collision
        freq_ratio: Minimum frequency ratio for resolution

    Returns:
        Tuple of (selected_word, ratio). selected_word is None if ambiguous.
    """
    word_freqs = [(w, cached_word_frequency(w, "en")) for w in words_in_group]
    word_freqs.sort(key=lambda x: x[1], reverse=True)

    most_common = word_freqs[0]
    second_most = word_freqs[1] if len(word_freqs) > 1 else (None, 0)
    ratio = most_common[1] / second_most[1] if second_most[1] > 0 else float("inf")

    if ratio > freq_ratio:
        return most_common[0], ratio
    return None, ratio


def _log_collision_debug(
    typo: str,
    words_in_group: list[str],
    boundary: BoundaryType,
    ratio: float,
    freq_ratio: float,
    is_resolved: bool,
    debug_typo_matcher: "DebugTypoMatcher | None",
) -> None:
    """Log debug information for collision resolution.

    Args:
        typo: The typo string
        words_in_group: List of words in collision
        boundary: The boundary type
        ratio: Frequency ratio
        freq_ratio: Minimum frequency ratio threshold
        is_resolved: Whether collision was resolved
        debug_typo_matcher: Matcher for debug typos
    """
    word_freqs = [(w, cached_word_frequency(w, "en")) for w in words_in_group]
    words_with_freqs = ", ".join([f"{w} (freq: {f:.2e})" for w, f in word_freqs])
    matched_patterns = (
        debug_typo_matcher.get_matching_patterns(typo, boundary) if debug_typo_matcher else None
    )

    if is_resolved:
        log_debug_typo(
            typo,
            f"Collision for boundary {boundary.value}: {typo} → [{words_with_freqs}] "
            f"(ratio: {ratio:.2f})",
            matched_patterns,
            "Stage 3",
        )
    else:
        log_debug_typo(
            typo,
            f"SKIPPED - ambiguous collision for boundary {boundary.value}: "
            f"{words_in_group}, ratio {ratio:.2f} <= threshold {freq_ratio}",
            matched_patterns,
            "Stage 3",
        )


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
        )

    if selected_word is not None:
        # Can resolve collision for this boundary
        word = selected_word

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

        if _should_skip_short_typo(typo, word, min_typo_length, min_word_length):
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
            typo, words_in_group, boundary, ratio, freq_ratio, False, debug_typo_matcher
        )
    return None, None, (typo, words_in_group, ratio, boundary), None


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
        boundary = choose_boundary_for_typo(
            typo,
            validation_index,
            source_index,
            debug_words=debug_words,
            debug_typo_matcher=debug_typo_matcher,
            word=word,  # CRITICAL: Pass target word!
        )
        word_boundary_map[word] = boundary

    by_boundary = defaultdict(list)
    for word, boundary in word_boundary_map.items():
        by_boundary[boundary].append(word)
    return by_boundary


def _log_initial_collision(
    typo: str,
    unique_words: list[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
) -> None:
    """Log initial collision detection for debugging.

    Args:
        typo: The typo string
        unique_words: List of unique words competing for this typo
        debug_typo_matcher: Matcher for debug typos
    """
    word_freqs = [(w, cached_word_frequency(w, "en")) for w in unique_words]
    words_with_freqs = ", ".join([f"{w} (freq: {f:.2e})" for w, f in word_freqs])
    matched_patterns = (
        debug_typo_matcher.get_matching_patterns(typo, BoundaryType.NONE)
        if debug_typo_matcher
        else None
    )
    log_debug_typo(
        typo,
        f"Collision detected: {typo} → [{words_with_freqs}]",
        matched_patterns,
        "Stage 3",
    )


def process_collision_case(
    typo: str,
    unique_words: list[str],
    freq_ratio: float,
    min_typo_length: int,
    min_word_length: int,
    user_words: set[str],
    exclusion_matcher: ExclusionMatcher,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
    validation_index: BoundaryIndex,
    source_index: BoundaryIndex,
) -> tuple[
    list[Correction],
    list[tuple[str, str, str | None]],
    list[tuple[str, list[str], float, BoundaryType]],
    list[dict],
]:
    """Process a collision case where multiple words compete for the same typo.

    Now determines boundaries for each word FIRST, then groups by boundary before
    applying frequency resolution. This allows "nto" with BOTH → "not" to coexist
    with "nto" with other boundaries → other words.

    Args:
        typo: The typo string
        unique_words: List of unique words competing for this typo
        freq_ratio: Minimum frequency ratio for collision resolution
        min_typo_length: Minimum typo length
        min_word_length: Minimum word length
        user_words: Set of user-provided words
        exclusion_matcher: Matcher for exclusion rules
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos
        validation_index: Boundary index for validation set
        source_index: Boundary index for source words

    Returns:
        Tuple of (corrections_list, excluded_list, skipped_collisions_list, boundary_details_list).
        corrections_list: List of accepted corrections (one per valid boundary group)
        excluded_list: List of (typo, word, matching_rule) for excluded corrections
        skipped_collisions_list: List of (typo, words_in_group, ratio, boundary)
            for ambiguous collisions
        boundary_details_list: List of boundary details dicts for later logging
    """
    # Check if any of the competing words are being debugged
    is_debug_collision = any(
        is_debug_correction((typo, w, BoundaryType.NONE), debug_words, debug_typo_matcher)
        for w in unique_words
    )

    if is_debug_collision:
        _log_initial_collision(typo, unique_words, debug_typo_matcher)

    # Group words by boundary type
    by_boundary = _group_words_by_boundary(
        typo, unique_words, validation_index, source_index, debug_words, debug_typo_matcher
    )

    # Process each boundary group separately
    return _process_boundary_groups(
        typo,
        by_boundary,
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
