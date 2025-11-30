"""Collision resolution for typo corrections."""

from typing import TYPE_CHECKING

from tqdm import tqdm
from wordfreq import word_frequency

from entroppy.core import BoundaryType, Correction
from entroppy.matching import ExclusionMatcher
from entroppy.utils import is_debug_correction, log_debug_correction, log_debug_typo
from entroppy.resolution.conflicts import resolve_conflicts_for_group
from entroppy.resolution.boundary_utils import (
    _should_skip_short_typo,
    apply_user_word_boundary_override,
    choose_strictest_boundary,
)

if TYPE_CHECKING:
    from entroppy.utils import DebugTypoMatcher


def _handle_exclusion(
    correction: Correction,
    exclusion_matcher: ExclusionMatcher,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
) -> tuple[bool, str | None]:
    """Check if a correction should be excluded and log if needed.

    Args:
        correction: The correction to check
        exclusion_matcher: Matcher for exclusion rules
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos

    Returns:
        Tuple of (should_exclude, matching_rule). matching_rule is None if not excluded.
    """
    if exclusion_matcher.should_exclude(correction):
        matching_rule = exclusion_matcher.get_matching_rule(correction)
        if is_debug_correction(correction, debug_words, debug_typo_matcher):
            log_debug_correction(
                correction,
                f"EXCLUDED by rule: {matching_rule}",
                debug_words,
                debug_typo_matcher,
                "Stage 3",
            )
        return True, matching_rule
    return False, None


def _process_single_word_correction(
    typo: str,
    word: str,
    boundaries: list[BoundaryType],
    min_typo_length: int,
    min_word_length: int,
    user_words: set[str],
    exclusion_matcher: ExclusionMatcher,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
) -> tuple[Correction | None, bool, tuple[str, str, str | None] | None]:
    """Process a correction with a single word (no collision).

    Args:
        typo: The typo string
        word: The correct word
        boundaries: List of boundary types for this word
        min_typo_length: Minimum typo length
        min_word_length: Minimum word length
        user_words: Set of user-provided words
        exclusion_matcher: Matcher for exclusion rules
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos

    Returns:
        Tuple of (correction, was_skipped_short, excluded_info).
        correction is None if skipped or excluded.
        excluded_info is (typo, word, matching_rule) if excluded, None otherwise.
    """
    boundary = choose_strictest_boundary(boundaries)
    boundary = apply_user_word_boundary_override(
        word, boundary, user_words, debug_words, debug_typo_matcher, typo
    )

    # Check if typo should be skipped due to length
    if _should_skip_short_typo(typo, word, min_typo_length, min_word_length):
        correction_temp = (typo, word, boundary)
        if is_debug_correction(correction_temp, debug_words, debug_typo_matcher):
            log_debug_correction(
                correction_temp,
                f"SKIPPED - typo length {len(typo)} < min_typo_length {min_typo_length} "
                f"(word length {len(word)} > min_word_length {min_word_length})",
                debug_words,
                debug_typo_matcher,
                "Stage 3",
            )
        return None, True, None

    correction = (typo, word, boundary)
    should_exclude, matching_rule = _handle_exclusion(
        correction, exclusion_matcher, debug_words, debug_typo_matcher
    )

    if should_exclude:
        return None, False, (typo, word, matching_rule)

    # Debug logging for accepted correction
    if is_debug_correction(correction, debug_words, debug_typo_matcher):
        log_debug_correction(
            correction,
            f"Selected (no collision, boundary: {boundary.value})",
            debug_words,
            debug_typo_matcher,
            "Stage 3",
        )

    return correction, False, None


def _process_collision_case(
    typo: str,
    unique_words: list[str],
    unique_pairs: list[tuple[str, BoundaryType]],
    freq_ratio: float,
    min_typo_length: int,
    min_word_length: int,
    user_words: set[str],
    exclusion_matcher: ExclusionMatcher,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
) -> tuple[Correction | None, bool, tuple[str, str, str | None] | None, float]:
    """Process a collision case where multiple words compete for the same typo.

    Args:
        typo: The typo string
        unique_words: List of unique words competing for this typo
        unique_pairs: List of (word, boundary) pairs
        freq_ratio: Minimum frequency ratio for collision resolution
        min_typo_length: Minimum typo length
        min_word_length: Minimum word length
        user_words: Set of user-provided words
        exclusion_matcher: Matcher for exclusion rules
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos

    Returns:
        Tuple of (correction, was_skipped_short, excluded_info, ratio).
        correction is None if skipped, excluded, or ambiguous.
        excluded_info is (typo, word, matching_rule) if excluded, None otherwise.
        ratio is the frequency ratio between most common and second most common word.
    """
    # Calculate word frequencies
    word_freqs = [(w, word_frequency(w, "en")) for w in unique_words]
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
        log_debug_typo(
            typo,
            f"Collision detected: {typo} → [{words_with_freqs}] (ratio: {ratio:.2f})",
            [],
            "Stage 3",
        )

    # Check if ratio is sufficient to resolve collision
    if ratio <= freq_ratio:
        if is_debug_collision:
            log_debug_typo(
                typo,
                f"SKIPPED - ambiguous collision, ratio {ratio:.2f} <= threshold {freq_ratio}",
                [],
                "Stage 3",
            )
        return None, False, None, ratio

    # Resolve collision: use most common word
    word = most_common[0]
    boundaries = [b for w, b in unique_pairs if w == word]
    boundary = choose_strictest_boundary(boundaries)

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
        if is_debug_correction(correction_temp, debug_words, debug_typo_matcher):
            log_debug_correction(
                correction_temp,
                f"SKIPPED after collision resolution - typo length {len(typo)} < min_typo_length {min_typo_length}",
                debug_words,
                debug_typo_matcher,
                "Stage 3",
            )
        return None, True, None, ratio

    correction = (typo, word, boundary)
    should_exclude, matching_rule = _handle_exclusion(
        correction, exclusion_matcher, debug_words, debug_typo_matcher
    )

    if should_exclude:
        return None, False, (typo, word, matching_rule), ratio

    return correction, False, None, ratio


def resolve_collisions(
    typo_map: dict[str, list[tuple[str, BoundaryType]]],
    freq_ratio: float,
    min_typo_length: int,
    min_word_length: int,
    user_words: set[str],
    exclusion_matcher: ExclusionMatcher,
    debug_words: set[str] | None = None,
    debug_typo_matcher: "DebugTypoMatcher | None" = None,
) -> tuple[list[Correction], list, list, list]:
    """Resolve collisions where multiple words map to same typo.

    Args:
        typo_map: Map of typos to (word, boundary) pairs
        freq_ratio: Minimum frequency ratio for collision resolution
        min_typo_length: Minimum typo length
        min_word_length: Minimum word length
        user_words: Set of user-provided words
        exclusion_matcher: Matcher for exclusion rules
        debug_words: Set of words to debug (exact matches)
        debug_typo_matcher: Matcher for debug typos (with wildcards/boundaries)

    Returns:
        Tuple of (final_corrections, skipped_collisions, skipped_short, excluded_corrections)
    """
    if debug_words is None:
        debug_words = set()

    final_corrections = []
    skipped_collisions = []
    skipped_short = []
    excluded_corrections = []

    for typo, word_boundary_list in typo_map.items():
        unique_pairs = list(set(word_boundary_list))
        unique_words = list(set(w for w, _ in unique_pairs))

        if len(unique_words) == 1:
            # Single word case: no collision
            word = unique_words[0]
            boundaries = [b for w, b in unique_pairs if w == word]

            correction, was_skipped_short, excluded_info = _process_single_word_correction(
                typo,
                word,
                boundaries,
                min_typo_length,
                min_word_length,
                user_words,
                exclusion_matcher,
                debug_words,
                debug_typo_matcher,
            )

            if was_skipped_short:
                skipped_short.append((typo, word, len(typo)))
            elif excluded_info:
                excluded_corrections.append(excluded_info)
            elif correction:
                final_corrections.append(correction)
        else:
            # Collision case: multiple words compete for same typo
            correction, was_skipped_short, excluded_info, ratio = _process_collision_case(
                typo,
                unique_words,
                unique_pairs,
                freq_ratio,
                min_typo_length,
                min_word_length,
                user_words,
                exclusion_matcher,
                debug_words,
                debug_typo_matcher,
            )

            if was_skipped_short:
                # Find the word that was selected before skipping
                word_freqs = [(w, word_frequency(w, "en")) for w in unique_words]
                word_freqs.sort(key=lambda x: x[1], reverse=True)
                selected_word = word_freqs[0][0]
                skipped_short.append((typo, selected_word, len(typo)))
            elif excluded_info:
                excluded_corrections.append(excluded_info)
            elif correction:
                final_corrections.append(correction)
            else:
                # Ambiguous collision - ratio too low
                skipped_collisions.append((typo, unique_words, ratio))

    return final_corrections, skipped_collisions, skipped_short, excluded_corrections


def remove_substring_conflicts(
    corrections: list[Correction],
    verbose: bool = False,
    debug_words: set[str] | None = None,
    debug_typo_matcher: "DebugTypoMatcher | None" = None,
) -> list[Correction]:
    """Remove corrections where one typo is a substring of another WITH THE SAME BOUNDARY.

    When Espanso sees a typo, it triggers on the first (shortest) match from left to right.

    Example 1: If we have 'teh' → 'the' and 'tehir' → 'their' (both no boundary):
    - When typing "tehir", Espanso sees "teh" first and corrects to "the"
    - User continues typing "ir", getting "their"
    - The "tehir" correction is unreachable, so remove it

    Example 2: If we have 'toin' (no boundary) → 'ton' and 'toin' (right_word) → 'tion':
    - These have DIFFERENT boundaries, so they DON'T conflict
    - 'toin' (no boundary) matches standalone "toin"
    - 'toin' (right_word) matches as a suffix in "*toin"
    - Both can coexist

    Example 3: If we have 'toin' → 'tion' and 'atoin' → 'ation' (both RIGHT):
    - Both would match at end of "information"
    - "toin" makes "atoin" redundant—the "a" is useless
    - Remove "atoin" in favor of shorter "toin"

    Args:
        corrections: List of corrections to check for conflicts
        verbose: Whether to print verbose output
        debug_words: Set of words to debug (exact matches)
        debug_typo_matcher: Matcher for debug typos (with wildcards/boundaries)

    Returns:
        List of corrections with conflicts removed
    """
    # Group by boundary type - process each separately
    by_boundary = {}
    for correction in corrections:
        _, _, boundary = correction
        if boundary not in by_boundary:
            by_boundary[boundary] = []
        by_boundary[boundary].append(correction)

    # Process each boundary group
    final_corrections = []

    if verbose and len(by_boundary) > 1:
        groups_iter = tqdm(
            by_boundary.items(),
            desc="Removing conflicts",
            unit="boundary",
            total=len(by_boundary),
        )
    else:
        groups_iter = by_boundary.items()

    for boundary, group in groups_iter:
        final_corrections.extend(
            resolve_conflicts_for_group(group, boundary, debug_words, debug_typo_matcher)
        )

    return final_corrections
