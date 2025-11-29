"""Stage 4: Pattern generalization."""

import sys
import time
from collections import defaultdict

from ..config import Config, Correction
from ..patterns import generalize_patterns
from ..processing import resolve_collisions, remove_substring_conflicts
from .data_models import (
    DictionaryData,
    CollisionResolutionResult,
    PatternGeneralizationResult,
)


def _filter_cross_boundary_conflicts(
    patterns: list[Correction],
    final_corrections: list[Correction],
    pattern_replacements: dict[Correction, list[Correction]],
    rejected_patterns: list[tuple[str, str, list[str]]],
    verbose: bool = False,
) -> tuple[list[Correction], list[Correction]]:
    """Filter out patterns that conflict with direct corrections across boundaries.

    A pattern conflicts if its (typo, word) pair already exists in final_corrections,
    regardless of boundary type. When a conflict is detected, the pattern is rejected
    and its replacements are restored to final_corrections.

    Args:
        patterns: List of patterns to check for conflicts
        final_corrections: List of direct corrections (non-patterns)
        pattern_replacements: Map of patterns to the corrections they replaced
        rejected_patterns: List to append rejected patterns to
        verbose: Whether to print verbose output

    Returns:
        Tuple of (final_corrections with restored replacements, safe patterns)
    """
    # Build index of (typo, word) pairs from direct corrections
    direct_pairs = {(typo, word) for typo, word, _ in final_corrections}

    # Check each pattern for conflicts and separate into safe/conflicting
    safe_patterns = []
    conflicting_patterns = []

    for pattern in patterns:
        typo, word, boundary = pattern
        if (typo, word) in direct_pairs:
            conflicting_patterns.append(pattern)
        else:
            safe_patterns.append(pattern)

    # Restore replacements for conflicting patterns
    for pattern in conflicting_patterns:
        if pattern in pattern_replacements:
            final_corrections.extend(pattern_replacements[pattern])
        # Add to rejected patterns with reason
        typo, word, _ = pattern
        rejected_patterns.append(
            (typo, word, ["Cross-boundary conflict with direct correction"])
        )

    # Verbose output for cross-boundary conflicts
    if verbose and conflicting_patterns:
        print(
            f"# Rejected {len(conflicting_patterns)} patterns due to "
            f"cross-boundary conflicts with direct corrections.",
            file=sys.stderr,
        )
        # Show first few examples
        for pattern in conflicting_patterns[:3]:
            typo, word, boundary = pattern
            print(
                f"#   - Pattern ({typo}, {word}, {boundary.value}) "
                f"conflicts with direct correction",
                file=sys.stderr,
            )
        if len(conflicting_patterns) > 3:
            print(f"#   ... and {len(conflicting_patterns) - 3} more", file=sys.stderr)

    return final_corrections, safe_patterns


def generalize_typo_patterns(
    collision_result: CollisionResolutionResult,
    dict_data: DictionaryData,
    config: Config,
    match_direction,
    verbose: bool = False,
) -> PatternGeneralizationResult:
    """Generalize patterns from corrections.

    Args:
        collision_result: Result from collision resolution stage
        dict_data: Dictionary data from loading stage
        config: Configuration object
        match_direction: Match direction enum from platform constraints
        verbose: Whether to print verbose output

    Returns:
        PatternGeneralizationResult containing corrections with patterns
    """
    start_time = time.time()

    # Generalize patterns
    (
        patterns,
        to_remove,
        pattern_replacements,
        rejected_patterns,
    ) = generalize_patterns(
        collision_result.corrections,
        dict_data.filtered_validation_set,
        dict_data.source_words_set,
        config.min_typo_length,
        match_direction,
        verbose,
    )

    # Remove original corrections that have been generalized
    pre_generalization_count = len(collision_result.corrections)
    final_corrections = [c for c in collision_result.corrections if c not in to_remove]
    removed_count = pre_generalization_count - len(final_corrections)

    # Patterns need collision resolution - multiple words might generate same pattern
    pattern_typo_map = defaultdict(list)
    for typo, word, boundary in patterns:
        pattern_typo_map[typo].append((word, boundary))

    # Resolve collisions for patterns
    resolved_patterns, _, _, _ = resolve_collisions(
        pattern_typo_map,
        config.freq_ratio,
        config.min_typo_length,
        config.min_word_length,
        dict_data.user_words_set,
        dict_data.exclusion_matcher,
    )

    # Remove substring conflicts from patterns
    # Patterns can also have redundancies (e.g., "lectiona" is redundant if "ectiona" exists)
    resolved_patterns = remove_substring_conflicts(resolved_patterns, verbose=False)

    # Cross-boundary deduplication: filter patterns that conflict with direct corrections
    final_corrections, safe_patterns = _filter_cross_boundary_conflicts(
        resolved_patterns,
        final_corrections,
        pattern_replacements,
        rejected_patterns,
        verbose,
    )

    # Add only safe patterns to final corrections
    final_corrections.extend(safe_patterns)

    if verbose:
        if patterns:
            print(
                f"# Generalized {len(resolved_patterns)} patterns, "
                f"removing {removed_count} specific corrections.",
                file=sys.stderr,
            )
        print(
            f"# After pattern generalization: {len(final_corrections)} entries",
            file=sys.stderr,
        )

    elapsed_time = time.time() - start_time

    return PatternGeneralizationResult(
        corrections=final_corrections,
        patterns=resolved_patterns,
        removed_count=removed_count,
        pattern_replacements=pattern_replacements,
        rejected_patterns=rejected_patterns,
        elapsed_time=elapsed_time,
    )
