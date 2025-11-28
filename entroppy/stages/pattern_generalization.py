"""Stage 4: Pattern generalization."""

import sys
import time
from collections import defaultdict

from ..config import Config
from ..patterns import generalize_patterns
from ..processing import resolve_collisions, remove_substring_conflicts
from .data_models import (
    DictionaryData,
    CollisionResolutionResult,
    PatternGeneralizationResult,
)


def generalize_typo_patterns(
    collision_result: CollisionResolutionResult,
    dict_data: DictionaryData,
    config: Config,
    verbose: bool = False,
) -> PatternGeneralizationResult:
    """Generalize patterns from corrections.

    Args:
        collision_result: Result from collision resolution stage
        dict_data: Dictionary data from loading stage
        config: Configuration object
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

    # Add resolved patterns to final corrections
    final_corrections.extend(resolved_patterns)

    if verbose:
        if patterns:
            print(
                f"# Generalized {len(resolved_patterns)} patterns, removing {removed_count} specific corrections.",
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
