"""Debug logging functions for QMK platform filtering and ranking."""

from typing import TYPE_CHECKING

from entroppy.core import Correction
from entroppy.utils.debug import is_debug_correction, log_debug_correction

if TYPE_CHECKING:
    from entroppy.utils.debug import DebugTypoMatcher


def log_separation_by_type(
    correction: Correction,
    _correction_type: str,  # Unused but kept for API consistency
    message: str,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
) -> None:
    """Log when a correction is separated by type (user word, pattern, or direct).

    Args:
        correction: The correction being separated
        _correction_type: Type of correction ("user word", "pattern", "direct", or "replaced")
        message: The message to log
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos
    """
    if is_debug_correction(correction, debug_words, debug_typo_matcher):
        log_debug_correction(correction, message, debug_words, debug_typo_matcher, "Stage 6")


def log_pattern_scoring(
    correction: Correction,
    total_freq: float,
    replacement_count: int,
    replacement_list: str,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
) -> None:
    """Log when a pattern is scored.

    Args:
        correction: The pattern correction
        total_freq: Total frequency score
        replacement_count: Number of replacements
        replacement_list: String representation of replacement words
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos
    """
    if is_debug_correction(correction, debug_words, debug_typo_matcher):
        log_debug_correction(
            correction,
            f"Scored pattern: {total_freq:.2e} (sum of frequencies for "
            f"{replacement_count} replacements: {replacement_list})",
            debug_words,
            debug_typo_matcher,
            "Stage 6",
        )


def log_direct_scoring(
    correction: Correction,
    freq: float,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
) -> None:
    """Log when a direct correction is scored.

    Args:
        correction: The direct correction
        freq: Word frequency score
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos
    """
    if is_debug_correction(correction, debug_words, debug_typo_matcher):
        log_debug_correction(
            correction,
            f"Scored direct correction: {freq:.2e} (word frequency)",
            debug_words,
            debug_typo_matcher,
            "Stage 6",
        )


def log_ranking_position(
    correction: Correction,
    position: int,
    total: int,
    tier: int,
    tier_name: str,
    tier_pos: int,
    tier_total: int,
    score_info: str,
    nearby_info: str,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
) -> None:
    """Log the final ranking position of a correction.

    Args:
        correction: The correction being ranked
        position: Overall position (1-indexed)
        total: Total number of corrections
        tier: Tier number (0=user, 1=pattern, 2=direct)
        tier_name: Name of the tier
        tier_pos: Position within tier (1-indexed)
        tier_total: Total in tier
        score_info: Score information string
        nearby_info: Nearby corrections information
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos
    """
    if is_debug_correction(correction, debug_words, debug_typo_matcher):
        log_debug_correction(
            correction,
            f"Ranked at position {position}/{total} (tier {tier}: {tier_name}, "
            f"position {tier_pos}/{tier_total}, {score_info}){nearby_info}",
            debug_words,
            debug_typo_matcher,
            "Stage 6",
        )


def log_max_corrections_limit(
    correction: Correction,
    position: int,
    max_corrections: int,
    total_ranked: int,
    within_limit: bool,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
) -> None:
    """Log when a correction is affected by max_corrections limit.

    Args:
        correction: The correction being checked
        position: Position in ranked list (1-indexed)
        max_corrections: Maximum corrections limit
        total_ranked: Total number of ranked corrections
        within_limit: Whether correction is within the limit
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos
    """
    # pylint: disable=duplicate-code
    # This function intentionally duplicates logic from
    # platform_filtering_logging.log_max_corrections_limit_application
    # to maintain separation between platform-specific (QMK) and general pipeline logging.
    # The QMK version is used during platform ranking, while the general version is used in the
    # general pipeline stage. Keeping them separate preserves existing debug logging
    # behavior and allows for platform-specific message customization.
    if is_debug_correction(correction, debug_words, debug_typo_matcher):
        if within_limit:
            log_debug_correction(
                correction,
                f"Made the cut: position {position} (within limit of {max_corrections})",
                debug_words,
                debug_typo_matcher,
                "Stage 6",
            )
        else:
            log_debug_correction(
                correction,
                f"Cut off by max_corrections limit: position {position} "
                f"(limit: {max_corrections}, total ranked: {total_ranked})",
                debug_words,
                debug_typo_matcher,
                "Stage 6",
            )
