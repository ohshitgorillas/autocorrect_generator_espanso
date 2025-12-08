"""Sorting and ranking functions for QMK."""

from typing import TYPE_CHECKING

from entroppy.core import BoundaryType, Correction
from entroppy.platforms.qmk.qmk_logging import log_max_corrections_limit, log_ranking_position
from entroppy.utils.debug import is_debug_correction

from .scorer import (
    _build_word_frequency_cache,
    _collect_all_words,
    score_direct_corrections,
    score_patterns,
)
from .tiers import separate_by_type

if TYPE_CHECKING:
    from entroppy.resolution.state import DictionaryState
    from entroppy.utils.debug import DebugTypoMatcher


def _get_tier_info(
    i: int,
    user_count: int,
    pattern_count: int,
    direct_count: int,
    correction: Correction,
    pattern_score_dict: dict[Correction, float],
    direct_score_dict: dict[Correction, float],
) -> tuple[int, int, str, int, float | None]:
    """Get tier information for a correction at index i.

    Returns:
        Tuple of (tier, tier_pos, tier_name, tier_total, score)
    """
    if i < user_count:
        return 0, i + 1, "user words", user_count, None
    if i < user_count + pattern_count:
        tier_pos = i - user_count + 1
        pattern_score = pattern_score_dict.get(correction)
        return 1, tier_pos, "patterns", pattern_count, pattern_score
    # Direct corrections tier
    tier_pos = i - user_count - pattern_count + 1
    direct_score = direct_score_dict.get(correction)
    return 2, tier_pos, "direct corrections", direct_count, direct_score


def _log_single_correction_debug(
    i: int,
    correction: Correction,
    ranked: list[Correction],
    user_count: int,
    pattern_count: int,
    direct_count: int,
    pattern_score_dict: dict[Correction, float],
    direct_score_dict: dict[Correction, float],
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
    state: "DictionaryState | None" = None,
) -> None:
    """Log debug information for a single correction."""
    tier, tier_pos, tier_name, tier_total, score = _get_tier_info(
        i,
        user_count,
        pattern_count,
        direct_count,
        correction,
        pattern_score_dict,
        direct_score_dict,
    )

    log_ranking_position(
        correction,
        i + 1,
        len(ranked),
        tier,
        tier_name,
        tier_pos,
        tier_total,
        score,
        None,  # nearby_corrections removed
        debug_words,
        debug_typo_matcher,
        state,
    )


def _log_ranking_debug(
    ranked: list[Correction],
    user_corrections: list[Correction],
    pattern_scores: list[tuple[float, str, str, BoundaryType]],
    direct_scores: list[tuple[float, str, str, BoundaryType]],
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
    state: "DictionaryState | None" = None,
) -> None:
    """Log ranking debug information for debug corrections.

    Args:
        ranked: Ranked list of corrections
        user_corrections: User corrections list
        pattern_scores: Pattern scores list
        direct_scores: Direct correction scores list
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos
        state: Optional dictionary state for storing structured debug data
    """
    # Build lookup dictionaries once instead of searching lists
    pattern_score_dict = {(t, w, b): score for score, t, w, b in pattern_scores}
    direct_score_dict = {(t, w, b): score for score, t, w, b in direct_scores}

    # Build tier boundaries for context
    user_count = len(user_corrections)
    pattern_count = len(pattern_scores)
    direct_count = len(direct_scores)

    for i, correction in enumerate(ranked):
        if is_debug_correction(correction, debug_words, debug_typo_matcher):
            _log_single_correction_debug(
                i,
                correction,
                ranked,
                user_count,
                pattern_count,
                direct_count,
                pattern_score_dict,
                direct_score_dict,
                debug_words,
                debug_typo_matcher,
                state,
            )


def _log_max_corrections_debug(
    ranked: list[Correction],
    max_corrections: int,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
    state: "DictionaryState | None" = None,
) -> None:
    """Log max corrections limit debug information.

    Args:
        ranked: Ranked list of corrections
        max_corrections: Maximum number of corrections
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos
        state: Optional dictionary state for storing structured debug data
    """
    # Log if any debug corrections are cut off by the limit
    for i, correction in enumerate(ranked):
        if is_debug_correction(correction, debug_words, debug_typo_matcher):
            log_max_corrections_limit(
                correction,
                i + 1,
                max_corrections,
                len(ranked),
                i < max_corrections,
                debug_words,
                debug_typo_matcher,
                state,
            )


def rank_corrections(
    corrections: list[Correction],
    patterns: list[Correction],
    pattern_replacements: dict[Correction, list[Correction]],
    user_words: set[str],
    max_corrections: int | None = None,
    cached_pattern_typos: set[tuple[str, str]] | None = None,
    cached_replaced_by_patterns: set[tuple[str, str]] | None = None,
    verbose: bool = False,
    debug_words: set[str] | None = None,
    debug_typo_matcher: "DebugTypoMatcher | None" = None,
    state: "DictionaryState | None" = None,
) -> tuple[
    list[Correction],
    list[Correction],
    list[tuple[float, str, str, BoundaryType]],
    list[tuple[float, str, str, BoundaryType]],
    list[tuple[float, str, str, BoundaryType]],
]:
    """Rank corrections by QMK-specific usefulness.

    Three-tier system:
    1. User words (infinite priority)
    2. Patterns (scored by sum of replaced word frequencies)
    3. Direct corrections (scored by word frequency)

    Optimized with:
    - Batch word frequency lookups (Priority 1)
    - Lazy evaluation for debug logging (Priority 2)
    - Separate sorting per tier (Priority 5)
    - O(1) score lookups for debug logging (Priority 4)

    Args:
        corrections: List of corrections to rank
        patterns: List of pattern corrections
        pattern_replacements: Dictionary mapping patterns to their replacements
        user_words: Set of user-defined words
        max_corrections: Optional limit on number of corrections
        cached_pattern_typos: Optional cached set of (typo, word) tuples for patterns
        cached_replaced_by_patterns: Optional cached set of (typo, word) tuples replaced by patterns
        verbose: Whether to show progress bars
        debug_words: Set of words to debug (exact matches)
        debug_typo_matcher: Matcher for debug typos (with wildcards/boundaries)
        state: Optional dictionary state for storing structured debug data

    Returns:
        Tuple of (ranked_corrections, user_corrections, pattern_scores, direct_scores, all_scored)
    """
    user_corrections, pattern_corrections, direct_corrections = separate_by_type(
        corrections,
        patterns,
        pattern_replacements,
        user_words,
        cached_pattern_typos,
        cached_replaced_by_patterns,
        debug_words,
        debug_typo_matcher,
    )

    # Priority 1: Batch word frequency lookups
    # Collect all unique words that need frequency lookups
    all_words = _collect_all_words(pattern_corrections, direct_corrections, pattern_replacements)

    # Pre-compute all word frequencies in one batch
    word_freq_cache = _build_word_frequency_cache(all_words, verbose)

    # Score patterns using pre-computed cache
    pattern_scores = score_patterns(
        pattern_corrections,
        pattern_replacements,
        word_freq_cache,
        verbose,
        debug_words,
        debug_typo_matcher,
    )

    # Score direct corrections using pre-computed cache
    direct_scores = score_direct_corrections(
        direct_corrections,
        word_freq_cache,
        verbose,
        debug_words,
        debug_typo_matcher,
    )

    # Priority 5: Sort patterns and direct corrections separately (they're in different tiers)
    # Sort patterns by score (descending)
    pattern_scores.sort(key=lambda x: -x[0])

    # Sort direct corrections by score (descending)
    direct_scores.sort(key=lambda x: -x[0])

    # Build ranked list: user words first, then sorted patterns, then sorted direct corrections
    ranked = (
        user_corrections
        + [(t, w, b) for _, t, w, b in pattern_scores]
        + [(t, w, b) for _, t, w, b in direct_scores]
    )

    # Priority 4: Optimize debug logging with O(1) lookup dictionaries
    if debug_words or debug_typo_matcher:
        _log_ranking_debug(
            ranked,
            user_corrections,
            pattern_scores,
            direct_scores,
            debug_words or set(),
            debug_typo_matcher,
            state,
        )

    # Apply max_corrections limit if specified
    if max_corrections:
        if debug_words or debug_typo_matcher:
            _log_max_corrections_debug(
                ranked, max_corrections, debug_words or set(), debug_typo_matcher, state
            )
        ranked = ranked[:max_corrections]

    # Build all_scored for backward compatibility (combines patterns and direct)
    all_scored = pattern_scores + direct_scores

    return ranked, user_corrections, pattern_scores, direct_scores, all_scored
