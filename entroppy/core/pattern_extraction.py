"""Pattern extraction from typo corrections."""

from collections import defaultdict
from typing import Callable

from loguru import logger
from tqdm import tqdm

from entroppy.core.boundaries import BoundaryType
from entroppy.core.types import Correction

# Minimum length for the non-pattern part when extracting patterns
# This prevents extracting nonsensical patterns that are too short
_MIN_OTHER_PART_LENGTH = 2


def _extract_pattern_parts(
    typo: str, word: str, length: int, is_suffix: bool
) -> tuple[str, str, str, str]:
    """Extract pattern parts from typo and word.

    Args:
        typo: The typo string
        word: The correct word string
        length: Length of pattern to extract
        is_suffix: True for suffix patterns, False for prefix patterns

    Returns:
        Tuple of (typo_pattern, word_pattern, other_part_typo, other_part_word)
    """
    if is_suffix:
        # Extract suffix patterns
        typo_pattern = typo[-length:]
        word_pattern = word[-length:]
        other_part_typo = typo[:-length]
        other_part_word = word[:-length]
    else:
        # Extract prefix patterns
        typo_pattern = typo[:length]
        word_pattern = word[:length]
        other_part_typo = typo[length:]
        other_part_word = word[length:]

    return typo_pattern, word_pattern, other_part_typo, other_part_word


def _filter_corrections_by_boundary(
    corrections: list[Correction],
    boundary_type: BoundaryType,
) -> list[Correction]:
    """Filter corrections by boundary type.

    For suffix patterns (RIGHT), include RIGHT and NONE boundaries.
    For prefix patterns (LEFT), include LEFT and NONE boundaries.

    Args:
        corrections: List of corrections to filter
        boundary_type: Boundary type to filter by

    Returns:
        Filtered list of corrections
    """
    return [
        (typo, word, boundary)
        for typo, word, boundary in corrections
        if boundary in (boundary_type, BoundaryType.NONE)
    ]


def _setup_debug_tracking(
    filtered_corrections: list[Correction],
    debug_typos: set[str] | None,
    debug_typos_exact: set[str] | None = None,
    debug_typos_wildcard: set[str] | None = None,
) -> dict[tuple[str, str, BoundaryType], list[tuple[int, str, str, str]]]:
    """Setup debug tracking for specific typos.

    Args:
        filtered_corrections: List of corrections to track
        debug_typos: Optional set of typo strings to debug (backward compatibility)
        debug_typos_exact: Optional set of exact debug typo patterns
            (for exact matching)
        debug_typos_wildcard: Optional set of wildcard debug typo pattern cores
            (for substring matching)

    Returns:
        Dict mapping (typo, word, boundary) to list of debug info
    """
    debug_corrections: dict[tuple[str, str, BoundaryType], list[tuple[int, str, str, str]]] = {}

    # Use new parameters if provided, otherwise fall back to old behavior for backward compatibility
    if debug_typos_exact is not None or debug_typos_wildcard is not None:
        exact_patterns = debug_typos_exact or set()
        wildcard_patterns = debug_typos_wildcard or set()

        for typo, word, boundary in filtered_corrections:
            typo_lower = typo.lower()
            # Check exact patterns (exact match)
            if any(typo_lower == pattern.lower() for pattern in exact_patterns):
                debug_corrections[(typo, word, boundary)] = []
            # Check wildcard patterns (substring match)
            elif any(pattern.lower() in typo_lower for pattern in wildcard_patterns):
                debug_corrections[(typo, word, boundary)] = []
    elif debug_typos is not None and len(debug_typos) > 0:
        # Backward compatibility: use substring matching for all patterns
        for typo, word, boundary in filtered_corrections:
            if any(debug_typo.lower() in typo.lower() for debug_typo in debug_typos):
                debug_corrections[(typo, word, boundary)] = []

    return debug_corrections


def _extract_patterns_from_correction(
    typo: str,
    word: str,
    boundary: BoundaryType,
    is_suffix: bool,
    is_debug: bool,
    pattern_cache: (
        dict[tuple[str, str, BoundaryType, bool], list[tuple[str, str, BoundaryType, int]]] | None
    ) = None,
    debug_corrections: (
        dict[tuple[str, str, BoundaryType], list[tuple[int, str, str, str]]] | None
    ) = None,
) -> tuple[list[tuple[str, str, BoundaryType, int]], bool]:
    """Extract all valid patterns from a single correction.

    Args:
        typo: The typo string
        word: The correct word string
        boundary: The boundary type
        is_suffix: True for suffix patterns, False for prefix patterns
        is_debug: Whether this correction is being debugged
        pattern_cache: Optional cache for pattern extraction results
        debug_corrections: Optional dict to populate with debug info

    Returns:
        Tuple of (list of extracted patterns, was_cache_hit)
        Patterns are tuples of (typo_pattern, word_pattern, boundary, length)
    """
    max_pattern_length = min(len(typo), len(word)) - _MIN_OTHER_PART_LENGTH

    if max_pattern_length < 2:
        return [], False

    if is_debug:
        logger.debug(
            f"[PATTERN EXTRACTION] Analyzing correction: '{typo}' → '{word}' "
            f"(boundary={boundary.value}, max_pattern_length={max_pattern_length})"
        )

    # Check cache first
    cache_key = (typo, word, boundary, is_suffix)
    cached_patterns = None
    was_cache_hit = False

    if pattern_cache is not None and cache_key in pattern_cache:
        cached_patterns = pattern_cache[cache_key]
        was_cache_hit = True
        if is_debug:
            logger.debug(f"  Using cached patterns: {len(cached_patterns)} patterns found")

    # Extract patterns if not cached
    if cached_patterns is None:
        cached_patterns = []
        # Extract all valid patterns at once by iterating through possible pattern lengths
        # Start from longest patterns (more specific) and work backwards
        for length in range(max_pattern_length, 1, -1):  # Start from longest, go down to 2
            typo_pattern, word_pattern, other_part_typo, other_part_word = _extract_pattern_parts(
                typo, word, length, is_suffix
            )

            if is_debug:
                logger.debug(
                    f"  Length {length}: pattern='{typo_pattern}'→'{word_pattern}', "
                    f"other_part='{other_part_typo}'→'{other_part_word}'"
                )

            # Skip if patterns are identical (useless pattern)
            if typo_pattern == word_pattern:
                if is_debug:
                    logger.debug("    SKIPPED - pattern identical (no change)")
                continue

            # Ensure the other parts match before considering a pattern valid
            if other_part_typo != other_part_word:
                if is_debug:
                    logger.debug(
                        f"    SKIPPED - other_part mismatch: "
                        f"'{other_part_typo}' != '{other_part_word}'"
                    )
                continue

            # Store pattern in cache (without graveyard filtering)
            cached_patterns.append((typo_pattern, word_pattern, boundary, length))

            if is_debug and debug_corrections is not None:
                debug_corrections[(typo, word, boundary)].append(
                    (length, typo_pattern, word_pattern, other_part_typo)
                )
                logger.debug(
                    f"    ✓ EXTRACTED - pattern '{typo_pattern}'→'{word_pattern}' "
                    f"(other_part='{other_part_typo}')"
                )

        # Store in cache for future iterations
        if pattern_cache is not None:
            pattern_cache[cache_key] = cached_patterns

    return cached_patterns, was_cache_hit


def _process_cached_patterns(
    typo: str,
    word: str,
    boundary: BoundaryType,
    cached_patterns: list[tuple[str, str, BoundaryType, int]],
    is_suffix: bool,
    is_debug: bool,
    is_in_graveyard: Callable[[str, str, BoundaryType], bool] | None,
    pattern_candidates: dict[tuple[str, str, BoundaryType], list[tuple[str, str, BoundaryType]]],
    debug_corrections: (
        dict[tuple[str, str, BoundaryType], list[tuple[int, str, str, str]]] | None
    ) = None,
) -> None:
    """Process cached patterns, filtering by graveyard and adding to candidates.

    Args:
        typo: The typo string
        word: The correct word string
        boundary: The boundary type
        cached_patterns: List of patterns from cache/extraction
        is_suffix: True for suffix patterns, False for prefix patterns
        is_debug: Whether this correction is being debugged
        is_in_graveyard: Optional function to check if pattern is in graveyard
        pattern_candidates: Dict to add valid patterns to
        debug_corrections: Optional dict to populate with debug info
    """
    for typo_pattern, word_pattern, pattern_boundary, length in cached_patterns:
        # Reconstruct other_part for debug logging
        if is_suffix:
            other_part_typo = typo[:-length] if length <= len(typo) else ""
        else:
            other_part_typo = typo[length:] if length <= len(typo) else ""

        if is_debug:
            logger.debug(
                f"  Length {length}: pattern='{typo_pattern}'→'{word_pattern}', "
                f"other_part='{other_part_typo}' (from cache)"
            )

        # Skip if pattern is already in graveyard
        if is_in_graveyard is not None and is_in_graveyard(
            typo_pattern, word_pattern, pattern_boundary
        ):
            if is_debug:
                logger.debug(
                    f"    SKIPPED - pattern already in graveyard: "
                    f"'{typo_pattern}'→'{word_pattern}' ({pattern_boundary.value})"
                )
            continue

        # Group directly by pattern, regardless of other_part
        pattern_key = (typo_pattern, word_pattern, pattern_boundary)
        pattern_candidates[pattern_key].append((typo, word, boundary))

        # Populate debug_corrections for summary logging
        if is_debug and debug_corrections is not None:
            debug_corrections[(typo, word, boundary)].append(
                (length, typo_pattern, word_pattern, other_part_typo)
            )
            logger.debug(
                f"    ✓ VALID CANDIDATE - pattern '{typo_pattern}'→'{word_pattern}' "
                f"(from cache, filtered by graveyard)"
            )


def _find_common_patterns(
    pattern_candidates: dict[tuple[str, str, BoundaryType], list[tuple[str, str, BoundaryType]]],
    debug_typos: set[str] | None,
    debug_enabled: bool,
    debug_typos_exact: set[str] | None = None,
    debug_typos_wildcard: set[str] | None = None,
) -> dict[tuple[str, str, BoundaryType], list[tuple[str, str, BoundaryType]]]:
    """Find patterns that have 2+ occurrences.

    Args:
        pattern_candidates: Dict of pattern candidates with their matches
        debug_typos: Optional set of typo strings to debug (backward compatibility)
        debug_enabled: Whether debug logging is enabled
        debug_typos_exact: Optional set of exact debug typo patterns
            (for exact matching)
        debug_typos_wildcard: Optional set of wildcard debug typo pattern cores
            (for substring matching)

    Returns:
        Dict mapping (typo_pattern, word_pattern, boundary) to list of
        (full_typo, full_word, original_boundary) tuples
    """
    patterns: dict[tuple[str, str, BoundaryType], list[tuple[str, str, BoundaryType]]] = (
        defaultdict(list)
    )

    # Add all patterns that have 2+ occurrences
    # Deduplicate matches since same correction might match pattern at different lengths
    for pattern_key, matches in pattern_candidates.items():
        if len(matches) >= 2:
            # Deduplicate: convert to set and back to list to remove duplicates
            unique_matches = list(dict.fromkeys(matches))  # Preserves order, removes duplicates
            if len(unique_matches) >= 2:
                patterns[pattern_key].extend(unique_matches)
                typo_pattern, word_pattern, boundary = pattern_key
                if debug_enabled:
                    should_log = False

                    # Use new parameters if provided
                    if debug_typos_exact is not None or debug_typos_wildcard is not None:
                        exact_patterns = debug_typos_exact or set()
                        wildcard_patterns = debug_typos_wildcard or set()
                        typo_pattern_lower = typo_pattern.lower()

                        # Check exact patterns (exact match)
                        if any(
                            typo_pattern_lower == pattern.lower()
                            or any(pattern.lower() == m[0].lower() for m in unique_matches)
                            for pattern in exact_patterns
                        ):
                            should_log = True
                        # Check wildcard patterns (substring match)
                        elif any(
                            pattern.lower() in typo_pattern_lower
                            or any(pattern.lower() in m[0].lower() for m in unique_matches)
                            for pattern in wildcard_patterns
                        ):
                            should_log = True
                    # Backward compatibility: use substring matching for all patterns
                    elif debug_typos is not None:
                        if any(
                            debug_typo.lower() in typo_pattern.lower()
                            or any(debug_typo.lower() in m[0].lower() for m in unique_matches)
                            for debug_typo in debug_typos
                        ):
                            should_log = True

                    if should_log:
                        logger.debug(
                            f"[PATTERN EXTRACTION] ✓ PATTERN FOUND: "
                            f"'{typo_pattern}' → '{word_pattern}' "
                            f"(boundary={boundary.value}, {len(unique_matches)} occurrences)"
                        )
                        for typo, word, orig_boundary in unique_matches:
                            logger.debug(
                                f"  - '{typo}' → '{word}' (boundary={orig_boundary.value})"
                            )

    return patterns


def _log_debug_summary(
    pattern_candidates: dict[tuple[str, str, BoundaryType], list[tuple[str, str, BoundaryType]]],
    patterns: dict[tuple[str, str, BoundaryType], list[tuple[str, str, BoundaryType]]],
    debug_corrections: dict[tuple[str, str, BoundaryType], list[tuple[int, str, str, str]]],
) -> None:
    """Log debug summary information.

    Args:
        pattern_candidates: Dict of pattern candidates
        patterns: Dict of final patterns
        debug_corrections: Dict of debug corrections
    """
    debug_enabled = len(debug_corrections) > 0

    if debug_enabled:
        logger.debug(
            f"[PATTERN EXTRACTION] Found {len(pattern_candidates)} unique pattern candidates"
        )

    if debug_enabled:
        logger.debug(f"[PATTERN EXTRACTION] Final: {len(patterns)} patterns with 2+ occurrences")
        # Show debug corrections summary
        for (typo, word, _), candidates in debug_corrections.items():
            if candidates:
                logger.debug(
                    f"[PATTERN EXTRACTION] '{typo}' → '{word}': "
                    f"{len(candidates)} valid pattern candidates"
                )
                for length, tp, wp, op in candidates:
                    logger.debug(f"  - Length {length}: '{tp}'→'{wp}' (other_part='{op}')")


def _find_patterns(
    corrections: list[Correction],
    boundary_type: BoundaryType,
    is_suffix: bool,
    debug_typos: set[str] | None = None,
    verbose: bool = False,
    is_in_graveyard: Callable[[str, str, BoundaryType], bool] | None = None,
    pattern_cache: (
        dict[tuple[str, str, BoundaryType, bool], list[tuple[str, str, BoundaryType, int]]] | None
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
        pattern_candidates, debug_typos, debug_enabled, debug_typos_exact, debug_typos_wildcard
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
        dict[tuple[str, str, BoundaryType, bool], list[tuple[str, str, BoundaryType, int]]] | None
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
        dict[tuple[str, str, BoundaryType, bool], list[tuple[str, str, BoundaryType, int]]] | None
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
