"""Platform substring conflict detection logic.

This module contains the core detection algorithms for finding cross-boundary
substring conflicts in platform-formatted typo strings.
"""

from collections import defaultdict
from typing import TYPE_CHECKING

from entroppy.core.boundaries import BoundaryIndex, BoundaryType
from entroppy.core.types import MatchDirection
from entroppy.resolution.false_trigger_check import _check_false_trigger_with_details
from entroppy.resolution.platform_substring_conflict_debug import (
    log_boundary_comparison,
    log_false_trigger_check,
    log_resolution_decision,
)

if TYPE_CHECKING:
    from tqdm import tqdm

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


def is_substring(shorter: str, longer: str) -> bool:
    """Check if shorter is a substring of longer.

    Optimized with fast paths for prefix and suffix checks, which are
    common cases (especially for QMK where boundaries create prefixes).

    Args:
        shorter: The shorter string
        longer: The longer string

    Returns:
        True if shorter is a substring of longer
    """
    if not shorter or not longer or shorter == longer:
        return False

    # Fast path: prefix check (common for QMK, e.g., "aemr" in ":aemr")
    if longer.startswith(shorter):
        return True

    # Fast path: suffix check
    if longer.endswith(shorter):
        return True

    # Fallback: middle substring (less common)
    return shorter in longer


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
    # Determine which boundary is less restrictive
    shorter_priority = BOUNDARY_PRIORITY.get(shorter_boundary, 0)
    longer_priority = BOUNDARY_PRIORITY.get(longer_boundary, 0)

    # Identify the less restrictive boundary
    if shorter_priority < longer_priority:
        less_restrictive_typo = shorter_typo
        less_restrictive_word = shorter_word
        less_restrictive_boundary = shorter_boundary
        more_restrictive_boundary = longer_boundary
    elif longer_priority < shorter_priority:
        less_restrictive_typo = longer_typo
        less_restrictive_word = longer_word
        less_restrictive_boundary = longer_boundary
        more_restrictive_boundary = shorter_boundary
    else:
        # Same priority (e.g., LEFT and RIGHT both have priority 1)
        # Default to keeping shorter for RTL, longer for LTR
        if match_direction == MatchDirection.RIGHT_TO_LEFT:
            return False  # Keep shorter for RTL
        return True  # Remove shorter for LTR

    # Log boundary comparison if debugging
    if debug_words is not None or debug_typo_matcher is not None:
        # Determine more restrictive typo for logging
        if less_restrictive_boundary == shorter_boundary:
            more_restrictive_typo = longer_typo
        else:
            more_restrictive_typo = shorter_typo

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

    # If we have validation/source indices, check if the less restrictive boundary
    # would cause false triggers. If it doesn't, prefer it over the more restrictive one.
    if validation_index is not None and source_index is not None:
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

    # Less restrictive boundary would cause false triggers, or we don't have indices
    # Fall back to keeping the more restrictive boundary (which is safer)
    if more_restrictive_boundary == shorter_boundary:
        return False  # Keep shorter (more restrictive), remove longer (less restrictive)
    return True  # Remove shorter (less restrictive), keep longer (more restrictive)


def build_length_buckets(
    formatted_to_corrections: dict[
        str, list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]]
    ],
) -> dict[int, list[tuple[str, list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]]]]]:
    """Group formatted typos by length into buckets.

    Args:
        formatted_to_corrections: Dict mapping formatted_typo ->
            list of (correction, typo, boundary)

    Returns:
        Dict mapping length -> list of (formatted_typo, corrections) tuples
    """
    length_buckets: dict[
        int, list[tuple[str, list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]]]]
    ] = defaultdict(list)

    for formatted_typo, corrections in formatted_to_corrections.items():
        length_buckets[len(formatted_typo)].append((formatted_typo, corrections))

    return length_buckets


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


def _build_index_keys_to_check(formatted_typo: str) -> list[str]:
    """Build list of index keys to check for substring conflicts.

    Args:
        formatted_typo: The formatted typo string

    Returns:
        List of index keys to check
    """
    index_key = formatted_typo[0] if formatted_typo else ""
    index_keys_to_check = [index_key]

    # For QMK boundary prefixes (starts with ':'), also check against the core typo
    if formatted_typo.startswith(":") and len(formatted_typo) > 1:
        core_typo_key = formatted_typo[1] if len(formatted_typo) > 1 else ""
        if core_typo_key:
            index_keys_to_check.append(core_typo_key)
    elif not formatted_typo.startswith(":") and formatted_typo:
        # For core typos, also check against colon-prefixed versions
        index_keys_to_check.append(":")

    # Also check all characters in the formatted typo to catch middle/end substrings
    for char in formatted_typo:
        if char not in index_keys_to_check:
            index_keys_to_check.append(char)

    return index_keys_to_check


def _process_typo_conflicts(
    formatted_typo: str,
    corrections_for_typo: list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]],
    index_keys_to_check: list[str],
    candidates_by_char: dict[
        str,
        list[tuple[str, list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]]]],
    ],
    match_direction: MatchDirection,
    processed_pairs: set[frozenset[tuple[str, str, BoundaryType]]],
    corrections_to_remove_set: set[tuple[str, str, BoundaryType]],
    validation_index: BoundaryIndex | None,
    source_index: BoundaryIndex | None,
    debug_words: set[str] | None,
    debug_typo_matcher: "DebugTypoMatcher | None",
) -> tuple[
    list[tuple[tuple[str, str, BoundaryType], str]],
    dict[tuple[str, str, BoundaryType], tuple[str, str, BoundaryType]],
]:
    """Process conflicts for a single formatted typo.

    Args:
        formatted_typo: The formatted typo string
        corrections_for_typo: List of corrections for this typo
        index_keys_to_check: List of index keys to check
        candidates_by_char: Character-based index of shorter typos
        match_direction: Platform match direction
        processed_pairs: Set of already processed correction pairs
        corrections_to_remove_set: Set of corrections already marked for removal
        validation_index: Optional boundary index for validation set
        source_index: Optional boundary index for source words
        debug_words: Optional set of words to debug
        debug_typo_matcher: Optional matcher for debug typos

    Returns:
        Tuple of (corrections_to_remove, conflict_pairs)
    """
    corrections_to_remove = []
    conflict_pairs: dict[tuple[str, str, BoundaryType], tuple[str, str, BoundaryType]] = {}

    checked_shorter_typos: set[str] = set()
    for key_to_check in index_keys_to_check:
        if key_to_check in candidates_by_char:
            for shorter_formatted_typo, shorter_corrections in candidates_by_char[key_to_check]:
                if shorter_formatted_typo in checked_shorter_typos:
                    continue
                checked_shorter_typos.add(shorter_formatted_typo)

                # Check if shorter is a substring of current
                if is_substring(shorter_formatted_typo, formatted_typo):
                    # Check all combinations of corrections with early termination
                    for correction1, _, boundary1 in shorter_corrections:
                        if correction1 in corrections_to_remove_set:
                            continue

                        for correction2, _, boundary2 in corrections_for_typo:
                            if correction2 in corrections_to_remove_set:
                                continue

                            # Process conflict pair
                            result, conflict_pair = process_conflict_pair(
                                correction1,
                                correction2,
                                shorter_formatted_typo,
                                formatted_typo,
                                boundary1,
                                boundary2,
                                match_direction,
                                processed_pairs,
                                corrections_to_remove_set,
                                validation_index,
                                source_index,
                                debug_words,
                                debug_typo_matcher,
                            )

                            if result is not None:
                                correction_to_remove, reason = result
                                corrections_to_remove.append((correction_to_remove, reason))
                                if conflict_pair is not None:
                                    removed_correction, conflicting_correction = conflict_pair
                                    conflict_pairs[removed_correction] = conflicting_correction
                                    corrections_to_remove_set.add(removed_correction)

                            # Break early if all corrections for this formatted typo are marked
                            if all(
                                c in corrections_to_remove_set for c, _, _ in corrections_for_typo
                            ):
                                break

    return corrections_to_remove, conflict_pairs


def check_bucket_conflicts(
    current_bucket: list[tuple[str, list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]]]],
    candidates_by_char: dict[
        str,
        list[tuple[str, list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]]]],
    ],
    match_direction: MatchDirection,
    processed_pairs: set[frozenset[tuple[str, str, BoundaryType]]],
    corrections_to_remove_set: set[tuple[str, str, BoundaryType]],
    progress_bar: "tqdm | None" = None,
    validation_index: BoundaryIndex | None = None,
    source_index: BoundaryIndex | None = None,
    debug_words: set[str] | None = None,
    debug_typo_matcher: "DebugTypoMatcher | None" = None,
) -> tuple[
    list[tuple[tuple[str, str, BoundaryType], str]],
    dict[tuple[str, str, BoundaryType], tuple[str, str, BoundaryType]],
]:
    """Check conflicts for a bucket against accumulated shorter typos.

    Args:
        current_bucket: List of (formatted_typo, corrections) tuples for current length
        candidates_by_char: Character-based index of shorter typos from previous buckets
        match_direction: Platform match direction
        processed_pairs: Set of already processed correction pairs
        corrections_to_remove_set: Set of corrections already marked for removal
        progress_bar: Optional progress bar to update as typos are processed
        validation_index: Optional boundary index for validation set (for false trigger checks)
        source_index: Optional boundary index for source words (for false trigger checks)
        debug_words: Optional set of words to debug
        debug_typo_matcher: Optional matcher for debug typos

    Returns:
        Tuple of:
        - corrections_to_remove: List of (correction, reason) tuples
        - conflict_pairs: Dict mapping removed_correction -> conflicting_correction
    """
    corrections_to_remove = []
    conflict_pairs: dict[tuple[str, str, BoundaryType], tuple[str, str, BoundaryType]] = {}

    for formatted_typo, corrections_for_typo in current_bucket:
        # Update progress bar for each formatted typo processed
        if progress_bar is not None:
            progress_bar.update(1)

        # Build index keys to check
        index_keys_to_check = _build_index_keys_to_check(formatted_typo)

        # Process conflicts for this typo
        typo_corrections_to_remove, typo_conflict_pairs = _process_typo_conflicts(
            formatted_typo,
            corrections_for_typo,
            index_keys_to_check,
            candidates_by_char,
            match_direction,
            processed_pairs,
            corrections_to_remove_set,
            validation_index,
            source_index,
            debug_words,
            debug_typo_matcher,
        )

        corrections_to_remove.extend(typo_corrections_to_remove)
        conflict_pairs.update(typo_conflict_pairs)

        # Add to index for future checks (only shorter typos are added since we
        # process in length order)
        index_key = formatted_typo[0] if formatted_typo else ""
        candidates_by_char[index_key].append((formatted_typo, corrections_for_typo))

    return corrections_to_remove, conflict_pairs
