"""Pattern validation coordination functions."""

from collections import defaultdict
from typing import TYPE_CHECKING, Callable

from loguru import logger

from entroppy.core.boundaries import BoundaryIndex, BoundaryType
from entroppy.core.patterns.extraction import find_prefix_patterns, find_suffix_patterns
from entroppy.core.patterns.indexes import CorrectionIndex, SourceWordIndex, ValidationIndexes
from entroppy.core.types import Correction, MatchDirection

if TYPE_CHECKING:
    from entroppy.utils.debug import DebugTypoMatcher


def build_validation_indexes(
    validation_set: set[str],
    source_words: set[str],
    match_direction: MatchDirection,
    corrections: list[Correction],
) -> ValidationIndexes:
    """Build all validation indexes needed for pattern validation.

    Args:
        validation_set: Set of valid words
        source_words: Set of source words
        match_direction: Platform match direction
        corrections: List of corrections to analyze

    Returns:
        ValidationIndexes containing all built indexes
    """
    return ValidationIndexes(
        validation_index=BoundaryIndex(validation_set),
        source_word_index=SourceWordIndex(source_words, match_direction),
        correction_index=CorrectionIndex(corrections),
    )


def extract_debug_typos(
    debug_typo_matcher: "DebugTypoMatcher | None",
) -> tuple[set[str], set[str]] | None:
    """Extract debug typos sets from debug typo matcher.

    Args:
        debug_typo_matcher: Matcher for debug typos (with wildcards/boundaries)

    Returns:
        Tuple of (exact_patterns, wildcard_patterns) or None if no matcher provided.
        exact_patterns: Patterns to match exactly (no wildcards)
        wildcard_patterns: Core patterns from wildcard patterns (for substring matching)
    """
    if debug_typo_matcher:
        # Extract exact patterns (for exact matching)
        exact_patterns = set(debug_typo_matcher.exact_patterns)

        # Extract wildcard pattern cores (for substring matching)
        # Get cores from all wildcard patterns (remove * and boundary markers)
        wildcard_patterns = set()
        for pattern in (
            debug_typo_matcher.wildcard_originals
            + debug_typo_matcher.left_wildcard_originals
            + debug_typo_matcher.right_wildcard_originals
            + debug_typo_matcher.both_wildcard_originals
        ):
            # Remove boundary markers and wildcards to get core pattern
            core = pattern.strip(":").replace("*", "")
            if core:  # Only add non-empty cores
                wildcard_patterns.add(core)

        return (exact_patterns, wildcard_patterns)
    return None


def extract_and_merge_patterns(
    corrections: list[Correction],
    debug_typos_exact: set[str],
    debug_typos_wildcard: set[str],
    verbose: bool,
    is_in_graveyard: Callable[[str, str, BoundaryType], bool] | None = None,
    pattern_cache: (
        dict[
            tuple[str, str, BoundaryType, bool],
            list[tuple[str, str, BoundaryType, int]],
        ]
        | None
    ) = None,
) -> dict[tuple[str, str, BoundaryType], list[Correction]]:
    """Extract prefix and suffix patterns and merge them.

    Args:
        corrections: List of corrections to analyze
        debug_typos_exact: Set of exact debug typo patterns (for exact matching)
        debug_typos_wildcard: Set of wildcard debug typo pattern cores (for substring matching)
        verbose: Whether to print verbose output
        is_in_graveyard: Optional function to check if a pattern is in graveyard
            (prevents infinite loops by skipping already-rejected patterns)
        pattern_cache: Optional cache for pattern extraction results

    Returns:
        Dictionary mapping pattern keys to their occurrences
    """
    # Combine for backward compatibility with existing pattern extraction functions
    debug_typos_set = (
        debug_typos_exact | debug_typos_wildcard
        if (debug_typos_exact or debug_typos_wildcard)
        else None
    )

    # Extract BOTH prefix and suffix patterns
    # Both types are useful regardless of match direction:
    # - Prefix patterns: match at start of words (e.g., "teh" → "the")
    # - Suffix patterns: match at end of words (e.g., "toin" → "tion")
    prefix_patterns = find_prefix_patterns(
        corrections,
        debug_typos=debug_typos_set,
        debug_typos_exact=debug_typos_exact,
        debug_typos_wildcard=debug_typos_wildcard,
        verbose=verbose,
        is_in_graveyard=is_in_graveyard,
        pattern_cache=pattern_cache,
    )
    suffix_patterns = find_suffix_patterns(
        corrections,
        debug_typos=debug_typos_set,
        debug_typos_exact=debug_typos_exact,
        debug_typos_wildcard=debug_typos_wildcard,
        verbose=verbose,
        is_in_graveyard=is_in_graveyard,
        pattern_cache=pattern_cache,
    )

    # Combine both pattern types into single dict
    # If same pattern key exists in both, merge the occurrences
    found_patterns = defaultdict(list)
    for pattern_key, occurrences in prefix_patterns.items():
        found_patterns[pattern_key].extend(occurrences)
    for pattern_key, occurrences in suffix_patterns.items():
        # Merge occurrences if pattern already exists, otherwise add new
        if pattern_key in found_patterns:
            # Deduplicate: same correction might appear in both prefix and suffix patterns
            existing_typos = set(found_patterns[pattern_key])
            for occ in occurrences:
                if occ not in existing_typos:
                    found_patterns[pattern_key].append(occ)
        else:
            found_patterns[pattern_key].extend(occurrences)

    if verbose:
        logger.info(
            f"Found {len(prefix_patterns)} prefix and {len(suffix_patterns)} "
            f"suffix pattern candidates ({len(found_patterns)} unique patterns)..."
        )
        logger.info("Generalizing patterns...")

    return found_patterns
