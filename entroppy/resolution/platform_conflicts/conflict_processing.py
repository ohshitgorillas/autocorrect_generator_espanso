"""Helper functions for processing conflict pairs."""

from typing import TYPE_CHECKING

from entroppy.core.boundaries import BoundaryType
from entroppy.core.types import MatchDirection
from entroppy.resolution.platform_conflicts.resolution import process_conflict_pair

if TYPE_CHECKING:
    from entroppy.core.boundaries.types import BoundaryIndex
    from entroppy.utils.debug import DebugTypoMatcher


def process_conflict_combinations(
    shorter_typo: str,
    longer_typo: str,
    shorter_corrections: list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]],
    longer_corrections: list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]],
    match_direction: MatchDirection,
    processed_pairs: set[frozenset[tuple[str, str, BoundaryType]]],
    corrections_to_remove_set: set[tuple[str, str, BoundaryType]],
    all_corrections_to_remove: list[tuple[tuple[str, str, BoundaryType], str]],
    all_conflict_pairs: dict[tuple[str, str, BoundaryType], tuple[str, str, BoundaryType]],
    validation_index: "BoundaryIndex | None",
    source_index: "BoundaryIndex | None",
    debug_words: set[str] | None,
    debug_typo_matcher: "DebugTypoMatcher | None",
) -> None:
    """Process all combinations of corrections for a conflict pair.

    Args:
        shorter_typo: The shorter typo string
        longer_typo: The longer typo string
        shorter_corrections: Corrections for the shorter typo
        longer_corrections: Corrections for the longer typo
        match_direction: Platform match direction
        processed_pairs: Set of already processed correction pairs
        corrections_to_remove_set: Set of corrections already marked for removal
        all_corrections_to_remove: List to append removals to
        all_conflict_pairs: Dict to update with conflict pairs
        validation_index: Optional boundary index for validation set
        source_index: Optional boundary index for source words
        debug_words: Optional set of words to debug
        debug_typo_matcher: Optional matcher for debug typos
    """
    for correction1, _, boundary1 in shorter_corrections:
        if correction1 in corrections_to_remove_set:
            continue

        for correction2, _, boundary2 in longer_corrections:
            if correction2 in corrections_to_remove_set:
                continue

            # Check if we've already processed this pair
            pair_key = frozenset({correction1, correction2})
            if pair_key in processed_pairs:
                continue
            processed_pairs.add(pair_key)

            # Process conflict pair
            result, conflict_pair = process_conflict_pair(
                correction1,
                correction2,
                shorter_typo,
                longer_typo,
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
                all_corrections_to_remove.append((correction_to_remove, reason))
                if conflict_pair is not None:
                    removed_correction, conflicting_correction = conflict_pair
                    all_conflict_pairs[removed_correction] = conflicting_correction
                    corrections_to_remove_set.add(correction_to_remove)
