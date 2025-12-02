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


def _update_patterns_from_blocked_corrections(
    patterns: list[Correction],
    pattern_replacements: dict[Correction, list[Correction]],
    final_corrections: list[Correction],
    removed_corrections: list[tuple[str, str, str, str, BoundaryType]],
):
    """Update patterns based on corrections that were blocked.

    When a shorter correction blocks a longer one (substring conflict),
    the shorter correction is effectively a pattern that eliminates the longer one.

    Args:
        patterns: Current list of patterns
        pattern_replacements: Current dictionary mapping patterns to their replacements
        final_corrections: Corrections that were kept (the blocking corrections)
        removed_corrections: List of (blocked_typo, blocked_word, blocking_typo,
            blocking_word, boundary)

    Returns:
        Tuple of (updated_patterns, updated_pattern_replacements)
    """
    updated_patterns = list(patterns)
    updated_replacements = dict(pattern_replacements)

    # Track which corrections are already patterns
    pattern_set = set(updated_patterns)

    # Build a map of blocking corrections to find their boundaries
    blocking_corrections_map = {}
    for typo, word, boundary in final_corrections:
        blocking_corrections_map[(typo, word)] = boundary

    # Process removed corrections to identify blocking patterns
    for blocked_typo, blocked_word, blocking_typo, blocking_word, _ in removed_corrections:
        # Find the boundary of the blocking correction
        blocking_boundary = blocking_corrections_map.get((blocking_typo, blocking_word))
        if blocking_boundary is None:
            # Blocking correction not found, skip
            continue

        # BOTH boundary corrections can't block anything (they only match standalone words)
        if blocking_boundary == BoundaryType.BOTH:
            continue

        blocking_correction = (blocking_typo, blocking_word, blocking_boundary)
        blocked_correction = (blocked_typo, blocked_word, blocking_boundary)

        # Add blocking correction to patterns if not already there
        if blocking_correction not in pattern_set:
            updated_patterns.append(blocking_correction)
            pattern_set.add(blocking_correction)
            updated_replacements[blocking_correction] = []

        # Add blocked correction to pattern_replacements
        if blocking_correction in updated_replacements:
            if blocked_correction not in updated_replacements[blocking_correction]:
                updated_replacements[blocking_correction].append(blocked_correction)

    return updated_patterns, updated_replacements


def update_patterns_from_conflicts(
    patterns: list[Correction],
    pattern_replacements: dict[Correction, list[Correction]],
    filtered_corrections: list[Correction],
    conflict_tuples: list[tuple[str, str, str, str, BoundaryType]],
):
    """Update patterns based on conflict tuples from filtering.

    Universal function to update patterns when conflicts are detected.
    Conflict tuples are: (blocked_typo, blocked_word, blocking_typo, blocking_word, boundary)

    Note: Corrections with BOTH boundaries are skipped because they can't block other corrections.

    Args:
        patterns: Current list of patterns
        pattern_replacements: Current dictionary mapping patterns to their replacements
        filtered_corrections: Corrections that were kept after filtering (the blocking corrections)
        conflict_tuples: List of conflict tuples from filtering

    Returns:
        Tuple of (updated_patterns, updated_pattern_replacements)
    """
    updated_patterns = list(patterns)
    updated_replacements = dict(pattern_replacements)

    # Track which corrections are already patterns
    pattern_set = set(updated_patterns)

    # Build a map of blocking corrections to find their boundaries
    blocking_corrections_map = {}
    for typo, word, boundary in filtered_corrections:
        blocking_corrections_map[(typo, word)] = boundary

    # Process conflicts: (blocked_typo, blocked_word, blocking_typo, blocking_word, boundary)
    for blocked_typo, blocked_word, blocking_typo, blocking_word, _ in conflict_tuples:
        # blocking_typo blocks blocked_typo, so blocking_typo is a pattern
        blocking_boundary = blocking_corrections_map.get((blocking_typo, blocking_word))
        if blocking_boundary is None:
            # Blocking correction not in final list, skip
            continue

        # BOTH boundary corrections can't block anything (they only match standalone words)
        if blocking_boundary == BoundaryType.BOTH:
            continue

        blocking_correction = (blocking_typo, blocking_word, blocking_boundary)
        blocked_correction = (blocked_typo, blocked_word, blocking_boundary)

        # Add blocking correction to patterns if not already there
        if blocking_correction not in pattern_set:
            updated_patterns.append(blocking_correction)
            pattern_set.add(blocking_correction)
            updated_replacements[blocking_correction] = []

        # Add blocked correction to pattern_replacements
        if blocking_correction in updated_replacements:
            if blocked_correction not in updated_replacements[blocking_correction]:
                updated_replacements[blocking_correction].append(blocked_correction)

    return updated_patterns, updated_replacements


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

    # Build blocking map during conflict removal for performance optimization
    # Always collect it since we need it for pattern updates
    final_corrections, blocking_map = remove_substring_conflicts(
        pattern_result.corrections,
        verbose,
        debug_words,
        debug_typo_matcher,
        collect_blocking_map=True,
    )

    conflicts_removed = pre_conflict_count - len(final_corrections)

    # Use blocking map instead of linear search (performance optimization)
    # Always build removed_corrections list for pattern updates, but use blocking map for efficiency
    if conflicts_removed > 0:
        final_set = set(final_corrections)
        removed = [c for c in pattern_result.corrections if c not in final_set]

        if verbose and collect_details:
            logger.info(f"  Building conflict details for {len(removed)} removed conflicts...")

        corrections_iter = removed
        if verbose and collect_details and len(removed) > 100:
            corrections_iter = tqdm(
                removed,
                desc="Building conflict details",
                unit="conflict",
            )

        # Use pre-computed blocking map instead of linear search
        for blocked_correction in corrections_iter:
            typo, word, boundary = blocked_correction
            blocking_correction = blocking_map.get(blocked_correction)
            if blocking_correction is not None:
                blocking_typo, blocking_word, _ = blocking_correction
            else:
                # Fallback to linear search if not in map (shouldn't happen, but safe)
                blocking_typo, blocking_word = _find_blocking_typo(
                    typo, word, boundary, final_corrections
                )
            removed_corrections.append((typo, word, blocking_typo, blocking_word, boundary))

    # Update patterns: when a shorter correction blocks a longer one, it's a pattern
    if removed_corrections:
        updated_patterns, updated_replacements = _update_patterns_from_blocked_corrections(
            pattern_result.patterns,
            pattern_result.pattern_replacements,
            final_corrections,
            removed_corrections,
        )
        pattern_result.patterns = updated_patterns
        pattern_result.pattern_replacements = updated_replacements

    if verbose and conflicts_removed > 0:
        logger.info(f"  Removed {conflicts_removed} typos due to substring conflicts")

    elapsed_time = time.time() - start_time

    return ConflictRemovalResult(
        corrections=final_corrections,
        removed_corrections=removed_corrections,
        conflicts_removed=conflicts_removed,
        elapsed_time=elapsed_time,
    )
