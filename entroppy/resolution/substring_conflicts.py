"""Substring conflict removal for collision resolution."""

from typing import TYPE_CHECKING

from tqdm import tqdm

from entroppy.core import Correction
from entroppy.core.boundaries import BoundaryType

from .conflicts import resolve_conflicts_for_group

if TYPE_CHECKING:
    from entroppy.utils.debug import DebugTypoMatcher


def remove_substring_conflicts(
    corrections: list[Correction],
    verbose: bool = False,
    debug_words: set[str] | None = None,
    debug_typo_matcher: "DebugTypoMatcher | None" = None,
    collect_blocking_map: bool = False,
) -> tuple[list[Correction], dict[Correction, Correction]]:
    """Remove corrections where one typo is a substring of another WITH THE SAME BOUNDARY.

    When Espanso sees a typo, it triggers on the first (shortest) match from left to right.

    Example 1: If we have 'teh' → 'the' and 'tehir' → 'their' (both no boundary):
    - When typing "tehir", Espanso sees "teh" first and corrects to "the"
    - User continues typing "ir", getting "their"
    - The "tehir" correction is unreachable, so remove it

    Example 2: If we have 'toin' (no boundary) → 'ton' and 'toin' (right_word) → 'tion':
    - These have DIFFERENT boundaries, so they DON'T conflict
    - 'toin' (no boundary) matches standalone "toin"
    - 'toin' (right_word) matches as a suffix in "*toin"
    - Both can coexist

    Example 3: If we have 'toin' → 'tion' and 'atoin' → 'ation' (both RIGHT):
    - Both would match at end of "information"
    - "toin" makes "atoin" redundant—the "a" is useless
    - Remove "atoin" in favor of shorter "toin"

    Args:
        corrections: List of corrections to check for conflicts
        verbose: Whether to print verbose output
        debug_words: Set of words to debug (exact matches)
        debug_typo_matcher: Matcher for debug typos (with wildcards/boundaries)
        collect_blocking_map: Whether to build blocking map (for performance optimization)

    Returns:
        Tuple of (list of corrections with conflicts removed, blocking map)
    """
    # Group by boundary type - process each separately
    by_boundary: dict[BoundaryType, list[Correction]] = {}
    for correction in corrections:
        _, _, boundary = correction
        if boundary not in by_boundary:
            by_boundary[boundary] = []
        by_boundary[boundary].append(correction)

    # Process each boundary group
    final_corrections = []
    blocking_map: dict[Correction, Correction] = {}

    if verbose and len(by_boundary) > 1:
        groups_iter: list[tuple[BoundaryType, list[Correction]]] = list(
            tqdm(
                by_boundary.items(),
                desc="Removing conflicts",
                unit="boundary",
                total=len(by_boundary),
            )
        )
    else:
        groups_iter = list(by_boundary.items())

    for boundary, group in groups_iter:
        group_final, group_blocking_map = resolve_conflicts_for_group(
            group, boundary, debug_words, debug_typo_matcher, collect_blocking_map
        )
        final_corrections.extend(group_final)
        if collect_blocking_map:
            blocking_map.update(group_blocking_map)

    return final_corrections, blocking_map
