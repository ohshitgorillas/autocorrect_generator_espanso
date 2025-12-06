"""Pattern prefix index helpers for DictionaryState.

This module provides helper functions for managing the pattern prefix index
used for fast pattern coverage checks.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from entroppy.core.types import Correction


def update_pattern_prefix_index_add(
    pattern_prefix_index: dict[str, set["Correction"]], pattern: "Correction"
) -> None:
    """Update pattern prefix index when adding a pattern.

    Args:
        pattern_prefix_index: The prefix index dictionary
        pattern: The pattern being added
    """
    pattern_typo = pattern[0]
    if len(pattern_typo) >= 3:
        prefix = pattern_typo[:3]
        pattern_prefix_index[prefix].add(pattern)


def update_pattern_prefix_index_remove(
    pattern_prefix_index: dict[str, set["Correction"]], pattern: "Correction"
) -> None:
    """Update pattern prefix index when removing a pattern.

    Args:
        pattern_prefix_index: The prefix index dictionary
        pattern: The pattern being removed
    """
    pattern_typo = pattern[0]
    if len(pattern_typo) >= 3:
        prefix = pattern_typo[:3]
        pattern_prefix_index[prefix].discard(pattern)
        # Clean up empty prefix entries
        if not pattern_prefix_index[prefix]:
            del pattern_prefix_index[prefix]
