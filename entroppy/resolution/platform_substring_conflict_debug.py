"""Debug logging for platform substring conflict resolution.

This module provides detailed logging for the false trigger checking process
when resolving substring conflicts between corrections with different boundaries.
"""

from typing import TYPE_CHECKING

from entroppy.core.boundaries import BoundaryType
from entroppy.utils.debug import is_debug_correction, log_debug_correction

if TYPE_CHECKING:
    from entroppy.utils.debug import DebugTypoMatcher


def log_false_trigger_check(
    typo: str,
    word: str,
    boundary: BoundaryType,
    would_cause: bool,
    reason: str | None,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
) -> None:
    """Log false trigger check for a typo/boundary combination.

    Args:
        typo: The typo string being checked
        word: The target word
        boundary: The boundary type being checked
        would_cause: Whether this boundary would cause false triggers
        reason: The reason for the false trigger (if any)
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos
    """
    correction = (typo, word, boundary)
    if is_debug_correction(correction, debug_words, debug_typo_matcher):
        status = "WOULD CAUSE" if would_cause else "SAFE"
        reason_text = f" ({reason})" if reason else ""
        log_debug_correction(
            correction,
            f"False trigger check: {boundary.value} boundary is {status}{reason_text}",
            debug_words,
            debug_typo_matcher,
            "PlatformSubstringConflicts",
        )


def log_boundary_comparison(
    typo1: str,
    word1: str,
    boundary1: BoundaryType,
    typo2: str,
    word2: str,
    boundary2: BoundaryType,
    less_restrictive_typo: str,
    less_restrictive_boundary: BoundaryType,
    more_restrictive_typo: str,
    more_restrictive_boundary: BoundaryType,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
) -> None:
    """Log boundary comparison when resolving substring conflicts.

    Args:
        typo1: First typo string
        word1: First target word
        boundary1: First boundary type
        typo2: Second typo string
        word2: Second target word
        boundary2: Second boundary type
        less_restrictive_typo: The typo with less restrictive boundary
        less_restrictive_boundary: The less restrictive boundary type
        more_restrictive_typo: The typo with more restrictive boundary
        more_restrictive_boundary: The more restrictive boundary type
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos
    """
    correction1 = (typo1, word1, boundary1)
    correction2 = (typo2, word2, boundary2)

    # Log for either correction if it's being debugged
    if is_debug_correction(correction1, debug_words, debug_typo_matcher) or is_debug_correction(
        correction2, debug_words, debug_typo_matcher
    ):
        message = (
            f"Boundary comparison: '{less_restrictive_typo}' ({less_restrictive_boundary.value}) "
            f"is less restrictive than '{more_restrictive_typo}' "
            f"({more_restrictive_boundary.value})"
        )

        # Log for correction1 if it's being debugged
        if is_debug_correction(correction1, debug_words, debug_typo_matcher):
            log_debug_correction(
                correction1,
                message,
                debug_words,
                debug_typo_matcher,
                "PlatformSubstringConflicts",
            )

        # Log for correction2 if it's being debugged
        if is_debug_correction(correction2, debug_words, debug_typo_matcher):
            log_debug_correction(
                correction2,
                message,
                debug_words,
                debug_typo_matcher,
                "PlatformSubstringConflicts",
            )


def log_resolution_decision(
    removed_typo: str,
    removed_word: str,
    removed_boundary: BoundaryType,
    kept_typo: str,
    kept_word: str,
    kept_boundary: BoundaryType,
    less_restrictive_typo: str,
    less_restrictive_boundary: BoundaryType,
    checked_false_triggers: bool,
    would_cause_false_triggers: bool | None,
    false_trigger_reason: str | None,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
) -> None:
    """Log the final resolution decision for a substring conflict.

    Args:
        removed_typo: The typo that was removed
        removed_word: The word for the removed correction
        removed_boundary: The boundary for the removed correction
        kept_typo: The typo that was kept
        kept_word: The word for the kept correction
        kept_boundary: The boundary for the kept correction
        less_restrictive_typo: The typo with less restrictive boundary
        less_restrictive_boundary: The less restrictive boundary type
        checked_false_triggers: Whether false triggers were checked
        would_cause_false_triggers: Whether less restrictive boundary would cause false triggers
        false_trigger_reason: Reason for false triggers (if any)
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos
    """
    removed_correction = (removed_typo, removed_word, removed_boundary)
    kept_correction = (kept_typo, kept_word, kept_boundary)

    # Build decision message
    if checked_false_triggers:
        if would_cause_false_triggers:
            decision_reason = (
                f"Less restrictive boundary ({less_restrictive_boundary.value}) would cause "
                f"false triggers{f' ({false_trigger_reason})' if false_trigger_reason else ''}, "
                f"keeping more restrictive boundary ({removed_boundary.value})"
            )
        else:
            decision_reason = (
                f"Less restrictive boundary ({less_restrictive_boundary.value}) is safe, "
                f"removing more restrictive boundary ({removed_boundary.value})"
            )
    else:
        decision_reason = (
            f"No false trigger check performed, using boundary priority "
            f"(removed: {removed_boundary.value}, kept: {kept_boundary.value})"
        )

    message = (
        f"Resolution decision: Removing '{removed_typo}' ({removed_boundary.value}), "
        f"keeping '{kept_typo}' ({kept_boundary.value}). "
        f"Less restrictive: '{less_restrictive_typo}' ({less_restrictive_boundary.value}). "
        f"{decision_reason}"
    )

    # Log for removed correction if it's being debugged
    if is_debug_correction(removed_correction, debug_words, debug_typo_matcher):
        log_debug_correction(
            removed_correction,
            message,
            debug_words,
            debug_typo_matcher,
            "PlatformSubstringConflicts",
        )

    # Log for kept correction if it's being debugged
    if is_debug_correction(kept_correction, debug_words, debug_typo_matcher):
        log_debug_correction(
            kept_correction,
            message,
            debug_words,
            debug_typo_matcher,
            "PlatformSubstringConflicts",
        )
