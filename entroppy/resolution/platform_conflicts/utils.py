"""Shared utility functions for platform conflict detection."""

from typing import TYPE_CHECKING, Callable

from entroppy.core.boundaries import BoundaryIndex, BoundaryType
from entroppy.core.types import MatchDirection
from entroppy.resolution.platform_conflicts.resolution import process_conflict_pair

if TYPE_CHECKING:
    from entroppy.utils.debug import DebugTypoMatcher


def determine_shorter_longer_formatted_typo(
    formatted_typo: str,
    matched_typo: str,
    corrections_for_typo: list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]],
    matched_corrections: list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]],
) -> tuple[str, str, list, list] | None:
    """Determine which formatted typo is shorter/longer and validate substring.

    Args:
        formatted_typo: Current formatted typo
        matched_typo: Matched formatted typo
        corrections_for_typo: Corrections for current typo
        matched_corrections: Corrections for matched typo

    Returns:
        Tuple of (shorter_typo, longer_typo, shorter_corrections, longer_corrections)
        or None if not a valid substring conflict
    """
    if len(formatted_typo) < len(matched_typo):
        shorter_typo = formatted_typo
        longer_typo = matched_typo
        shorter_corrections = corrections_for_typo
        longer_corrections = matched_corrections
    elif len(formatted_typo) > len(matched_typo):
        shorter_typo = matched_typo
        longer_typo = formatted_typo
        shorter_corrections = matched_corrections
        longer_corrections = corrections_for_typo
    else:
        # Same length - check if they're actually substrings
        if formatted_typo != matched_typo:
            # Different strings of same length can't be substrings
            return None
        # Same string - skip (duplicate)
        return None

    # Suffix array already found this as a substring match
    # Quick CPU verification to ensure it's actually a substring (handles edge cases)
    if not is_substring(shorter_typo, longer_typo):
        return None

    return shorter_typo, longer_typo, shorter_corrections, longer_corrections


def bulk_remove_losing_formatted_typos(
    formatted_typos_to_remove: set[str],
    losing_to_winning_formatted: dict[str, str],
    formatted_to_corrections: dict[
        str, list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]]
    ],
    all_corrections_to_remove: list[tuple[tuple[str, str, BoundaryType], str]],
    all_conflict_pairs: dict[tuple[str, str, BoundaryType], tuple[str, str, BoundaryType]],
) -> None:
    """Bulk remove all corrections with losing formatted typos.

    Args:
        formatted_typos_to_remove: Set of formatted typos to remove
        losing_to_winning_formatted: Dict mapping losing -> winning formatted typo
        formatted_to_corrections: Dict mapping formatted typo -> corrections
        all_corrections_to_remove: List to append removals
        all_conflict_pairs: Dict to update with conflict pairs
    """
    for losing_formatted_typo in formatted_typos_to_remove:
        if losing_formatted_typo not in formatted_to_corrections:
            continue
        losing_corrections = formatted_to_corrections[losing_formatted_typo]
        winning_formatted_typo = losing_to_winning_formatted.get(losing_formatted_typo)
        # Remove all corrections with losing formatted typo
        for correction, _, _ in losing_corrections:
            reason = (
                f"Cross-boundary substring conflict: "
                f"'{losing_formatted_typo}' conflicts with "
                f"'{winning_formatted_typo if winning_formatted_typo else 'another typo'}'"
            )
            all_corrections_to_remove.append((correction, reason))
            # Create conflict pair if we found a winner
            if winning_formatted_typo and winning_formatted_typo in formatted_to_corrections:
                winning_corrections = formatted_to_corrections[winning_formatted_typo]
                if winning_corrections:
                    all_conflict_pairs[correction] = winning_corrections[0][0]


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


def build_index_keys_to_check(formatted_typo: str) -> list[str]:
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


def find_substring_conflicts_in_index(
    formatted_typo: str,
    index_keys_to_check: list[str],
    candidates_by_char: dict[
        str,
        list[tuple[str, list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]]]],
    ],
    is_substring_fn: Callable[[str, str], bool],
) -> list[tuple[str, list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]]]]:
    """Find all shorter formatted typos that are substrings of the given typo.

    This helper function extracts the common pattern of iterating through index keys
    and checking for substring conflicts.

    Args:
        formatted_typo: The formatted typo to check
        index_keys_to_check: List of index keys to check
        candidates_by_char: Character-based index of shorter typos
        is_substring_fn: Function to check if shorter is substring of longer

    Returns:
        List of (shorter_formatted_typo, shorter_corrections) tuples
    """
    checked_shorter_typos: set[str] = set()
    conflicts: list[tuple[str, list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]]]] = []

    for key_to_check in index_keys_to_check:
        if key_to_check in candidates_by_char:
            for shorter_formatted_typo, shorter_corrections in candidates_by_char[key_to_check]:
                if shorter_formatted_typo in checked_shorter_typos:
                    continue
                checked_shorter_typos.add(shorter_formatted_typo)

                # Check if shorter is a substring of current
                if is_substring_fn(shorter_formatted_typo, formatted_typo):
                    conflicts.append((shorter_formatted_typo, shorter_corrections))

    return conflicts


def process_conflict_combinations(
    shorter_corrections: list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]],
    corrections_for_typo: list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]],
    shorter_formatted_typo: str,
    formatted_typo: str,
    match_direction: MatchDirection,
    processed_pairs: set[frozenset[tuple[str, str, BoundaryType]]],
    corrections_to_remove_set: set[tuple[str, str, BoundaryType]],
    corrections_to_remove: list,
    conflict_pairs: dict,
    validation_index: BoundaryIndex | None,
    source_index: BoundaryIndex | None,
    debug_words: set[str] | None,
    debug_typo_matcher: "DebugTypoMatcher | None",
) -> bool:
    """Process all combinations of corrections, returning True if all are marked for removal.

    Args:
        shorter_corrections: List of corrections for the shorter formatted typo
        corrections_for_typo: List of corrections for the longer formatted typo
        shorter_formatted_typo: The shorter formatted typo string
        formatted_typo: The longer formatted typo string
        match_direction: Platform match direction
        processed_pairs: Set of already processed correction pairs
        corrections_to_remove_set: Set of corrections already marked for removal
        corrections_to_remove: List to append (correction, reason) tuples to
        conflict_pairs: Dict to update with conflict pair mappings
        validation_index: Optional boundary index for validation set
        source_index: Optional boundary index for source words
        debug_words: Optional set of words to debug
        debug_typo_matcher: Optional matcher for debug typos

    Returns:
        True if all corrections for the formatted typo are marked for removal
    """
    for correction1, _, boundary1 in shorter_corrections:
        if correction1 in corrections_to_remove_set:
            continue

        for correction2, _, boundary2 in corrections_for_typo:
            if correction2 in corrections_to_remove_set:
                continue

            # Process conflict pair
            # pylint: disable=duplicate-code
            # Acceptable pattern: This is a function call to process_conflict_pair
            # with standard parameters. The similar code in conflict_processing.py calls the
            # same function with the same parameters. This is expected when both places
            # need to process conflict pairs in the same way.
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
                    corrections_to_remove_set.add(correction_to_remove)

            # Break early if all corrections for this formatted typo are marked
            if all(c in corrections_to_remove_set for c, _, _ in corrections_for_typo):
                return True

    return False
