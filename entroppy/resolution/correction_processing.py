"""Correction processing for single words and collision cases."""

from collections import defaultdict
from typing import TYPE_CHECKING

from entroppy.core import BoundaryType, Correction
from entroppy.core.boundaries import BoundaryIndex
from entroppy.matching import ExclusionMatcher
from entroppy.utils.debug import (
    is_debug_correction,
    log_debug_typo,
    log_if_debug_correction,
)
from entroppy.utils.helpers import cached_word_frequency


from .boundary_selection import (
    _check_false_trigger_with_details,
    choose_boundary_for_typo,
)
from .boundary_utils import _should_skip_short_typo, apply_user_word_boundary_override
from .exclusion import handle_exclusion

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
        # Log initial collision detection
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

    # Step 1: Determine boundary for each competing word
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

    # Step 2: Group words by boundary type
    by_boundary = defaultdict(list)
    for word, boundary in word_boundary_map.items():
        by_boundary[boundary].append(word)

    # Step 3: Process each boundary group separately
    all_corrections = []
    all_excluded = []
    all_skipped = []
    all_boundary_details = []

    for boundary, words_in_group in by_boundary.items():
        if len(words_in_group) == 1:
            # No collision for this boundary - single word
            word = words_in_group[0]

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
                if boundary_details:
                    all_boundary_details.append(boundary_details)

            # Apply user word boundary override
            boundary = apply_user_word_boundary_override(
                word, boundary, user_words, debug_words, debug_typo_matcher, typo
            )

            # Apply checks
            if _should_skip_short_typo(typo, word, min_typo_length, min_word_length):
                continue

            correction = (typo, word, boundary)
            should_exclude, matching_rule = handle_exclusion(
                correction, exclusion_matcher, debug_words, debug_typo_matcher
            )

            if should_exclude:
                all_excluded.append((typo, word, matching_rule))
            else:
                all_corrections.append(correction)
                log_if_debug_correction(
                    correction,
                    f"Selected (no collision for boundary {boundary.value})",
                    debug_words,
                    debug_typo_matcher,
                    "Stage 3",
                )
        else:
            # Collision within this boundary group - resolve by frequency
            word_freqs = [(w, cached_word_frequency(w, "en")) for w in words_in_group]
            word_freqs.sort(key=lambda x: x[1], reverse=True)

            most_common = word_freqs[0]
            second_most = word_freqs[1] if len(word_freqs) > 1 else (None, 0)
            ratio = most_common[1] / second_most[1] if second_most[1] > 0 else float("inf")

            if is_debug_collision:
                words_with_freqs = ", ".join([f"{w} (freq: {f:.2e})" for w, f in word_freqs])
                matched_patterns = (
                    debug_typo_matcher.get_matching_patterns(typo, boundary)
                    if debug_typo_matcher
                    else None
                )
                log_debug_typo(
                    typo,
                    f"Collision for boundary {boundary.value}: {typo} → [{words_with_freqs}] "
                    f"(ratio: {ratio:.2f})",
                    matched_patterns,
                    "Stage 3",
                )

            if ratio > freq_ratio:
                # Can resolve collision for this boundary
                word = most_common[0]

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
                    if boundary_details:
                        all_boundary_details.append(boundary_details)

                # Apply user word boundary override
                boundary = apply_user_word_boundary_override(
                    word, boundary, user_words, debug_words, debug_typo_matcher, typo
                )

                if _should_skip_short_typo(typo, word, min_typo_length, min_word_length):
                    continue

                correction = (typo, word, boundary)
                should_exclude, matching_rule = handle_exclusion(
                    correction, exclusion_matcher, debug_words, debug_typo_matcher
                )

                if should_exclude:
                    all_excluded.append((typo, word, matching_rule))
                else:
                    all_corrections.append(correction)
                    log_if_debug_correction(
                        correction,
                        f"Selected '{word}' over {words_in_group[1:]} "
                        f"(boundary {boundary.value}, ratio: {ratio:.2f})",
                        debug_words,
                        debug_typo_matcher,
                        "Stage 3",
                    )
            else:
                # Ambiguous collision for this boundary only
                all_skipped.append((typo, words_in_group, ratio, boundary))

                is_debug = any(
                    is_debug_correction((typo, w, boundary), debug_words, debug_typo_matcher)
                    for w in words_in_group
                )
                if is_debug:
                    matched_patterns = (
                        debug_typo_matcher.get_matching_patterns(typo, boundary)
                        if debug_typo_matcher
                        else None
                    )
                    log_debug_typo(
                        typo,
                        f"SKIPPED - ambiguous collision for boundary {boundary.value}: "
                        f"{words_in_group}, ratio {ratio:.2f} <= threshold {freq_ratio}",
                        matched_patterns,
                        "Stage 3",
                    )

    return all_corrections, all_excluded, all_skipped, all_boundary_details
