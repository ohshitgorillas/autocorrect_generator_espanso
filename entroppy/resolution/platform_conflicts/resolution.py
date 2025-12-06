"""Platform substring conflict resolution logic.

This module contains the resolution algorithms for determining which corrections
to remove when resolving cross-boundary substring conflicts.
"""

from typing import TYPE_CHECKING

from entroppy.core.boundaries import BoundaryIndex, BoundaryType
from entroppy.core.types import MatchDirection
from entroppy.resolution.false_trigger_check import _check_false_trigger_with_details
from entroppy.resolution.platform_conflicts.debug import (
    log_boundary_comparison,
    log_false_trigger_check,
    log_resolution_decision,
)

if TYPE_CHECKING:
    from entroppy.utils.debug import DebugTypoMatcher

# Boundary priority mapping: lower number = less restrictive (matches in more contexts)
# Used to determine which correction to keep when resolving conflicts
# We prefer less restrictive boundaries (lower priority) when both passed false trigger checks
BOUNDARY_PRIORITY = {
    BoundaryType.NONE: 0,  # Least restrictive (matches anywhere)
    BoundaryType.LEFT: 1,  # More restrictive (matches at word start only)
    BoundaryType.RIGHT: 1,  # More restrictive (matches at word end only)
    BoundaryType.BOTH: 2,  # Most restrictive (matches standalone words only)
}


def _identify_less_restrictive_boundary(
    shorter_typo: str,
    longer_typo: str,
    shorter_word: str,
    longer_word: str,
    shorter_boundary: BoundaryType,
    longer_boundary: BoundaryType,
) -> tuple[str, str, BoundaryType, BoundaryType] | None:
    """Identify which boundary is less restrictive, returning None if same priority."""
    shorter_priority = BOUNDARY_PRIORITY.get(shorter_boundary, 0)
    longer_priority = BOUNDARY_PRIORITY.get(longer_boundary, 0)

    if shorter_priority < longer_priority:
        return shorter_typo, shorter_word, shorter_boundary, longer_boundary
    if longer_priority < shorter_priority:
        return longer_typo, longer_word, longer_boundary, shorter_boundary
    return None  # Same priority


def _handle_same_priority_boundaries(
    match_direction: MatchDirection,
) -> bool:
    """Handle case where boundaries have same priority."""
    # Default to keeping shorter for RTL, longer for LTR
    if match_direction == MatchDirection.RIGHT_TO_LEFT:
        return False  # Keep shorter for RTL
    return True  # Remove shorter for LTR


def _check_and_prefer_less_restrictive(
    less_restrictive_typo: str,
    less_restrictive_word: str,
    less_restrictive_boundary: BoundaryType,
    _more_restrictive_boundary: BoundaryType,  # Unused but kept for API consistency
    shorter_boundary: BoundaryType,
    validation_index: BoundaryIndex | None,
    source_index: BoundaryIndex | None,
    debug_words: set[str] | None,
    debug_typo_matcher: "DebugTypoMatcher | None",
) -> bool | None:
    """Check if less restrictive boundary is safe, returning decision or None if no indices."""
    if validation_index is None or source_index is None:
        return None

    would_cause, details = _check_false_trigger_with_details(
        less_restrictive_typo,
        less_restrictive_boundary,
        validation_index,
        source_index,
        target_word=less_restrictive_word,
    )

    # Log false trigger check if debugging
    if debug_words is not None or debug_typo_matcher is not None:
        reason_value = details.get("reason") if details else None
        reason_str = reason_value if isinstance(reason_value, str) else None
        log_false_trigger_check(
            less_restrictive_typo,
            less_restrictive_word,
            less_restrictive_boundary,
            would_cause,
            reason_str,
            debug_words or set(),
            debug_typo_matcher,
        )

    if not would_cause:
        # Less restrictive boundary doesn't trigger garbage corrections - prefer it
        # Remove the more restrictive one
        if less_restrictive_boundary == shorter_boundary:
            return False  # Keep shorter (less restrictive), remove longer (more restrictive)
        return True  # Remove shorter (more restrictive), keep longer (less restrictive)

    return None  # Less restrictive would cause false triggers


def should_remove_shorter(
    match_direction: MatchDirection,
    shorter_typo: str,
    longer_typo: str,
    shorter_word: str,
    longer_word: str,
    shorter_boundary: BoundaryType,
    longer_boundary: BoundaryType,
    validation_index: BoundaryIndex | None = None,
    source_index: BoundaryIndex | None = None,
    debug_words: set[str] | None = None,
    debug_typo_matcher: "DebugTypoMatcher | None" = None,
) -> bool:
    """Determine if the shorter formatted typo should be removed.

    When resolving substring conflicts between patterns with different boundaries,
    we prefer the less restrictive boundary (e.g., NONE over LEFT) if it doesn't
    trigger garbage corrections. This ensures we keep the most useful correction
    while avoiding false triggers.

    Args:
        match_direction: Platform match direction
        shorter_typo: The shorter typo string (core typo, not formatted)
        longer_typo: The longer typo string (core typo, not formatted)
        shorter_word: Word for shorter typo
        longer_word: Word for longer typo
        shorter_boundary: Boundary type for shorter typo
        longer_boundary: Boundary type for longer typo
        validation_index: Optional boundary index for validation set (for false trigger checks)
        source_index: Optional boundary index for source words (for false trigger checks)
        debug_words: Optional set of words to debug
        debug_typo_matcher: Optional matcher for debug typos

    Returns:
        True if shorter should be removed, False if longer should be removed
    """
    # Identify the less restrictive boundary
    result = _identify_less_restrictive_boundary(
        shorter_typo,
        longer_typo,
        shorter_word,
        longer_word,
        shorter_boundary,
        longer_boundary,
    )

    if result is None:
        # Same priority - use match direction
        return _handle_same_priority_boundaries(match_direction)

    (
        less_restrictive_typo,
        less_restrictive_word,
        less_restrictive_boundary,
        more_restrictive_boundary,
    ) = result

    # Log boundary comparison if debugging
    if debug_words is not None or debug_typo_matcher is not None:
        # Determine more restrictive typo for logging
        more_restrictive_typo = (
            longer_typo if less_restrictive_boundary == shorter_boundary else shorter_typo
        )

        log_boundary_comparison(
            shorter_typo,
            shorter_word,
            shorter_boundary,
            longer_typo,
            longer_word,
            longer_boundary,
            less_restrictive_typo,
            less_restrictive_boundary,
            more_restrictive_typo,
            more_restrictive_boundary,
            debug_words or set(),
            debug_typo_matcher,
        )

    # Check if less restrictive boundary is safe
    decision = _check_and_prefer_less_restrictive(
        less_restrictive_typo,
        less_restrictive_word,
        less_restrictive_boundary,
        more_restrictive_boundary,
        shorter_boundary,
        validation_index,
        source_index,
        debug_words,
        debug_typo_matcher,
    )

    if decision is not None:
        return decision

    # Less restrictive boundary would cause false triggers, or we don't have indices
    # Fall back to keeping the more restrictive boundary (which is safer)
    if more_restrictive_boundary == shorter_boundary:
        return False  # Keep shorter (more restrictive), remove longer (less restrictive)
    return True  # Remove shorter (less restrictive), keep longer (more restrictive)


def _determine_less_restrictive_boundary(
    boundary1: BoundaryType,
    boundary2: BoundaryType,
    typo1: str,
    typo2: str,
    match_direction: MatchDirection,
) -> tuple[str, BoundaryType]:
    """Determine which boundary is less restrictive.

    Args:
        boundary1: First boundary type
        boundary2: Second boundary type
        typo1: First typo
        typo2: Second typo
        match_direction: Platform match direction

    Returns:
        Tuple of (less_restrictive_typo, less_restrictive_boundary)
    """
    shorter_priority = BOUNDARY_PRIORITY.get(boundary1, 0)
    longer_priority = BOUNDARY_PRIORITY.get(boundary2, 0)
    if shorter_priority < longer_priority:
        return typo1, boundary1
    if longer_priority < shorter_priority:
        return typo2, boundary2
    # Same priority - determine based on match direction
    if match_direction == MatchDirection.RIGHT_TO_LEFT:
        return typo1, boundary1
    return typo2, boundary2


def _check_false_triggers_for_conflict(
    less_restrictive_typo: str,
    less_restrictive_boundary: BoundaryType,
    word1: str,
    word2: str,
    typo1: str,
    validation_index: BoundaryIndex | None,
    source_index: BoundaryIndex | None,
) -> tuple[bool | None, str | None]:
    """Check false triggers for the less restrictive boundary.

    Args:
        less_restrictive_typo: The less restrictive typo
        less_restrictive_boundary: The less restrictive boundary
        word1: First word
        word2: Second word
        typo1: First typo
        validation_index: Optional boundary index for validation set
        source_index: Optional boundary index for source words

    Returns:
        Tuple of (would_cause_false_triggers, false_trigger_reason)
    """
    if validation_index is None or source_index is None:
        return None, None

    would_cause, details = _check_false_trigger_with_details(
        less_restrictive_typo,
        less_restrictive_boundary,
        validation_index,
        source_index,
        target_word=word1 if less_restrictive_typo == typo1 else word2,
    )
    reason_value = details.get("reason") if details else None
    false_trigger_reason = reason_value if isinstance(reason_value, str) else None
    return would_cause, false_trigger_reason


def _log_conflict_resolution(
    typo1: str,
    word1: str,
    boundary1: BoundaryType,
    typo2: str,
    word2: str,
    boundary2: BoundaryType,
    less_restrictive_typo: str,
    less_restrictive_boundary: BoundaryType,
    checked_false_triggers: bool,
    would_cause_false_triggers: bool | None,
    false_trigger_reason: str | None,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
    remove_first: bool,
) -> None:
    """Log conflict resolution decision.

    Args:
        typo1: First typo
        word1: First word
        boundary1: First boundary
        typo2: Second typo
        word2: Second word
        boundary2: Second boundary
        less_restrictive_typo: Less restrictive typo
        less_restrictive_boundary: Less restrictive boundary
        checked_false_triggers: Whether false triggers were checked
        would_cause_false_triggers: Whether false triggers would occur
        false_trigger_reason: Reason for false triggers
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos
        remove_first: Whether removing first correction
    """
    if debug_words or debug_typo_matcher:
        if remove_first:
            log_resolution_decision(
                typo1,
                word1,
                boundary1,
                typo2,
                word2,
                boundary2,
                less_restrictive_typo,
                less_restrictive_boundary,
                checked_false_triggers,
                would_cause_false_triggers,
                false_trigger_reason,
                debug_words,
                debug_typo_matcher,
            )
        else:
            log_resolution_decision(
                typo2,
                word2,
                boundary2,
                typo1,
                word1,
                boundary1,
                less_restrictive_typo,
                less_restrictive_boundary,
                checked_false_triggers,
                would_cause_false_triggers,
                false_trigger_reason,
                debug_words,
                debug_typo_matcher,
            )


def process_conflict_pair(
    correction1: tuple[str, str, BoundaryType],
    correction2: tuple[str, str, BoundaryType],
    shorter_formatted_typo: str,
    formatted_typo: str,
    boundary1: BoundaryType,
    boundary2: BoundaryType,
    match_direction: MatchDirection,
    processed_pairs: set[frozenset[tuple[str, str, BoundaryType]]],
    corrections_to_remove_set: set[tuple[str, str, BoundaryType]],
    validation_index: BoundaryIndex | None = None,
    source_index: BoundaryIndex | None = None,
    debug_words: set[str] | None = None,
    debug_typo_matcher: "DebugTypoMatcher | None" = None,
) -> tuple[
    tuple[tuple[str, str, BoundaryType], str] | None,
    tuple[tuple[str, str, BoundaryType], tuple[str, str, BoundaryType]] | None,
]:
    """Process a single conflict pair and determine which correction to remove.

    Args:
        correction1: First correction (from shorter formatted typo)
        correction2: Second correction (from longer formatted typo)
        shorter_formatted_typo: The shorter formatted typo string
        formatted_typo: The longer formatted typo string
        boundary1: Boundary type for correction1
        boundary2: Boundary type for correction2
        match_direction: Platform match direction
        processed_pairs: Set of already processed correction pairs
        corrections_to_remove_set: Set of corrections already marked for removal
        validation_index: Optional boundary index for validation set (for false trigger checks)
        source_index: Optional boundary index for source words (for false trigger checks)
        debug_words: Optional set of words to debug
        debug_typo_matcher: Optional matcher for debug typos

    Returns:
        Tuple of:
        - (correction_to_remove, reason) or None if pair already processed
        - (removed_correction, conflicting_correction) or None if pair already processed
    """
    # Skip if already marked for removal (early termination)
    if correction1 in corrections_to_remove_set or correction2 in corrections_to_remove_set:
        return None, None

    # Use frozenset to create unique pair identifier
    pair_id = frozenset([correction1, correction2])
    if pair_id in processed_pairs:
        return None, None
    processed_pairs.add(pair_id)

    # Determine which one to remove based on match direction and false trigger checks
    typo1, word1, _ = correction1
    typo2, word2, _ = correction2

    # Determine which boundary is less restrictive
    less_restrictive_typo, less_restrictive_boundary = _determine_less_restrictive_boundary(
        boundary1, boundary2, typo1, typo2, match_direction
    )

    # Check false triggers to determine decision
    checked_false_triggers = validation_index is not None and source_index is not None
    would_cause_false_triggers, false_trigger_reason = _check_false_triggers_for_conflict(
        less_restrictive_typo,
        less_restrictive_boundary,
        word1,
        word2,
        typo1,
        validation_index,
        source_index,
    )

    if should_remove_shorter(
        match_direction,
        typo1,
        typo2,
        word1,
        word2,
        boundary1,
        boundary2,
        validation_index,
        source_index,
        debug_words,
        debug_typo_matcher,
    ):
        # Remove the shorter formatted one (formatted1)
        reason = (
            f"Cross-boundary substring conflict: "
            f"'{shorter_formatted_typo}' is substring of "
            f"'{formatted_typo}'"
        )

        _log_conflict_resolution(
            typo1,
            word1,
            boundary1,
            typo2,
            word2,
            boundary2,
            less_restrictive_typo,
            less_restrictive_boundary,
            checked_false_triggers,
            would_cause_false_triggers,
            false_trigger_reason,
            debug_words or set(),
            debug_typo_matcher,
            remove_first=True,
        )

        return (correction1, reason), (correction1, correction2)

    # Remove the longer formatted one (formatted2)
    reason = (
        f"Cross-boundary substring conflict: "
        f"'{formatted_typo}' contains substring "
        f"'{shorter_formatted_typo}'"
    )

    _log_conflict_resolution(
        typo2,
        word2,
        boundary2,
        typo1,
        word1,
        boundary1,
        less_restrictive_typo,
        less_restrictive_boundary,
        checked_false_triggers,
        would_cause_false_triggers,
        false_trigger_reason,
        debug_words or set(),
        debug_typo_matcher,
        remove_first=False,
    )

    return (correction2, reason), (correction2, correction1)
