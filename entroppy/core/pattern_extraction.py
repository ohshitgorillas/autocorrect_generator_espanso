"""Pattern extraction from typo corrections."""

from collections import defaultdict

from loguru import logger

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
) -> dict[tuple[str, str, BoundaryType], list[tuple[str, str, BoundaryType]]]:
    """Find common patterns (prefix or suffix) in corrections.

    Optimized implementation that groups corrections by their "other part"
    (the part that doesn't change) to eliminate redundant pattern length checks.

    Args:
        corrections: List of corrections to analyze
        boundary_type: Boundary type to filter by (LEFT for prefix, RIGHT for suffix)
        is_suffix: True for suffix patterns, False for prefix patterns
        debug_typos: Optional set of typo strings to debug (for logging)

    Returns:
        Dict mapping (typo_pattern, word_pattern, boundary) to list of
        (full_typo, full_word, original_boundary) tuples that match this pattern.
    """
    patterns = defaultdict(list)
    debug_enabled = debug_typos is not None and len(debug_typos) > 0

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

    # Group corrections by word length for efficient processing
    corrections_by_len = defaultdict(list)
    for typo, word, boundary in filtered_corrections:
        corrections_by_len[len(word)].append((typo, word, boundary))

    # Group directly by (typo_pattern, word_pattern, boundary) across ALL corrections
    # This finds patterns even when corrections have different "other parts"
    # Example: "action" and "lection" both share pattern "tion" → "tion" despite different prefixes
    pattern_candidates: dict[tuple[str, str, BoundaryType], list[tuple[str, str, BoundaryType]]] = (
        defaultdict(list)
    )

    # Track debug info for specific typos
    debug_corrections = {}
    if debug_enabled:
        for typo, word, boundary in filtered_corrections:
            if any(debug_typo.lower() in typo.lower() for debug_typo in debug_typos):
                debug_corrections[(typo, word, boundary)] = []

    for length_group in corrections_by_len.values():
        for typo, word, boundary in length_group:
            max_pattern_length = len(word) - _MIN_OTHER_PART_LENGTH
            is_debug = (typo, word, boundary) in debug_corrections

            if is_debug:
                logger.debug(
                    f"[PATTERN EXTRACTION] Analyzing correction: '{typo}' → '{word}' "
                    f"(boundary={boundary.value}, max_pattern_length={max_pattern_length})"
                )

            # Check all valid pattern lengths
            for length in range(2, max_pattern_length + 1):
                if len(typo) < length:
                    if is_debug:
                        logger.debug(
                            f"  Length {length}: SKIPPED - typo length {len(typo)} "
                            f"< pattern length {length}"
                        )
                    continue

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

                # Group directly by pattern, regardless of other_part
                pattern_key = (typo_pattern, word_pattern, boundary)
                pattern_candidates[pattern_key].append((typo, word, boundary))

                if is_debug:
                    debug_corrections[(typo, word, boundary)].append(
                        (length, typo_pattern, word_pattern, other_part_typo)
                    )
                    logger.debug(
                        f"    ✓ VALID CANDIDATE - pattern '{typo_pattern}'→'{word_pattern}' "
                        f"(other_part='{other_part_typo}')"
                    )

    if debug_enabled:
        logger.debug(
            f"[PATTERN EXTRACTION] Found {len(pattern_candidates)} unique pattern candidates"
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
) -> dict[tuple[str, str, BoundaryType], list[tuple[str, str, BoundaryType]]]:
    """Find common suffix patterns (for RIGHT boundaries).

    Returns a dict mapping (typo_suffix, word_suffix, boundary) to list of
    (full_typo, full_word, original_boundary) tuples that match this pattern.

    Args:
        corrections: List of corrections to analyze
        debug_typos: Optional set of typo strings to debug (for logging)
    """
    return _find_patterns(corrections, BoundaryType.RIGHT, is_suffix=True, debug_typos=debug_typos)


def find_prefix_patterns(
    corrections: list[Correction],
    debug_typos: set[str] | None = None,
) -> dict[tuple[str, str, BoundaryType], list[tuple[str, str, BoundaryType]]]:
    """Find common prefix patterns (for LEFT boundaries).

    Returns a dict mapping (typo_prefix, word_prefix, boundary) to list of
    (full_typo, full_word, original_boundary) tuples that match this pattern.

    Args:
        corrections: List of corrections to analyze
        debug_typos: Optional set of typo strings to debug (for logging)
    """
    return _find_patterns(corrections, BoundaryType.LEFT, is_suffix=False, debug_typos=debug_typos)
