"""Stage 5: Conflict removal."""

import time
from typing import TYPE_CHECKING

from loguru import logger
from tqdm import tqdm

from entroppy.processing.stages.data_models import (
    PatternGeneralizationResult,
    ConflictRemovalResult,
)
from entroppy.core import BoundaryType, Correction
from entroppy.resolution import remove_substring_conflicts

if TYPE_CHECKING:
    from ...utils import DebugTypoMatcher


def _find_blocking_typo(
    typo: str,
    word: str,
    boundary: BoundaryType,
    final_corrections: list[Correction],
) -> tuple[str, str]:
    """Find the typo and word that block a given correction.

    Args:
        typo: The typo that was blocked
        word: The word it corrects to
        boundary: The boundary type
        final_corrections: List of corrections that were kept

    Returns:
        Tuple of (blocking_typo, blocking_word)
    """
    blocking_typo = "unknown"
    blocking_word = "unknown"

    for other_typo, other_word, other_boundary in final_corrections:
        if other_boundary != boundary or typo == other_typo:
            continue

        # For RIGHT boundaries (suffixes), check if typo ends with shorter typo
        # For other boundaries, check if typo starts with shorter typo
        if boundary == BoundaryType.RIGHT:
            if typo.endswith(other_typo):
                # Validate: check if this actually would have caused the blocking
                remaining_prefix = typo[: -len(other_typo)]
                expected_result = remaining_prefix + other_word
                if expected_result == word:
                    blocking_typo = other_typo
                    blocking_word = other_word
                    break
        else:
            if typo.startswith(other_typo):
                # Validate: check if this actually would have caused the blocking
                remaining_suffix = typo[len(other_typo) :]
                expected_result = other_word + remaining_suffix
                if expected_result == word:
                    blocking_typo = other_typo
                    blocking_word = other_word
                    break

    return blocking_typo, blocking_word


def remove_typo_conflicts(
    pattern_result: PatternGeneralizationResult,
    verbose: bool = False,
    collect_details: bool = False,
    debug_words: set[str] | None = None,
    debug_typo_matcher: "DebugTypoMatcher | None" = None,
) -> ConflictRemovalResult:
    """Remove substring conflicts from corrections.

    Args:
        pattern_result: Result from pattern generalization stage
        verbose: Whether to print verbose output
        collect_details: Whether to collect detailed information about removed conflicts
        debug_words: Set of words to debug (exact matches)
        debug_typo_matcher: Matcher for debug typos (with wildcards/boundaries)

    Returns:
        ConflictRemovalResult containing final corrections and conflict statistics
    """
    if debug_words is None:
        debug_words = set()

    start_time = time.time()

    pre_conflict_count = len(pattern_result.corrections)

    # Track which corrections are removed if needed
    removed_corrections = []
    if collect_details:
        pre_conflict_corrections = {c: c for c in pattern_result.corrections}

    final_corrections = remove_substring_conflicts(
        pattern_result.corrections, verbose, debug_words, debug_typo_matcher
    )

    conflicts_removed = pre_conflict_count - len(final_corrections)

    # Analyze removed corrections if details are requested
    if collect_details and conflicts_removed > 0:
        final_set = set(final_corrections)
        removed = [c for c in pre_conflict_corrections.values() if c not in final_set]

        if removed and verbose:
            logger.info(f"Analyzing {len(removed)} removed conflicts for report...")

        corrections_iter = removed
        if verbose and len(removed) > 100:
            corrections_iter = tqdm(
                removed,
                desc="Analyzing removed conflicts",
                unit="conflict",
            )

        for typo, word, boundary in corrections_iter:
            blocking_typo, blocking_word = _find_blocking_typo(
                typo, word, boundary, final_corrections
            )
            removed_corrections.append((typo, word, blocking_typo, blocking_word, boundary))

    if verbose and conflicts_removed > 0:
        logger.info(f"# Removed {conflicts_removed} typos due to substring conflicts")

    elapsed_time = time.time() - start_time

    return ConflictRemovalResult(
        corrections=final_corrections,
        removed_corrections=removed_corrections,
        conflicts_removed=conflicts_removed,
        elapsed_time=elapsed_time,
    )
