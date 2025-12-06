"""Parallelization helpers for platform substring conflict detection.

This module contains worker functions and utilities for parallelizing
the conflict detection phase while maintaining correctness.
"""

from typing import TYPE_CHECKING

from entroppy.core.boundaries import BoundaryIndex, BoundaryType
from entroppy.core.types import MatchDirection
from entroppy.resolution.platform_conflicts.resolution import process_conflict_pair


def _is_substring(shorter: str, longer: str) -> bool:
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


if TYPE_CHECKING:
    from entroppy.utils.debug import DebugTypoMatcher

# Type alias for conflict tuples
_ConflictTuple = tuple[
    str,  # formatted_typo
    list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]],  # corrections_for_typo
    str,  # shorter_formatted_typo
    list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]],  # shorter_corrections
]


def detect_conflicts_for_chunk(
    typos_chunk: list[tuple[str, list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]]]],
    candidates_by_char: dict[
        str,
        list[tuple[str, list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]]]],
    ],
) -> list[_ConflictTuple]:
    """Worker function to detect conflicts without modifying state (read-only).

    This function finds all substring conflicts in a chunk of typos by checking
    against the candidates_by_char index. It does not resolve conflicts or modify
    any shared state, making it safe for parallel execution.

    Args:
        typos_chunk: Chunk of (formatted_typo, corrections) tuples to check
        candidates_by_char: Character-based index of shorter typos (read-only)

    Returns:
        List of conflict tuples: (formatted_typo, corrections_for_typo,
        shorter_formatted_typo, shorter_corrections)
    """
    conflicts: list[_ConflictTuple] = []

    for formatted_typo, corrections_for_typo in typos_chunk:
        # Build index keys to check
        index_keys_to_check = _build_index_keys_to_check(formatted_typo)

        checked_shorter_typos: set[str] = set()
        for key_to_check in index_keys_to_check:
            if key_to_check in candidates_by_char:
                for shorter_formatted_typo, shorter_corrections in candidates_by_char[key_to_check]:
                    if shorter_formatted_typo in checked_shorter_typos:
                        continue
                    checked_shorter_typos.add(shorter_formatted_typo)

                    # Check if shorter is a substring of current
                    if _is_substring(shorter_formatted_typo, formatted_typo):
                        conflicts.append(
                            (
                                formatted_typo,
                                corrections_for_typo,
                                shorter_formatted_typo,
                                shorter_corrections,
                            )
                        )

    return conflicts


def resolve_conflicts_sequential(
    all_conflicts: list[_ConflictTuple],
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
    """Resolve conflicts sequentially using deterministic rules.

    This function applies the same decision logic as the original algorithm,
    but processes all detected conflicts in a deterministic order to ensure
    consistent results.

    Args:
        all_conflicts: List of detected conflicts from parallel phase
        match_direction: Platform match direction
        processed_pairs: Set of already processed correction pairs (modified in-place)
        corrections_to_remove_set: Set of corrections already marked for removal (modified in-place)
        validation_index: Optional boundary index for validation set
        source_index: Optional boundary index for source words
        debug_words: Optional set of words to debug
        debug_typo_matcher: Optional matcher for debug typos

    Returns:
        Tuple of (corrections_to_remove, conflict_pairs)
    """
    corrections_to_remove: list[tuple[tuple[str, str, BoundaryType], str]] = []
    conflict_pairs: dict[tuple[str, str, BoundaryType], tuple[str, str, BoundaryType]] = {}

    # Sort conflicts deterministically to ensure consistent resolution order
    # Sort by formatted_typo, then shorter_formatted_typo for reproducibility
    sorted_conflicts = sorted(
        all_conflicts,
        key=lambda x: (x[0], x[2]),  # (formatted_typo, shorter_formatted_typo)
    )

    for (
        formatted_typo,
        corrections_for_typo,
        shorter_formatted_typo,
        shorter_corrections,
    ) in sorted_conflicts:
        # Process all combinations of corrections for this conflict
        for correction1, _, boundary1 in shorter_corrections:
            if correction1 in corrections_to_remove_set:
                continue

            for correction2, _, boundary2 in corrections_for_typo:
                if correction2 in corrections_to_remove_set:
                    continue

                # Process conflict pair using existing logic
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
                    break

    return corrections_to_remove, conflict_pairs


def divide_into_chunks(
    items: list[tuple[str, list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]]]],
    num_chunks: int,
) -> list[list[tuple[str, list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]]]]]:
    """Divide a list into approximately equal chunks.

    Args:
        items: List of items to divide
        num_chunks: Number of chunks to create

    Returns:
        List of chunks
    """
    if num_chunks <= 1:
        return [items]

    chunk_size = max(1, len(items) // num_chunks)
    chunks = []
    for i in range(0, len(items), chunk_size):
        chunks.append(items[i : i + chunk_size])
    return chunks
