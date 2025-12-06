"""Pattern matching and extraction functions."""

from typing import Callable

from loguru import logger

from entroppy.core.boundaries import BoundaryType

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


def _extract_single_pattern(
    typo: str,
    word: str,
    boundary: BoundaryType,
    length: int,
    is_suffix: bool,
    is_debug: bool,
    debug_corrections: (
        dict[tuple[str, str, BoundaryType], list[tuple[int, str, str, str]]] | None
    ) = None,
) -> tuple[str, str, BoundaryType, int] | None:
    """Extract a single pattern of given length, returning None if invalid."""
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
        return None

    # Ensure the other parts match before considering a pattern valid
    if other_part_typo != other_part_word:
        if is_debug:
            logger.debug(
                f"    SKIPPED - other_part mismatch: " f"'{other_part_typo}' != '{other_part_word}'"
            )
        return None

    if is_debug and debug_corrections is not None:
        debug_corrections[(typo, word, boundary)].append(
            (length, typo_pattern, word_pattern, other_part_typo)
        )
        logger.debug(
            f"    ✓ EXTRACTED - pattern '{typo_pattern}'→'{word_pattern}' "
            f"(other_part='{other_part_typo}')"
        )

    return (typo_pattern, word_pattern, boundary, length)


def _extract_patterns_from_correction(
    typo: str,
    word: str,
    boundary: BoundaryType,
    is_suffix: bool,
    is_debug: bool,
    pattern_cache: (
        dict[
            tuple[str, str, BoundaryType, bool],
            list[tuple[str, str, BoundaryType, int]],
        ]
        | None
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
            pattern = _extract_single_pattern(
                typo, word, boundary, length, is_suffix, is_debug, debug_corrections
            )
            if pattern is not None:
                cached_patterns.append(pattern)

        # Store in cache for future iterations
        if pattern_cache is not None:
            pattern_cache[cache_key] = cached_patterns

    return cached_patterns, was_cache_hit


def _reconstruct_other_part(typo: str, length: int, is_suffix: bool) -> str:
    """Reconstruct the other part of the typo for debug logging."""
    if is_suffix:
        return typo[:-length] if length <= len(typo) else ""
    return typo[length:] if length <= len(typo) else ""


def _process_single_cached_pattern(
    typo: str,
    word: str,
    boundary: BoundaryType,
    typo_pattern: str,
    word_pattern: str,
    pattern_boundary: BoundaryType,
    length: int,
    is_suffix: bool,
    is_debug: bool,
    is_in_graveyard: Callable[[str, str, BoundaryType], bool] | None,
    pattern_candidates: dict[tuple[str, str, BoundaryType], list[tuple[str, str, BoundaryType]]],
    debug_corrections: (
        dict[tuple[str, str, BoundaryType], list[tuple[int, str, str, str]]] | None
    ) = None,
) -> bool:
    """Process a single cached pattern, returning True if added to candidates."""
    other_part_typo = _reconstruct_other_part(typo, length, is_suffix)

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
        return False

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

    return True


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
        _process_single_cached_pattern(
            typo,
            word,
            boundary,
            typo_pattern,
            word_pattern,
            pattern_boundary,
            length,
            is_suffix,
            is_debug,
            is_in_graveyard,
            pattern_candidates,
            debug_corrections,
        )
