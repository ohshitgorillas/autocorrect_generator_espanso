"""Pattern generalization for typo corrections."""

from collections import defaultdict

from .boundaries import would_trigger_at_end
from .config import BoundaryType, Correction


def find_suffix_patterns(
    corrections: list[Correction],
) -> dict[tuple[str, str, BoundaryType], list[tuple[str, str, BoundaryType]]]:
    """Find common suffix patterns.

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
            # Only generalize suffix patterns for RIGHT or NONE boundaries
            if boundary not in (BoundaryType.RIGHT, BoundaryType.NONE):
                continue

            # Iterate from a sensible minimum suffix length up to the full word length
            for length in range(2, len(word) + 1):
                if len(typo) < length:
                    continue

                typo_suffix = typo[-length:]
                word_suffix = word[-length:]
                # Keep the same boundary type as the original corrections
                # NONE boundary patterns can fix compound typos like "natoinal" → "national"
                pattern_key = (typo_suffix, word_suffix, boundary)
                # Store the original correction with its original boundary for later removal
                patterns[pattern_key].append((typo, word, boundary))

    return patterns


def generalize_patterns(
    corrections: list[Correction],
    validation_set: set[str],
    min_typo_length: int,
) -> tuple[list[Correction], set[Correction]]:
    """Find repeated patterns, create generalized rules, and return corrections to be removed."""
    patterns = []
    corrections_to_remove = set()
    suffix_patterns = find_suffix_patterns(corrections)

    for (typo_suffix, word_suffix, boundary), occurrences in suffix_patterns.items():
        if len(occurrences) < 2:
            continue

        if len(typo_suffix) < min_typo_length:
            continue

        # Check for conflicts with existing words before generalizing
        if typo_suffix in validation_set:
            continue

        if not would_trigger_at_end(typo_suffix, validation_set):
            patterns.append((typo_suffix, word_suffix, boundary))
            # Mark original corrections that generated this pattern for removal
            for typo, word, orig_boundary in occurrences:
                corrections_to_remove.add((typo, word, orig_boundary))

    return patterns, corrections_to_remove
