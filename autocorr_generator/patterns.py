"""Pattern generalization for typo corrections."""

from collections import defaultdict

from tqdm import tqdm

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
            # Only extract suffix patterns from corrections 
            # that are already suffix patterns (RIGHT boundary)
            if boundary == BoundaryType.RIGHT:
                for length in range(2, len(word) + 1):
                    if len(typo) < length:
                        continue
                    typo_suffix = typo[-length:]
                    word_suffix = word[-length:]
                    pattern_key = (typo_suffix, word_suffix, boundary)
                    patterns[pattern_key].append((typo, word, boundary))

    return patterns


def generalize_patterns(
    corrections: list[Correction],
    validation_set: set[str],
    source_words: set[str],
    min_typo_length: int,
    verbose: bool = False,
) -> tuple[list[Correction], set[Correction]]:
    """Find repeated patterns, create generalized rules, and return corrections to be removed."""
    patterns = []
    corrections_to_remove = set()
    suffix_patterns = find_suffix_patterns(corrections)

    # Wrap with progress bar if verbose
    pattern_items = suffix_patterns.items()
    if verbose:
        pattern_items = tqdm(
            pattern_items,
            total=len(suffix_patterns),
            desc="Generalizing patterns",
            unit="pattern",
        )

    for (typo_suffix, word_suffix, boundary), occurrences in pattern_items:
        if len(occurrences) < 2:
            continue

        if len(typo_suffix) < min_typo_length:
            continue

        # Check for conflicts with existing words before generalizing
        if typo_suffix in validation_set:
            continue

        if not would_trigger_at_end(typo_suffix, validation_set):
            # Check if this pattern would incorrectly trigger on any source words
            # For RIGHT boundary patterns, they trigger when followed by a word boundary
            # So check if pattern appears in source word followed by non-letter
            would_corrupt_source = False

            for source_word in source_words:
                idx = source_word.find(typo_suffix)
                while idx != -1:
                    # Check if there's a word boundary after this occurrence
                    char_after_idx = idx + len(typo_suffix)
                    if (
                        char_after_idx >= len(source_word)
                        or not source_word[char_after_idx].isalpha()
                    ):
                        # Pattern would trigger here and corrupt the source word
                        would_corrupt_source = True
                        break
                    # Look for next occurrence
                    idx = source_word.find(typo_suffix, idx + 1)
                if would_corrupt_source:
                    break

            if not would_corrupt_source:
                patterns.append((typo_suffix, word_suffix, boundary))

                # Mark original corrections for removal
                for typo, word, orig_boundary in occurrences:
                    corrections_to_remove.add((typo, word, orig_boundary))

    return patterns, corrections_to_remove
