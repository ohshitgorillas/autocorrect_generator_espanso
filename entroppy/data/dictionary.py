"""Dictionary and word list loading."""

import itertools

from english_words import get_english_words_set  # type: ignore[import-untyped]
from loguru import logger
from wordfreq import top_n_list

from entroppy.core import Config
from entroppy.matching import PatternMatcher
from entroppy.utils import Constants, expand_file_path


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
        logger.info("  Loading English words dictionary...")

    try:
        # type: ignore[no-any-return]
        words: set[str] = get_english_words_set(["web2", "gcide"], lower=True)
    except Exception as e:
        logger.error(f"✗ Failed to load English words dictionary: {e}")
        logger.error("  This may indicate a problem with the 'english-words' package")
        logger.error("  Try reinstalling: pip install english-words")
        raise RuntimeError("Failed to load validation dictionary") from e
    original_word_count = len(words)

    # Add custom words from the main include file to the validation set
    custom_words = load_word_list(include_filepath)  # No verbose here
    words.update(custom_words)
    added_count = len(words) - original_word_count

    # Load exclusions from file
    exclusion_patterns = load_exclusions(exclude_filepath)  # No verbose here

    # Filter out patterns that are for typo->word mapping, not single word exclusion
    word_exclusion_patterns = {
        p for p in exclusion_patterns if Constants.EXCLUSION_SEPARATOR not in p
    }

    if not word_exclusion_patterns:
        if verbose:
            logger.info(f"  Loaded {len(words)} words for validation (no exclusions applied)")
        return words

    # Filter words using pattern matcher
    pattern_matcher = PatternMatcher(word_exclusion_patterns)
    validation_set = pattern_matcher.filter_set(words)
    removed_count = len(words) - len(validation_set)

    if verbose:
        logger.info(f"  Loaded {len(validation_set)} words for validation")
        if added_count > 0:
            logger.info(f"  Added {added_count} custom words from include file")
        if removed_count > 0:
            logger.info(
                f"  Removed {removed_count} words based on exclude file (including wildcards)"
            )

    return validation_set


def load_word_list(filepath: str | None, verbose: bool = False) -> list[str]:
    """Load custom word list from file."""
    if not filepath:
        return []

    filepath = expand_file_path(filepath)
    if not filepath:
        return []

    words = []
    invalid_count = 0

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip().lower()
                if line and not line.startswith("#"):
                    # Basic validation
                    if any(c in line for c in ["\n", "\r", "\t", "\\"]):
                        invalid_count += 1
                        continue
                    words.append(line)
    except FileNotFoundError:
        logger.error(f"✗ Word list file not found: {filepath}")
        logger.error("  Please check the file path and try again")
        raise
    except PermissionError:
        logger.error(f"✗ Permission denied reading file: {filepath}")
        logger.error("  Please check file permissions and try again")
        raise
    except UnicodeDecodeError as e:
        logger.error(f"✗ Encoding error reading {filepath}: {e}")
        logger.error("  Please ensure the file is UTF-8 encoded")
        raise
    except Exception as e:
        logger.error(f"✗ Unexpected error reading word list file {filepath}: {e}")
        raise

    if verbose and invalid_count > 0:
        logger.info(f"Skipped {invalid_count} words with invalid characters")

    return words


def load_exclusions(filepath: str | None, verbose: bool = False) -> set[str]:
    """Load exclusion patterns from file."""
    if not filepath:
        return set()

    filepath = expand_file_path(filepath)
    if not filepath:
        return set()

    exclusions = set()
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    exclusions.add(line)
    except FileNotFoundError:
        logger.error(f"✗ Exclusions file not found: {filepath}")
        logger.error("  Please check the file path and try again")
        raise
    except PermissionError:
        logger.error(f"✗ Permission denied reading file: {filepath}")
        logger.error("  Please check file permissions and try again")
        raise
    except UnicodeDecodeError as e:
        logger.error(f"✗ Encoding error reading {filepath}: {e}")
        logger.error("  Please ensure the file is UTF-8 encoded")
        raise
    except Exception as e:
        logger.error(f"✗ Unexpected error reading exclusions file {filepath}: {e}")
        raise

    if verbose:
        logger.info(f"Loaded {len(exclusions)} exclusion patterns")

    return exclusions


def load_adjacent_letters_map(filepath: str | None, verbose: bool = False) -> dict[str, str] | None:
    """Load keyboard adjacency map from file."""
    if not filepath:
        return None

    filepath = expand_file_path(filepath)
    if not filepath:
        return None

    adjacent_map = {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if Constants.ADJACENT_MAP_SEPARATOR in line:
                    try:
                        key, adjacents = line.split(Constants.ADJACENT_MAP_SEPARATOR, 1)
                        adjacent_map[key.strip()] = adjacents.strip()
                    except ValueError:
                        logger.warning(f"Skipping malformed line in {filepath}: {line.strip()}")
                        continue
    except FileNotFoundError:
        logger.error(f"✗ Adjacent letters map file not found: {filepath}")
        logger.error("  Please check the file path and try again")
        raise
    except PermissionError:
        logger.error(f"✗ Permission denied reading file: {filepath}")
        logger.error("  Please check file permissions and try again")
        raise
    except UnicodeDecodeError as e:
        logger.error(f"✗ Encoding error reading {filepath}: {e}")
        logger.error("  Please ensure the file is UTF-8 encoded")
        raise
    except Exception as e:
        logger.error(f"✗ Unexpected error reading adjacent letters map file {filepath}: {e}")
        raise

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
    try:
        all_words = top_n_list("en", config.top_n * Constants.WORDFREQ_MULTIPLIER)
    except Exception as e:
        logger.error(f"✗ Failed to load words from wordfreq: {e}")
        logger.error("  This may indicate a problem with the 'wordfreq' package")
        logger.error("  or network connectivity issues")
        raise RuntimeError("Failed to load source words from wordfreq") from e

    # Filter words using a generator expression for efficiency
    max_len = config.max_word_length or float("inf")
    valid_words = (
        word.lower()
        for word in all_words
        if config.min_word_length <= len(word) <= max_len and not any(c in word for c in "\n\r\t\\")
    )

    # Take the top N valid words
    return list(itertools.islice(valid_words, config.top_n))


def load_all_source_words(
    config: Config,
    exclude_filepath: str | None,
    verbose: bool = False,
) -> list[str]:
    """Get ALL words from english-words dictionary (minus exclusions).

    This function loads the full english-words dictionary and applies
    exclusions and length filters. Used when --hurtmycpu flag is enabled.

    Args:
        config: Configuration object with length constraints
        exclude_filepath: Path to exclusion patterns file
        verbose: Whether to print verbose output

    Returns:
        Sorted list of valid words from english-words dictionary
    """
    if verbose:
        logger.info("  Loading ALL words from english-words dictionary...")
        logger.warning("  ⚠️  This will take a very long time!")

    try:
        # type: ignore[no-any-return]
        words: set[str] = get_english_words_set(["web2", "gcide"], lower=True)
    except Exception as e:
        logger.error(f"✗ Failed to load English words dictionary: {e}")
        logger.error("  This may indicate a problem with the 'english-words' package")
        logger.error("  Try reinstalling: pip install english-words")
        raise RuntimeError("Failed to load english-words dictionary") from e

    original_word_count = len(words)

    # Apply exclusions
    exclusion_patterns = load_exclusions(exclude_filepath, verbose=False)
    word_exclusion_patterns = {
        p for p in exclusion_patterns if Constants.EXCLUSION_SEPARATOR not in p
    }
    if word_exclusion_patterns:
        pattern_matcher = PatternMatcher(word_exclusion_patterns)
        words = pattern_matcher.filter_set(words)

    # Filter by length constraints
    max_len = config.max_word_length or float("inf")
    valid_words = [
        word
        for word in words
        if config.min_word_length <= len(word) <= max_len and not any(c in word for c in "\n\r\t\\")
    ]

    removed_count = original_word_count - len(valid_words)
    if verbose:
        logger.info(f"  Loaded {len(valid_words)} words from english-words dictionary")
        if removed_count > 0:
            logger.info(f"  Removed {removed_count} words based on exclusions and length filters")

    # Sort for deterministic output
    return sorted(valid_words)
