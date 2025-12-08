"""Helper functions for conflict removal pass."""

from collections import defaultdict

from entroppy.core import BoundaryType
from entroppy.resolution.conflicts import build_typo_index, get_detector_for_boundary


def process_conflict_batch_worker(
    boundary: BoundaryType,
    corrections: list[tuple[str, str, BoundaryType]],
) -> tuple[
    list[tuple[str, str, BoundaryType]],  # blocked corrections
    list[tuple[str, str, BoundaryType, str]],  # graveyard entries (typo, word, boundary, blocker)
]:
    """Worker function to process a batch of corrections for conflict detection.

    Args:
        boundary: The boundary type for this batch
        corrections: List of corrections to process

    Returns:
        Tuple of (blocked_corrections, graveyard_entries)
        - blocked_corrections: List of (typo, word, boundary) tuples to remove
        - graveyard_entries: List of (typo, word, boundary, blocker_typo) tuples
    """
    if not corrections:
        return [], []

    # Get the appropriate conflict detector for this boundary
    detector = get_detector_for_boundary(boundary)

    # Use existing build_typo_index function to avoid code duplication
    # Pass empty debug sets since we don't need debug logging in workers
    # pylint: disable=duplicate-code
    # Acceptable pattern: This is a function call to build_typo_index with standard parameters.
    # The similar code in conflicts.py calls the same function with the same parameters.
    # This is expected when both places need to build typo indexes for conflict detection.
    typos_to_remove, blocking_map = build_typo_index(
        corrections,
        detector,
        boundary,
        debug_words=set(),
        debug_typo_matcher=None,
        collect_blocking_map=True,
    )

    # Build lookup map from typo to full correction
    typo_to_correction = {c[0]: c for c in corrections}

    # Build return lists
    blocked_corrections = [typo_to_correction[typo] for typo in typos_to_remove]
    graveyard_entries = [
        (
            typo,
            typo_to_correction[typo][1],  # word
            boundary,
            blocking_map[typo_to_correction[typo]][
                0
            ],  # blocker_typo (first element of blocking correction)
        )
        for typo in typos_to_remove
        if typo_to_correction[typo] in blocking_map
    ]

    return blocked_corrections, graveyard_entries


def find_blocker_typo(
    correction: tuple[str, str, BoundaryType],
    graveyard_entries: list[tuple[str, str, BoundaryType, str]],
) -> str | None:
    """Find the blocker typo for a correction from graveyard entries.

    Args:
        correction: The correction tuple (typo, word, boundary)
        graveyard_entries: List of graveyard entries

    Returns:
        The blocker typo string, or None if not found
    """
    for typo, w, b, bt in graveyard_entries:
        if (typo, w, b) == correction:
            return bt
    return None


def shard_large_group(
    corrections: list[tuple[str, str, BoundaryType]],
) -> list[list[tuple[str, str, BoundaryType]]]:
    """Shard a large group of corrections by first character.

    Args:
        corrections: List of corrections to shard

    Returns:
        List of sharded correction lists
    """
    sharded = defaultdict(list)
    for correction in corrections:
        typo = correction[0]
        if typo:
            first_char = typo[0].lower()
            sharded[first_char].append(correction)
        else:
            # Empty typos go to a special shard
            sharded[""].append(correction)

    return [shard for shard in sharded.values() if shard]
