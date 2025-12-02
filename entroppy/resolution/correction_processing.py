"""Correction processing for single words and collision cases."""

from typing import TYPE_CHECKING

from entroppy.core import BoundaryType, Correction
from entroppy.core.boundaries import BoundaryIndex
from entroppy.matching import ExclusionMatcher
from entroppy.utils.debug import (
    is_debug_correction,
    log_debug_correction,
    log_debug_typo,
    log_if_debug_correction,
)
from entroppy.utils.helpers import cached_word_frequency


from .boundary_selection import _would_cause_false_trigger, choose_boundary_for_typo
from .boundary_utils import _should_skip_short_typo, apply_user_word_boundary_override
from .exclusion import handle_exclusion

if TYPE_CHECKING:
    from entroppy.utils.debug import DebugTypoMatcher


def _collect_boundary_details(
    typo: str,
    word: str,
    boundary: BoundaryType,
    validation_set: set[str],
    source_words: set[str],
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
        validation_set: Set of validation words
        source_words: Set of source words
        validation_index: Boundary index for validation set
        source_index: Boundary index for source words

    Returns:
        Dictionary with boundary details, or None if details shouldn't be collected
    """
    _, details = _would_cause_false_trigger(
        typo,
        boundary,
        validation_set,
        source_words,
        validation_index,
        source_index,
        target_word=word,
        return_details=True,
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
    validation_set: set[str],
    source_words: set[str],
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
        validation_set: Set of validation words
        source_words: Set of source words
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
        validation_set,
        source_words,
        validation_index,
        source_index,
        debug_words=debug_words,
        debug_typo_matcher=debug_typo_matcher,
        word=word,
    )

    # Collect boundary details for later logging (only if debug_typo_matcher is None, i.e., in worker)
    boundary_details = None
    if not debug_typo_matcher:
        boundary_details = _collect_boundary_details(
            typo,
            word,
            boundary,
            validation_set,
            source_words,
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
    validation_set: set[str],
    source_words: set[str],
    freq_ratio: float,
    min_typo_length: int,
    min_word_length: int,
    user_words: set[str],
    exclusion_matcher: ExclusionMatcher,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
    validation_index: BoundaryIndex,
    source_index: BoundaryIndex,
) -> tuple[Correction | None, bool, tuple[str, str, str | None] | None, float, dict | None]:
    """Process a collision case where multiple words compete for the same typo.

    Args:
        typo: The typo string
        unique_words: List of unique words competing for this typo
        validation_set: Set of validation words
        source_words: Set of source words
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
        Tuple of (correction, was_skipped_short, excluded_info, ratio).
        correction is None if skipped, excluded, or ambiguous.
        excluded_info is (typo, word, matching_rule) if excluded, None otherwise.
        ratio is the frequency ratio between most common and second most common word.
    """
    # Calculate word frequencies
    word_freqs = [(w, cached_word_frequency(w, "en")) for w in unique_words]
    word_freqs.sort(key=lambda x: x[1], reverse=True)

    most_common = word_freqs[0]
    second_most = word_freqs[1] if len(word_freqs) > 1 else (None, 0)

    ratio = most_common[1] / second_most[1] if second_most[1] > 0 else float("inf")

    # Check if any of the competing words are being debugged
    is_debug_collision = any(
        is_debug_correction((typo, w, BoundaryType.NONE), debug_words, debug_typo_matcher)
        for w in unique_words
    )

    if is_debug_collision:
        # Log collision details
        words_with_freqs = ", ".join([f"{w} (freq: {f:.2e})" for w, f in word_freqs])
        matched_patterns = (
            debug_typo_matcher.get_matching_patterns(typo, BoundaryType.NONE)
            if debug_typo_matcher
            else None
        )
        log_debug_typo(
            typo,
            f"Collision detected: {typo} → [{words_with_freqs}] (ratio: {ratio:.2f})",
            matched_patterns,
            "Stage 3",
        )

    # Check if ratio is sufficient to resolve collision
    if ratio <= freq_ratio:
        if is_debug_collision:
            matched_patterns = (
                debug_typo_matcher.get_matching_patterns(typo, BoundaryType.NONE)
                if debug_typo_matcher
                else None
            )
            log_debug_typo(
                typo,
                f"SKIPPED - ambiguous collision, ratio {ratio:.2f} <= threshold {freq_ratio}",
                matched_patterns,
                "Stage 3",
            )
        return None, False, None, ratio, None

    # Resolve collision: use most common word
    word = most_common[0]
    boundary = choose_boundary_for_typo(
        typo,
        validation_set,
        source_words,
        validation_index,
        source_index,
        debug_words=debug_words,
        debug_typo_matcher=debug_typo_matcher,
        word=word,
    )

    # Collect boundary details for later logging (only if debug_typo_matcher is None, i.e., in worker)
    boundary_details = None
    if not debug_typo_matcher:
        boundary_details = _collect_boundary_details(
            typo,
            word,
            boundary,
            validation_set,
            source_words,
            validation_index,
            source_index,
        )

    if is_debug_collision:
        log_debug_correction(
            (typo, word, boundary),
            f"Selected '{word}' (freq: {most_common[1]:.2e}) over '{second_most[0]}' "
            f"(freq: {second_most[1]:.2e}), ratio: {ratio:.2f} > threshold {freq_ratio}",
            debug_words,
            debug_typo_matcher,
            "Stage 3",
        )

    boundary = apply_user_word_boundary_override(
        word, boundary, user_words, debug_words, debug_typo_matcher, typo
    )

    # Check if typo should be skipped due to length
    if _should_skip_short_typo(typo, word, min_typo_length, min_word_length):
        correction_temp = (typo, word, boundary)
        log_if_debug_correction(
            correction_temp,
            f"SKIPPED after collision resolution - typo length {len(typo)} < min_typo_length {min_typo_length}",
            debug_words,
            debug_typo_matcher,
            "Stage 3",
        )
        return None, True, None, ratio, boundary_details

    correction = (typo, word, boundary)
    should_exclude, matching_rule = handle_exclusion(
        correction, exclusion_matcher, debug_words, debug_typo_matcher
    )

    if should_exclude:
        return None, False, (typo, word, matching_rule), ratio, boundary_details

    return correction, False, None, ratio, boundary_details
