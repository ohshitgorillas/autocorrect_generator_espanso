"""Platform substring conflict detection logic.

This module contains the core detection algorithms for finding cross-boundary
substring conflicts in platform-formatted typo strings.
"""

from collections import defaultdict
from multiprocessing import Pool
from typing import TYPE_CHECKING

from entroppy.core.boundaries import BoundaryIndex, BoundaryType
from entroppy.core.types import MatchDirection
from entroppy.resolution.platform_conflicts import parallel
from entroppy.resolution.platform_conflicts.resolution import process_conflict_pair

if TYPE_CHECKING:
    from tqdm import tqdm

    from entroppy.utils.debug import DebugTypoMatcher


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
        int,
        list[tuple[str, list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]]]],
    ] = defaultdict(list)

    for formatted_typo, corrections in formatted_to_corrections.items():
        length_buckets[len(formatted_typo)].append((formatted_typo, corrections))

    return length_buckets


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
    corrections_to_remove: list[tuple[tuple[str, str, BoundaryType], str]] = []
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
                    all_marked = _process_conflict_combinations(
                        shorter_corrections,
                        corrections_for_typo,
                        shorter_formatted_typo,
                        formatted_typo,
                        match_direction,
                        processed_pairs,
                        corrections_to_remove_set,
                        corrections_to_remove,
                        conflict_pairs,
                        validation_index,
                        source_index,
                        debug_words,
                        debug_typo_matcher,
                    )
                    if all_marked:
                        break

    return corrections_to_remove, conflict_pairs


def _process_conflict_combinations(
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
    """Process all combinations of corrections, returning True if all are marked for removal."""
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
                    corrections_to_remove_set.add(correction_to_remove)

            # Break early if all corrections for this formatted typo are marked
            if all(c in corrections_to_remove_set for c, _, _ in corrections_for_typo):
                return True

    return False


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
    num_workers: int = 1,
) -> tuple[
    list[tuple[tuple[str, str, BoundaryType], str]],
    dict[tuple[str, str, BoundaryType], tuple[str, str, BoundaryType]],
]:
    """Check conflicts for a bucket against accumulated shorter typos.

    Uses a two-phase approach when parallelization is enabled:
    1. Parallel detection (read-only): Find all conflicts without modifying state
    2. Sequential resolution: Apply deterministic rules to resolve conflicts

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
        num_workers: Number of worker processes to use (1 = sequential, >1 = parallel)

    Returns:
        Tuple of:
        - corrections_to_remove: List of (correction, reason) tuples
        - conflict_pairs: Dict mapping removed_correction -> conflicting_correction
    """
    # Determine if we should use parallel processing
    use_parallel = num_workers > 1 and len(current_bucket) >= 100

    # Initialize return values
    corrections_to_remove: list[tuple[tuple[str, str, BoundaryType], str]] = []
    conflict_pairs: dict[tuple[str, str, BoundaryType], tuple[str, str, BoundaryType]] = {}

    if use_parallel:
        # Phase 1: Parallel detection (read-only)
        chunks = parallel.divide_into_chunks(current_bucket, num_workers)

        with Pool(processes=num_workers) as pool:
            all_conflicts_lists = pool.starmap(
                parallel.detect_conflicts_for_chunk,
                [(chunk, candidates_by_char) for chunk in chunks],
            )

        # Flatten all conflicts from all workers
        all_conflicts = []
        for conflicts_list in all_conflicts_lists:
            all_conflicts.extend(conflicts_list)

        # Update progress bar
        if progress_bar is not None:
            progress_bar.update(len(current_bucket))

        # Phase 2: Sequential resolution (deterministic)
        corrections_to_remove, conflict_pairs = parallel.resolve_conflicts_sequential(
            all_conflicts,
            match_direction,
            processed_pairs,
            corrections_to_remove_set,
            validation_index,
            source_index,
            debug_words,
            debug_typo_matcher,
        )
    else:
        # Sequential processing (original algorithm)

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
    for formatted_typo, corrections_for_typo in current_bucket:
        index_key = formatted_typo[0] if formatted_typo else ""
        candidates_by_char[index_key].append((formatted_typo, corrections_for_typo))

    return corrections_to_remove, conflict_pairs
