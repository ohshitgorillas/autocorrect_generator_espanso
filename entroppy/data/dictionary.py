"""Dictionary and word list loading."""

import itertools
import os
from english_words import get_english_words_set
from loguru import logger
from wordfreq import top_n_list

from entroppy.core import Config
from entroppy.matching import PatternMatcher


def load_validation_dictionary(
    exclude_filepath: str | None,
    include_filepath: str | None,
    verbose: bool = False,
) -> set[str]:
    """Load english-words dictionary for validation.

    Removes words from the `exclude` file and adds words from the `include` file.
    Handles exact words and wildcard (*) patterns for exclusions.
    """
    if verbose:
        logger.info("Loading English words dictionary...")

    words = get_english_words_set(["web2", "gcide"], lower=True)
    original_word_count = len(words)

    # Add custom words from the main include file to the validation set
    custom_words = load_word_list(include_filepath)  # No verbose here
    words.update(custom_words)
    added_count = len(words) - original_word_count

    # Load exclusions from file
    exclusion_patterns = load_exclusions(exclude_filepath)  # No verbose here

    # Filter out patterns that are for typo->word mapping, not single word exclusion
    word_exclusion_patterns = {p for p in exclusion_patterns if "->" not in p}

    if not word_exclusion_patterns:
        if verbose:
            logger.info(
                f"Loaded {len(words)} words for validation (no exclusions applied)."
            )
        return words

    # Filter words using pattern matcher
    pattern_matcher = PatternMatcher(word_exclusion_patterns)
    validation_set = pattern_matcher.filter_set(words)
    removed_count = len(words) - len(validation_set)

    if verbose:
        logger.info(f"Loaded {len(validation_set)} words for validation")
        if added_count > 0:
            logger.info(
                f"Added {added_count} custom words from the include file."
            )
        if removed_count > 0:
            logger.info(
                f"Removed {removed_count} words based on the exclude file (including wildcards)."
            )

    return validation_set


def load_word_list(filepath: str | None, verbose: bool = False) -> list[str]:
    """Load custom word list from file."""
    if not filepath:
        return []

    filepath = os.path.expanduser(filepath)
    words = []
    invalid_count = 0

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip().lower()
            if line and not line.startswith("#"):
                # Basic validation
                if any(c in line for c in ["\n", "\r", "\t", "\\"]):
                    invalid_count += 1
                    continue
                words.append(line)

    if verbose and invalid_count > 0:
        logger.info(f"Skipped {invalid_count} words with invalid characters")

    return words


def load_exclusions(filepath: str | None, verbose: bool = False) -> set[str]:
    """Load exclusion patterns from file."""
    if not filepath:
        return set()

    filepath = os.path.expanduser(filepath)
    exclusions = set()
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                exclusions.add(line)

    if verbose:
        logger.info(f"Loaded {len(exclusions)} exclusion patterns")

    return exclusions


def load_adjacent_letters_map(
    filepath: str | None, verbose: bool = False
) -> dict[str, str] | None:
    """Load keyboard adjacency map from file."""
    if not filepath:
        return None

    filepath = os.path.expanduser(filepath)
    adjacent_map = {}
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if " -> " in line:
                key, adjacents = line.split(" -> ", 1)
                adjacent_map[key.strip()] = adjacents.strip()

    if verbose:
        logger.info(f"Loaded adjacency mapping for {len(adjacent_map)} keys")

    return adjacent_map


def load_source_words(config: Config, verbose: bool = False) -> list[str]:
    """Get source words from wordfreq."""
    if not config.top_n:
        return []

    if verbose:
        logger.info(f"Loading top {config.top_n} words from wordfreq...")

    # Get words from wordfreq, fetch extra for filtering
    all_words = top_n_list("en", config.top_n * 3)

    # Filter words using a generator expression for efficiency
    max_len = config.max_word_length or float("inf")
    valid_words = (
        word.lower()
        for word in all_words
        if config.min_word_length <= len(word) <= max_len
        and not any(c in word for c in "\n\r\t\\")
    )

    # Take the top N valid words
    filtered = list(itertools.islice(valid_words, config.top_n))

    return filtered
