"""Pattern generalization for typo corrections."""

from collections import defaultdict

from loguru import logger

from .boundaries import would_trigger_at_end
from .config import BoundaryType, Correction
from .debug_utils import is_debug_correction

from .platforms.base import MatchDirection


def _find_patterns(
    corrections: list[Correction],
    boundary_type: BoundaryType,
    is_suffix: bool,
) -> dict[tuple[str, str, BoundaryType], list[tuple[str, str, BoundaryType]]]:
    """Find common patterns (prefix or suffix) in corrections.

    Args:
        corrections: List of corrections to analyze
        boundary_type: Boundary type to filter by (LEFT for prefix, RIGHT for suffix)
        is_suffix: True for suffix patterns, False for prefix patterns

    Returns:
        Dict mapping (typo_pattern, word_pattern, boundary) to list of
        (full_typo, full_word, original_boundary) tuples that match this pattern.
    """
    patterns = defaultdict(list)
    # Group corrections by word length to make comparison more efficient
    corrections_by_len = defaultdict(list)
    for typo, word, boundary in corrections:
        corrections_by_len[len(word)].append((typo, word, boundary))

    for length_group in corrections_by_len.values():
        for typo, word, boundary in length_group:
            # Only extract patterns from corrections with matching boundary type
            if boundary == boundary_type:
                # Require at least 2 characters of the non-pattern part
                # This prevents extracting nonsensical patterns
                min_other_length = 2
                max_pattern_length = len(word) - min_other_length

                for length in range(2, max_pattern_length + 1):
                    if len(typo) < length:
                        continue

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

                    # Skip if patterns are identical (useless pattern)
                    if typo_pattern == word_pattern:
                        continue
                    # Ensure the other parts match before considering a pattern valid
                    if other_part_typo != other_part_word:
                        continue

                    pattern_key = (typo_pattern, word_pattern, boundary)
                    patterns[pattern_key].append((typo, word, boundary))

    return patterns


def find_suffix_patterns(
    corrections: list[Correction],
) -> dict[tuple[str, str, BoundaryType], list[tuple[str, str, BoundaryType]]]:
    """Find common suffix patterns (for RIGHT boundaries).

    Returns a dict mapping (typo_suffix, word_suffix, boundary) to list of
    (full_typo, full_word, original_boundary) tuples that match this pattern.
    """
    return _find_patterns(corrections, BoundaryType.RIGHT, is_suffix=True)


def find_prefix_patterns(
    corrections: list[Correction],
) -> dict[tuple[str, str, BoundaryType], list[tuple[str, str, BoundaryType]]]:
    """Find common prefix patterns (for LEFT boundaries).

    Returns a dict mapping (typo_prefix, word_prefix, boundary) to list of
    (full_typo, full_word, original_boundary) tuples that match this pattern.
    """
    return _find_patterns(corrections, BoundaryType.LEFT, is_suffix=False)


def _validate_pattern_result(
    typo_pattern: str,
    word_pattern: str,
    full_typo: str,
    full_word: str,
    match_direction,
) -> tuple[bool, str]:
    """Validate that a pattern produces the expected result for a specific case.

    Returns:
        Tuple of (is_valid, expected_result)
    """
    if match_direction == MatchDirection.RIGHT_TO_LEFT:
        # PREFIX pattern: typo_pattern at start
        remaining_suffix = full_typo[len(typo_pattern) :]
        expected_result = word_pattern + remaining_suffix
    else:
        # SUFFIX pattern: typo_pattern at end
        remaining_prefix = full_typo[: -len(typo_pattern)]
        expected_result = remaining_prefix + word_pattern

    return expected_result == full_word, expected_result


def _would_corrupt_source_word(
    typo_pattern: str,
    source_word: str,
    match_direction,
) -> bool:
    """Check if a pattern would corrupt a source word.

    For RTL: checks if pattern appears at word boundaries at the start
    For LTR: checks if pattern appears at word boundaries at the end
    """
    idx = source_word.find(typo_pattern)
    while idx != -1:
        if match_direction == MatchDirection.RIGHT_TO_LEFT:
            # PREFIX pattern: check if there's a word boundary before
            if idx == 0 or not source_word[idx - 1].isalpha():
                return True
        else:
            # SUFFIX pattern: check if there's a word boundary after
            char_after_idx = idx + len(typo_pattern)
            if (
                char_after_idx >= len(source_word)
                or not source_word[char_after_idx].isalpha()
            ):
                return True
        # Look for next occurrence
        idx = source_word.find(typo_pattern, idx + 1)

    return False


def generalize_patterns(
    corrections: list[Correction],
    validation_set: set[str],
    source_words: set[str],
    min_typo_length: int,
    match_direction: MatchDirection,
    verbose: bool = False,
    debug_words: set[str] = set(),
    debug_typo_matcher: "DebugTypoMatcher | None" = None,
) -> tuple[list[Correction], set[Correction], dict, list]:
    """Find repeated patterns, create generalized rules, and return corrections to be removed.

    Args:
        corrections: List of corrections to analyze
        validation_set: Set of valid words
        source_words: Set of source words
        min_typo_length: Minimum typo length
        match_direction: Platform match direction
        verbose: Whether to print verbose output
        debug_words: Set of words to debug (exact matches)
        debug_typo_matcher: Matcher for debug typos (with wildcards/boundaries)

    Returns:
        Tuple of (patterns, corrections_to_remove, pattern_replacements, rejected_patterns)
    """
    from .debug_utils import log_debug_correction, log_debug_typo

    patterns = []
    corrections_to_remove = set()
    pattern_replacements = {}
    rejected_patterns = []

    # Choose pattern finding strategy based on match direction
    if match_direction == MatchDirection.RIGHT_TO_LEFT:
        # RTL matching (QMK): look for prefix patterns (LEFT boundary)
        found_patterns = find_prefix_patterns(corrections)
        pattern_type = "prefix"
    else:
        # LTR matching (Espanso): look for suffix patterns (RIGHT boundary)
        found_patterns = find_suffix_patterns(corrections)
        pattern_type = "suffix"

    if verbose:
        logger.info(
            f"Generalizing {len(found_patterns)} {pattern_type} patterns..."
        )

    for (typo_pattern, word_pattern, boundary), occurrences in found_patterns.items():
        if len(occurrences) < 2:
            continue

        # Check if any of the occurrences involve debug items
        has_debug_occurrence = any(
            is_debug_correction(occ, debug_words, debug_typo_matcher)
            for occ in occurrences
        )

        if len(typo_pattern) < min_typo_length:
            rejected_patterns.append(
                (typo_pattern, word_pattern, f"Too short (< {min_typo_length})")
            )
            if has_debug_occurrence:
                # Log that a pattern involving debug items was rejected
                pattern_correction = (typo_pattern, word_pattern, boundary)
                log_debug_correction(
                    pattern_correction,
                    f"Pattern rejected - too short (< {min_typo_length}), would have replaced {len(occurrences)} corrections",
                    debug_words,
                    debug_typo_matcher,
                    "Stage 4"
                )
            continue

        # Validate: Check if this pattern actually works for all occurrences
        pattern_valid = True
        for full_typo, full_word, _ in occurrences:
            is_valid, expected_result = _validate_pattern_result(
                typo_pattern, word_pattern, full_typo, full_word, match_direction
            )
            if not is_valid:
                # This pattern would create garbage for this word
                pattern_valid = False
                rejected_patterns.append(
                    (
                        typo_pattern,
                        word_pattern,
                        f"Creates '{expected_result}' instead of "
                        f"'{full_word}' for typo '{full_typo}'",
                    )
                )
                if has_debug_occurrence:
                    pattern_correction = (typo_pattern, word_pattern, boundary)
                    log_debug_correction(
                        pattern_correction,
                        f"Pattern rejected - creates '{expected_result}' instead of '{full_word}' for typo '{full_typo}'",
                        debug_words,
                        debug_typo_matcher,
                        "Stage 4"
                    )
                break

        if not pattern_valid:
            continue

        # Check for conflicts with existing words before generalizing
        if typo_pattern in validation_set:
            rejected_patterns.append(
                (
                    typo_pattern,
                    word_pattern,
                    f"Conflicts with validation word '{typo_pattern}'",
                )
            )
            if has_debug_occurrence:
                pattern_correction = (typo_pattern, word_pattern, boundary)
                log_debug_correction(
                    pattern_correction,
                    f"Pattern rejected - conflicts with validation word '{typo_pattern}'",
                    debug_words,
                    debug_typo_matcher,
                    "Stage 4"
                )
            continue

        if not would_trigger_at_end(typo_pattern, validation_set):
            # Check if this pattern would incorrectly trigger on any source words
            would_corrupt_source = any(
                _would_corrupt_source_word(typo_pattern, source_word, match_direction)
                for source_word in source_words
            )

            if not would_corrupt_source:
                patterns.append((typo_pattern, word_pattern, boundary))

                # Track which corrections this pattern replaces
                pattern_key = (typo_pattern, word_pattern, boundary)
                pattern_replacements[pattern_key] = occurrences

                # Debug logging for pattern acceptance
                if has_debug_occurrence:
                    pattern_correction = (typo_pattern, word_pattern, boundary)
                    replaced_strs = [f"{t}→{w}" for t, w, _ in occurrences[:3]]
                    if len(occurrences) > 3:
                        replaced_strs.append(f"... and {len(occurrences) - 3} more")
                    log_debug_correction(
                        pattern_correction,
                        f"Pattern ACCEPTED - replaces {len(occurrences)} corrections: {', '.join(replaced_strs)}",
                        debug_words,
                        debug_typo_matcher,
                        "Stage 4"
                    )

                # Mark original corrections for removal
                for typo, word, orig_boundary in occurrences:
                    corrections_to_remove.add((typo, word, orig_boundary))
                    # Log individual replacements for debug items
                    correction = (typo, word, orig_boundary)
                    if is_debug_correction(correction, debug_words, debug_typo_matcher):
                        log_debug_correction(
                            correction,
                            f"Will be replaced by pattern: {typo_pattern} → {word_pattern}",
                            debug_words,
                            debug_typo_matcher,
                            "Stage 4"
                        )
            else:
                rejected_patterns.append(
                    (typo_pattern, word_pattern, "Would corrupt source words")
                )
                if has_debug_occurrence:
                    pattern_correction = (typo_pattern, word_pattern, boundary)
                    log_debug_correction(
                        pattern_correction,
                        "Pattern rejected - would corrupt source words",
                        debug_words,
                        debug_typo_matcher,
                        "Stage 4"
                    )
        else:
            rejected_patterns.append(
                (typo_pattern, word_pattern, "Would trigger at end of validation words")
            )

    return patterns, corrections_to_remove, pattern_replacements, rejected_patterns
