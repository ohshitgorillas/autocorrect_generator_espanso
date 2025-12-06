"""Main pattern finding functions."""

from collections import defaultdict
from typing import Callable

from loguru import logger
from tqdm import tqdm

from entroppy.core.boundaries import BoundaryType
from entroppy.core.types import Correction

from .filters import (
    _filter_corrections_by_boundary,
    _find_common_patterns,
    _log_debug_summary,
    _setup_debug_tracking,
)
from .matcher import _extract_patterns_from_correction, _process_cached_patterns


def _find_patterns(
    corrections: list[Correction],
    boundary_type: BoundaryType,
    is_suffix: bool,
    debug_typos: set[str] | None = None,
    verbose: bool = False,
    is_in_graveyard: Callable[[str, str, BoundaryType], bool] | None = None,
    pattern_cache: (
        dict[
            tuple[str, str, BoundaryType, bool],
            list[tuple[str, str, BoundaryType, int]],
        ]
        | None
    ) = None,
    debug_typos_exact: set[str] | None = None,
    debug_typos_wildcard: set[str] | None = None,
) -> dict[tuple[str, str, BoundaryType], list[tuple[str, str, BoundaryType]]]:
    """Find common patterns (prefix or suffix) in corrections.

    Optimized implementation that extracts all possible patterns from each correction
    in a single pass, then groups by pattern to find common ones.

    Args:
        corrections: List of corrections to analyze
        boundary_type: Boundary type to filter by (LEFT for prefix, RIGHT for suffix)
        is_suffix: True for suffix patterns, False for prefix patterns
        debug_typos: Optional set of typo strings to debug (for logging)
        verbose: Whether to show progress bar
        is_in_graveyard: Optional function to check if pattern is in graveyard
        pattern_cache: Optional cache for pattern extraction results
        debug_typos_exact: Optional set of exact debug typo patterns (for exact matching)
        debug_typos_wildcard: Optional set of wildcard debug typo pattern cores
            (for substring matching)

    Returns:
        Dict mapping (typo_pattern, word_pattern, boundary) to list of
        (full_typo, full_word, original_boundary) tuples that match this pattern.
    """
    debug_enabled = debug_typos is not None and len(debug_typos) > 0

    # Filter corrections by boundary type
    filtered_corrections = _filter_corrections_by_boundary(corrections, boundary_type)

    if not filtered_corrections:
        return defaultdict(list)

    if debug_enabled:
        logger.debug(
            f"[PATTERN EXTRACTION] Processing {len(filtered_corrections)} corrections "
            f"with boundary {boundary_type.value} (suffix={is_suffix})"
        )

    # Group directly by (typo_pattern, word_pattern, boundary) across ALL corrections
    # This finds patterns even when corrections have different "other parts"
    # Example: "action" and "lection" both share pattern "tion" → "tion" despite different prefixes
    pattern_candidates: dict[tuple[str, str, BoundaryType], list[tuple[str, str, BoundaryType]]] = (
        defaultdict(list)
    )

    # Track debug info for specific typos
    debug_corrections = _setup_debug_tracking(
        filtered_corrections, debug_typos, debug_typos_exact, debug_typos_wildcard
    )

    # Optimized: Extract all valid patterns from each correction in a single pass
    if verbose:
        pattern_type = "suffix" if is_suffix else "prefix"
        corrections_iter: list[tuple[str, str, BoundaryType]] = list(
            tqdm(
                filtered_corrections,
                desc=f"    Extracting {pattern_type} patterns",
                unit="correction",
                leave=False,
            )
        )
    else:
        corrections_iter = filtered_corrections

    for typo, word, boundary in corrections_iter:
        is_debug = (typo, word, boundary) in debug_corrections

        # Extract patterns from this correction
        cached_patterns, _ = _extract_patterns_from_correction(
            typo=typo,
            word=word,
            boundary=boundary,
            is_suffix=is_suffix,
            is_debug=is_debug,
            pattern_cache=pattern_cache,
            debug_corrections=debug_corrections if is_debug else None,
        )

        # Process cached patterns, filtering by graveyard
        _process_cached_patterns(
            typo=typo,
            word=word,
            boundary=boundary,
            cached_patterns=cached_patterns,
            is_suffix=is_suffix,
            is_debug=is_debug,
            is_in_graveyard=is_in_graveyard,
            pattern_candidates=pattern_candidates,
            debug_corrections=debug_corrections if is_debug else None,
        )

    # Find common patterns (2+ occurrences)
    patterns = _find_common_patterns(
        pattern_candidates,
        debug_typos,
        debug_enabled,
        debug_typos_exact,
        debug_typos_wildcard,
    )

    # Log debug summary
    _log_debug_summary(
        pattern_candidates=pattern_candidates,
        patterns=patterns,
        debug_corrections=debug_corrections,
    )

    return patterns


def find_suffix_patterns(
    corrections: list[Correction],
    debug_typos: set[str] | None = None,
    verbose: bool = False,
    is_in_graveyard: Callable[[str, str, BoundaryType], bool] | None = None,
    pattern_cache: (
        dict[
            tuple[str, str, BoundaryType, bool],
            list[tuple[str, str, BoundaryType, int]],
        ]
        | None
    ) = None,
    debug_typos_exact: set[str] | None = None,
    debug_typos_wildcard: set[str] | None = None,
) -> dict[tuple[str, str, BoundaryType], list[tuple[str, str, BoundaryType]]]:
    """Find common suffix patterns (for RIGHT boundaries).

    Returns a dict mapping (typo_suffix, word_suffix, boundary) to list of
    (full_typo, full_word, original_boundary) tuples that match this pattern.

    Args:
        corrections: List of corrections to analyze
        debug_typos: Optional set of typo strings to debug (for logging)
        verbose: Whether to show progress bar
        is_in_graveyard: Optional function to check if pattern is in graveyard
        pattern_cache: Optional cache for pattern extraction results
        debug_typos_exact: Optional set of exact debug typo patterns
            (for exact matching)
        debug_typos_wildcard: Optional set of wildcard debug typo pattern cores
            (for substring matching)
    """
    return _find_patterns(
        corrections,
        BoundaryType.RIGHT,
        is_suffix=True,
        debug_typos=debug_typos,
        verbose=verbose,
        is_in_graveyard=is_in_graveyard,
        pattern_cache=pattern_cache,
        debug_typos_exact=debug_typos_exact,
        debug_typos_wildcard=debug_typos_wildcard,
    )


def find_prefix_patterns(
    corrections: list[Correction],
    debug_typos: set[str] | None = None,
    verbose: bool = False,
    is_in_graveyard: Callable[[str, str, BoundaryType], bool] | None = None,
    pattern_cache: (
        dict[
            tuple[str, str, BoundaryType, bool],
            list[tuple[str, str, BoundaryType, int]],
        ]
        | None
    ) = None,
    debug_typos_exact: set[str] | None = None,
    debug_typos_wildcard: set[str] | None = None,
) -> dict[tuple[str, str, BoundaryType], list[tuple[str, str, BoundaryType]]]:
    """Find common prefix patterns (for LEFT boundaries).

    Returns a dict mapping (typo_prefix, word_prefix, boundary) to list of
    (full_typo, full_word, original_boundary) tuples that match this pattern.

    Args:
        corrections: List of corrections to analyze
        debug_typos: Optional set of typo strings to debug (for logging)
        verbose: Whether to show progress bar
        is_in_graveyard: Optional function to check if pattern is in graveyard
        pattern_cache: Optional cache for pattern extraction results
        debug_typos_exact: Optional set of exact debug typo patterns
            (for exact matching)
        debug_typos_wildcard: Optional set of wildcard debug typo pattern cores
            (for substring matching)
    """
    return _find_patterns(
        corrections,
        BoundaryType.LEFT,
        is_suffix=False,
        debug_typos=debug_typos,
        verbose=verbose,
        is_in_graveyard=is_in_graveyard,
        pattern_cache=pattern_cache,
        debug_typos_exact=debug_typos_exact,
        debug_typos_wildcard=debug_typos_wildcard,
    )
