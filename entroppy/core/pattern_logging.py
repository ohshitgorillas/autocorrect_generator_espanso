"""Debug logging functions for pattern generalization."""

from typing import TYPE_CHECKING

from loguru import logger

from entroppy.core.boundaries import BoundaryType
from entroppy.core.pattern_validation import _log_pattern_acceptance, _log_pattern_rejection
from entroppy.core.types import Correction
from entroppy.utils.debug import log_if_debug_correction

if TYPE_CHECKING:
    from entroppy.utils.debug import DebugTypoMatcher


def is_debug_pattern(
    typo_pattern: str,
    occurrences: list[Correction],
    debug_typo_matcher: "DebugTypoMatcher | None",
) -> bool:
    """Check if a pattern matches any debug typos.

    Args:
        typo_pattern: The typo pattern to check
        occurrences: List of occurrences for this pattern
        debug_typo_matcher: Matcher for debug typos

    Returns:
        True if this is a debug pattern, False otherwise
    """
    if not debug_typo_matcher:
        return False
    return any(
        debug_typo.lower() in typo_pattern.lower()
        or any(debug_typo.lower() in occ[0].lower() for occ in occurrences)
        for debug_typo in debug_typo_matcher.exact_patterns
    )


def log_pattern_candidate(
    typo_pattern: str,
    word_pattern: str,
    occurrences: list[Correction],
    debug_typo_matcher: "DebugTypoMatcher | None",
) -> None:
    """Log when processing a pattern candidate.

    Args:
        typo_pattern: The typo pattern
        word_pattern: The word pattern
        occurrences: List of occurrences for this pattern
        debug_typo_matcher: Matcher for debug typos
    """
    if is_debug_pattern(typo_pattern, occurrences, debug_typo_matcher):
        logger.debug(
            f"[PATTERN GENERALIZATION] Processing pattern candidate: "
            f"'{typo_pattern}' → '{word_pattern}' ({len(occurrences)} occurrences)"
        )


def process_rejected_pattern(
    typo_pattern: str,
    word_pattern: str,
    boundary: BoundaryType,
    reason: str,
    occurrences: list[Correction],
    is_debug_pattern_flag: bool,
    has_debug_occurrence: bool,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
    rejected_patterns: list[tuple[str, str, BoundaryType, str]],
) -> None:
    """Process a rejected pattern by logging and adding to rejected list.

    Args:
        typo_pattern: The typo pattern
        word_pattern: The word pattern
        boundary: The boundary type
        reason: Reason for rejection
        occurrences: List of occurrences for this pattern
        is_debug_pattern_flag: Whether this is a debug pattern
        has_debug_occurrence: Whether any occurrence is a debug item
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos
        rejected_patterns: List to append rejected pattern to
    """
    rejected_patterns.append((typo_pattern, word_pattern, boundary, reason))
    if is_debug_pattern_flag:
        logger.debug(
            f"[PATTERN GENERALIZATION] REJECTED: '{typo_pattern}' → '{word_pattern}': {reason}"
        )
    # For "Too short" rejections, include occurrence count in log message
    log_reason = reason
    if reason.startswith("Too short"):
        log_reason = f"{reason}, would have replaced {len(occurrences)} corrections"
    _log_pattern_rejection(
        typo_pattern,
        word_pattern,
        boundary,
        log_reason,
        has_debug_occurrence,
        debug_words,
        debug_typo_matcher,
    )


def process_accepted_pattern(
    typo_pattern: str,
    word_pattern: str,
    boundary: BoundaryType,
    occurrences: list[Correction],
    has_debug_occurrence: bool,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
    patterns: list[Correction],
    pattern_replacements: dict[Correction, list[Correction]],
    corrections_to_remove: set[Correction],
) -> None:
    """Process an accepted pattern by logging and adding to results.

    Args:
        typo_pattern: The typo pattern
        word_pattern: The word pattern
        boundary: The boundary type
        occurrences: List of occurrences for this pattern
        has_debug_occurrence: Whether any occurrence is a debug item
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos
        patterns: List to append accepted pattern to
        pattern_replacements: Dict to store pattern replacements
        corrections_to_remove: Set to add corrections to remove
    """
    pattern_key = (typo_pattern, word_pattern, boundary)
    patterns.append(pattern_key)
    pattern_replacements[pattern_key] = occurrences

    # Log pattern acceptance for debug
    _log_pattern_acceptance(
        typo_pattern,
        word_pattern,
        boundary,
        occurrences,
        has_debug_occurrence,
        debug_words,
        debug_typo_matcher,
    )

    # Mark original corrections for removal
    for typo, word, orig_boundary in occurrences:
        correction = (typo, word, orig_boundary)
        corrections_to_remove.add(correction)
        # Log individual replacements for debug items
        log_if_debug_correction(
            correction,
            f"Will be replaced by pattern: {typo_pattern} → {word_pattern}",
            debug_words,
            debug_typo_matcher,
            "Stage 4",
        )
