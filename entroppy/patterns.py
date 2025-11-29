"""Pattern generalization for typo corrections."""

import sys
from collections import defaultdict

from .boundaries import would_trigger_at_end
from .config import BoundaryType, Correction

from .platforms.base import MatchDirection


def find_suffix_patterns(
    corrections: list[Correction],
) -> dict[tuple[str, str, BoundaryType], list[tuple[str, str, BoundaryType]]]:
    """Find common suffix patterns (for RIGHT boundaries).

    Returns a dict mapping (typo_suffix, word_suffix, boundary) to list of
    (full_typo, full_word, original_boundary) tuples that match this pattern.
    """
    patterns = defaultdict(list)
    # Group corrections by word length to make suffix comparison more efficient
    corrections_by_len = defaultdict(list)
    for typo, word, boundary in corrections:
        corrections_by_len[len(word)].append((typo, word, boundary))

    for length_group in corrections_by_len.values():
        for typo, word, boundary in length_group:
            # Only extract suffix patterns from corrections
            # that are already suffix patterns (RIGHT boundary)
            if boundary == BoundaryType.RIGHT:
                # Require at least 2 characters of prefix before the suffix
                # This prevents extracting nonsensical patterns like "ayt → lay" from "layt → lay"
                min_prefix_length = 2
                max_suffix_length = len(word) - min_prefix_length

                for length in range(2, max_suffix_length + 1):
                    if len(typo) < length:
                        continue
                    typo_suffix = typo[-length:]
                    word_suffix = word[-length:]
                    # Skip if typo and word suffixes are identical (useless pattern)
                    if typo_suffix == word_suffix:
                        continue
                    # Ensure prefixes match before considering a pattern valid
                    if typo[:-length] != word[:-length]:
                        continue

                    pattern_key = (typo_suffix, word_suffix, boundary)
                    patterns[pattern_key].append((typo, word, boundary))

    return patterns


def find_prefix_patterns(
    corrections: list[Correction],
) -> dict[tuple[str, str, BoundaryType], list[tuple[str, str, BoundaryType]]]:
    """Find common prefix patterns (for LEFT boundaries).

    Returns a dict mapping (typo_prefix, word_prefix, boundary) to list of
    (full_typo, full_word, original_boundary) tuples that match this pattern.
    """
    patterns = defaultdict(list)
    # Group corrections by word length to make prefix comparison more efficient
    corrections_by_len = defaultdict(list)
    for typo, word, boundary in corrections:
        corrections_by_len[len(word)].append((typo, word, boundary))

    for length_group in corrections_by_len.values():
        for typo, word, boundary in length_group:
            # Only extract prefix patterns from corrections
            # that are already prefix patterns (LEFT boundary)
            if boundary == BoundaryType.LEFT:
                # Require at least 2 characters of suffix after the prefix
                # This prevents extracting nonsensical patterns
                min_suffix_length = 2
                max_prefix_length = len(word) - min_suffix_length

                for length in range(2, max_prefix_length + 1):
                    if len(typo) < length:
                        continue
                    typo_prefix = typo[:length]
                    word_prefix = word[:length]
                    # Skip if typo and word prefixes are identical (useless pattern)
                    if typo_prefix == word_prefix:
                        continue
                    # Ensure suffixes match before considering a pattern valid
                    if typo[length:] != word[length:]:
                        continue

                    pattern_key = (typo_prefix, word_prefix, boundary)
                    patterns[pattern_key].append((typo, word, boundary))

    return patterns


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
) -> tuple[list[Correction], set[Correction], dict, list]:
    """Find repeated patterns, create generalized rules, and return corrections to be removed.

    Returns:
        Tuple of (patterns, corrections_to_remove, pattern_replacements, rejected_patterns)
    """
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
        print(
            f"Generalizing {len(found_patterns)} {pattern_type} patterns...",
            file=sys.stderr,
        )

    for (typo_pattern, word_pattern, boundary), occurrences in found_patterns.items():
        if len(occurrences) < 2:
            continue

        if len(typo_pattern) < min_typo_length:
            rejected_patterns.append(
                (typo_pattern, word_pattern, f"Too short (< {min_typo_length})")
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

                # Mark original corrections for removal
                for typo, word, orig_boundary in occurrences:
                    corrections_to_remove.add((typo, word, orig_boundary))
            else:
                rejected_patterns.append(
                    (typo_pattern, word_pattern, "Would corrupt source words")
                )
        else:
            rejected_patterns.append(
                (typo_pattern, word_pattern, "Would trigger at end of validation words")
            )

    return patterns, corrections_to_remove, pattern_replacements, rejected_patterns
