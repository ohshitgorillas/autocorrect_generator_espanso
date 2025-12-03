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

    Returns:
        Dict mapping (typo_pattern, word_pattern, boundary) to list of
        (full_typo, full_word, original_boundary) tuples that match this pattern.
    """
    patterns: dict[tuple[str, str, BoundaryType], list[tuple[str, str, BoundaryType]]] = (
        defaultdict(list)
    )
    debug_enabled = debug_typos is not None and len(debug_typos) > 0

    # Track cache statistics
    cache_hits = 0
    cache_misses = 0

    # Filter corrections by boundary type
    # For suffix patterns (RIGHT), also include NONE boundary (matches anywhere, so suffix is valid)
    # For prefix patterns (LEFT), also include NONE boundary (matches anywhere, so prefix is valid)
    if is_suffix:
        # Suffix patterns: include RIGHT and NONE boundaries
        filtered_corrections = [
            (typo, word, boundary)
            for typo, word, boundary in corrections
            if boundary in (boundary_type, BoundaryType.NONE)
        ]
    else:
        # Prefix patterns: include LEFT and NONE boundaries
        filtered_corrections = [
            (typo, word, boundary)
            for typo, word, boundary in corrections
            if boundary in (boundary_type, BoundaryType.NONE)
        ]

    if not filtered_corrections:
        return patterns

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
    debug_corrections: dict[tuple[str, str, BoundaryType], list[tuple[int, str, str, str]]] = {}
    if debug_enabled and debug_typos is not None:
        for typo, word, boundary in filtered_corrections:
            if any(debug_typo.lower() in typo.lower() for debug_typo in debug_typos):
                debug_corrections[(typo, word, boundary)] = []

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
        max_pattern_length = min(len(typo), len(word)) - _MIN_OTHER_PART_LENGTH

        if max_pattern_length < 2:
            continue

        if is_debug:
            logger.debug(
                f"[PATTERN EXTRACTION] Analyzing correction: '{typo}' → '{word}' "
                f"(boundary={boundary.value}, max_pattern_length={max_pattern_length})"
            )

        # Check cache first
        cache_key = (typo, word, boundary, is_suffix)
        cached_patterns = None
        if pattern_cache is not None and cache_key in pattern_cache:
            cached_patterns = pattern_cache[cache_key]
            cache_hits += 1
            if is_debug:
                logger.debug(f"  Using cached patterns: {len(cached_patterns)} patterns found")
            elif verbose:
                logger.debug(
                    f"[CACHE HIT] {typo}→{word} ({boundary.value}, "
                    f"{'suffix' if is_suffix else 'prefix'}): {len(cached_patterns)} patterns"
                )

        # Extract patterns if not cached
        if cached_patterns is None:
            cache_misses += 1
            cached_patterns = []
            # Extract all valid patterns at once by iterating through possible pattern lengths
            # Start from longest patterns (more specific) and work backwards
            for length in range(max_pattern_length, 1, -1):  # Start from longest, go down to 2
                typo_pattern, word_pattern, other_part_typo, other_part_word = (
                    _extract_pattern_parts(typo, word, length, is_suffix)
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

                if is_debug:
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
                if verbose and not is_debug:
                    logger.debug(
                        f"[CACHE MISS] {typo}→{word} ({boundary.value}, "
                        f"{'suffix' if is_suffix else 'prefix'}): "
                        f"extracted {len(cached_patterns)} patterns"
                    )

        # Process cached patterns, filtering by graveyard
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
            if is_debug:
                debug_corrections[(typo, word, boundary)].append(
                    (length, typo_pattern, word_pattern, other_part_typo)
                )
                logger.debug(
                    f"    ✓ VALID CANDIDATE - pattern '{typo_pattern}'→'{word_pattern}' "
                    f"(from cache, filtered by graveyard)"
                )

    if debug_enabled:
        logger.debug(
            f"[PATTERN EXTRACTION] Found {len(pattern_candidates)} unique pattern candidates"
        )

    # Log cache statistics if cache is being used
    if pattern_cache is not None and verbose:
        cache_size = len(pattern_cache)
        logger.debug(
            f"[PATTERN EXTRACTION] Cache stats: {cache_hits} hits, {cache_misses} misses, "
            f"{cache_size} total entries"
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
                if debug_enabled and debug_typos is not None:
                    # Check if any debug typos are in this pattern
                    if any(
                        debug_typo.lower() in typo_pattern.lower()
                        or any(debug_typo.lower() in m[0].lower() for m in unique_matches)
                        for debug_typo in debug_typos
                    ):
                        logger.debug(
                            f"[PATTERN EXTRACTION] ✓ PATTERN FOUND: "
                            f"'{typo_pattern}' → '{word_pattern}' "
                            f"(boundary={boundary.value}, {len(unique_matches)} occurrences)"
                        )
                        for typo, word, orig_boundary in unique_matches:
                            logger.debug(
                                f"  - '{typo}' → '{word}' (boundary={orig_boundary.value})"
                            )

    if debug_enabled:
        logger.debug(f"[PATTERN EXTRACTION] Final: {len(patterns)} patterns with 2+ occurrences")
        # Show debug corrections summary
        for (typo, word, boundary), candidates in debug_corrections.items():
            if candidates:
                logger.debug(
                    f"[PATTERN EXTRACTION] '{typo}' → '{word}': "
                    f"{len(candidates)} valid pattern candidates"
                )
                for length, tp, wp, op in candidates:
                    logger.debug(f"  - Length {length}: '{tp}'→'{wp}' (other_part='{op}')")

    return patterns


def find_suffix_patterns(
    corrections: list[Correction],
    debug_typos: set[str] | None = None,
    verbose: bool = False,
    is_in_graveyard: Callable[[str, str, BoundaryType], bool] | None = None,
    pattern_cache: (
        dict[tuple[str, str, BoundaryType, bool], list[tuple[str, str, BoundaryType, int]]] | None
    ) = None,
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
    """
    return _find_patterns(
        corrections,
        BoundaryType.RIGHT,
        is_suffix=True,
        debug_typos=debug_typos,
        verbose=verbose,
        is_in_graveyard=is_in_graveyard,
        pattern_cache=pattern_cache,
    )


def find_prefix_patterns(
    corrections: list[Correction],
    debug_typos: set[str] | None = None,
    verbose: bool = False,
    is_in_graveyard: Callable[[str, str, BoundaryType], bool] | None = None,
    pattern_cache: (
        dict[tuple[str, str, BoundaryType, bool], list[tuple[str, str, BoundaryType, int]]] | None
    ) = None,
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
    """
    return _find_patterns(
        corrections,
        BoundaryType.LEFT,
        is_suffix=False,
        debug_typos=debug_typos,
        verbose=verbose,
        is_in_graveyard=is_in_graveyard,
        pattern_cache=pattern_cache,
    )
