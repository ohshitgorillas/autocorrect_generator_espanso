"""Stage 1: Dictionary loading and initialization."""

import time

from loguru import logger

from ..config import Config
from ..dictionary import (
    load_adjacent_letters,
    load_exclusions,
    load_source_words,
    load_validation_dictionary,
    load_word_list,
)
from ..exclusions import ExclusionMatcher
from .data_models import DictionaryData


def load_dictionaries(config: Config, verbose: bool = False) -> DictionaryData:
    """Load all dictionaries, exclusions, and source words.

    Args:
        config: Configuration object
        verbose: Whether to print verbose output

    Returns:
        DictionaryData containing all loaded resources
    """
    start_time = time.time()

    # Load validation dictionary
    validation_set = load_validation_dictionary(config.exclude, config.include, verbose)

    # Load exclusions and create matcher
    exclusions = load_exclusions(config.exclude, verbose)
    exclusion_matcher = ExclusionMatcher(exclusions)

    # Filter validation set for boundary detection
    # This removes words matching exclusion patterns so they don't block valid typos
    filtered_validation_set = exclusion_matcher.filter_validation_set(validation_set)

    if verbose and len(filtered_validation_set) != len(validation_set):
        removed = len(validation_set) - len(filtered_validation_set)
        logger.info(
            f"Filtered {removed} words from validation set using exclusion patterns"
        )

    # Load adjacent letters mapping
    adjacent_letters_map = load_adjacent_letters(config.adjacent_letters, verbose)

    # Load source words
    user_words = load_word_list(config.include, verbose)
    if verbose and user_words:
        logger.info(f"Loaded {len(user_words)} words from include file")

    user_words_set = set(user_words)
    source_words = load_source_words(config, verbose)
    source_words.extend(user_words)

    if verbose and user_words:
        logger.info(
            f"Included {len(user_words)} user words (bypassed filters)"
        )

    source_words_set = set(source_words)

    elapsed_time = time.time() - start_time

    return DictionaryData(
        validation_set=validation_set,
        filtered_validation_set=filtered_validation_set,
        exclusions=exclusions,
        exclusion_matcher=exclusion_matcher,
        adjacent_letters_map=adjacent_letters_map,
        source_words=source_words,
        source_words_set=source_words_set,
        user_words_set=user_words_set,
        elapsed_time=elapsed_time,
    )
