"""Boundary selection logic for collision resolution."""

from entroppy.core import BoundaryType
from entroppy.core.boundaries import BoundaryIndex, would_trigger_at_start, would_trigger_at_end
from .boundary_utils import choose_strictest_boundary


def choose_boundary_for_typo(
    typo: str,
    boundaries: list[BoundaryType],
    typo_substring_index: dict[str, dict[str, bool]],
    validation_set: set[str],
    source_words: set[str],
    validation_index: BoundaryIndex,
    source_index: BoundaryIndex,
) -> BoundaryType:
    """Choose boundary for a typo, checking if it appears in multiple positions.

    If the typo appears in multiple positions (prefix, middle, suffix) in other typos,
    and NONE boundary would be safe (no false triggers in validation or source words), use NONE.
    Otherwise, use the strictest boundary.

    Args:
        typo: The typo string
        boundaries: List of boundary types from different contexts
        typo_substring_index: Pre-computed index of substring relationships between typos
        validation_set: Set of validation words to check for false triggers
        source_words: Set of source words to check for false triggers
        validation_index: Boundary index for validation set
        source_index: Boundary index for source words

    Returns:
        The chosen boundary type
    """
    # Get pre-computed substring information from index
    substring_info = typo_substring_index.get(
        typo,
        {
            "appears_as_prefix": False,
            "appears_as_suffix": False,
            "appears_in_middle": False,
        },
    )

    appears_as_prefix = substring_info["appears_as_prefix"]
    appears_as_suffix = substring_info["appears_as_suffix"]
    appears_in_middle = substring_info["appears_in_middle"]

    # Count how many different positions it appears in
    position_count = sum([appears_as_prefix, appears_as_suffix, appears_in_middle])

    # If it appears in multiple positions in other typos, check if NONE is safe
    if position_count >= 2:
        # Check if NONE boundary would cause false triggers
        # A false trigger would occur if the typo appears as a prefix or suffix in validation/source words
        # (because then it would match at word boundaries when it shouldn't)
        # If it only appears in the middle of validation/source words, NONE is safe

        would_trigger_start = would_trigger_at_start(
            typo, validation_set, validation_index
        ) or would_trigger_at_start(typo, source_words, source_index)
        would_trigger_end = would_trigger_at_end(
            typo, validation_set, validation_index
        ) or would_trigger_at_end(typo, source_words, source_index)

        # If it doesn't trigger at start or end, NONE is safe
        if not would_trigger_start and not would_trigger_end:
            return BoundaryType.NONE

    # Otherwise, use strictest boundary
    return choose_strictest_boundary(boundaries)
