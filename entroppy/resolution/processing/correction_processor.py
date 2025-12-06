"""Correction processing for single words and collision cases."""

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
from entroppy.utils.debug import is_debug_correction, log_if_debug_correction

from .helpers import (
    _collect_boundary_details,
    _group_words_by_boundary,
    _log_initial_collision,
    _process_boundary_groups,
)

if TYPE_CHECKING:
    from entroppy.utils.debug import DebugTypoMatcher


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
        typo,
        unique_words,
        validation_index,
        source_index,
        debug_words,
        debug_typo_matcher,
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
