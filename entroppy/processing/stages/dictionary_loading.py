"""Stage 1: Dictionary loading and initialization."""

import time

from loguru import logger

from entroppy.core import Config
from entroppy.data import (
    load_adjacent_letters_map,
    load_all_source_words,
    load_exclusions,
    load_source_words,
    load_validation_dictionary,
    load_word_list,
)
from entroppy.matching import ExclusionMatcher
from entroppy.processing.stages.data_models import DictionaryData
from entroppy.processing.stages.dictionary_loading_logging import (
    log_typo_validation_check,
    log_word_loading,
)


def _load_and_filter_validation_set(
    exclude_filepath: str | None, include_filepath: str | None, verbose: bool
) -> tuple[set[str], set[str], set[str], ExclusionMatcher]:
    """Load validation dictionary and apply exclusions."""
    validation_set = load_validation_dictionary(exclude_filepath, include_filepath, verbose)

    # Load exclusions and create matcher
    exclusions = load_exclusions(exclude_filepath, verbose)
    exclusion_matcher = ExclusionMatcher(exclusions)

    # Filter validation set for boundary detection
    # This removes words matching exclusion patterns so they don't block valid typos
    filtered_validation_set = exclusion_matcher.filter_validation_set(validation_set)

    if verbose and len(filtered_validation_set) != len(validation_set):
        removed = len(validation_set) - len(filtered_validation_set)
        logger.info(f"  Filtered {removed} words from validation set using exclusion patterns")

    return validation_set, filtered_validation_set, exclusions, exclusion_matcher


def _load_source_words(config: Config, user_words: list[str], verbose: bool) -> list[str]:
    """Load source words based on configuration."""
    if config.hurtmycpu:
        if verbose:
            logger.info("  🚀 HURTMYCPU MODE: Generating typos for ALL english-words...")
            logger.warning("  ⚠️  This will take a very long time!")
        source_words = load_all_source_words(config, config.exclude, verbose)
    else:
        source_words = load_source_words(config, verbose)

    source_words.extend(user_words)
    if verbose and user_words:
        logger.info(f"  Included {len(user_words)} user words (bypassed filters)")

    return source_words


def _process_debug_logging(
    config: Config,
    user_words_set: set[str],
    source_words: list[str],
    validation_set: set[str],
    exclusion_matcher: ExclusionMatcher,
    debug_messages: list[str],
) -> None:
    """Process debug logging for words and typos.

    Args:
        config: Configuration object
        user_words_set: Set of user-provided words
        source_words: List of source words
        validation_set: Set of validation words
        exclusion_matcher: Exclusion matcher
        debug_messages: List to collect debug messages into
    """
    if config.debug_words:
        for word in config.debug_words:
            log_word_loading(
                word,
                user_words_set,
                source_words,
                config.top_n,
                config.max_word_length,
                config.min_word_length,
                debug_messages,
            )

    if config.debug_typo_matcher:
        # Check all patterns against validation set
        # We'll check exact patterns (not wildcards) for validation
        all_patterns = config.debug_typos
        for pattern_str in all_patterns:
            # For exact patterns, check directly
            if "*" not in pattern_str and ":" not in pattern_str:
                typo = pattern_str
                log_typo_validation_check(
                    typo, pattern_str, validation_set, exclusion_matcher, debug_messages
                )


def load_dictionaries(config: Config, verbose: bool = False) -> DictionaryData:
    """Load all dictionaries, exclusions, and source words.

    Args:
        config: Configuration object
        verbose: Whether to print verbose output

    Returns:
        DictionaryData containing all loaded resources
    """
    start_time = time.time()

    # Load validation dictionary and exclusions
    validation_set, filtered_validation_set, exclusions, exclusion_matcher = (
        _load_and_filter_validation_set(config.exclude, config.include, verbose)
    )

    # Load adjacent letters mapping
    adjacent_letters_map = load_adjacent_letters_map(config.adjacent_letters, verbose)

    # Load source words
    user_words = load_word_list(config.include, verbose)
    if verbose and user_words:
        logger.info(f"  Loaded {len(user_words)} words from include file")

    user_words_set = set(user_words)
    source_words = _load_source_words(config, user_words, verbose)
    source_words_set = set(source_words)

    # Debug logging for Stage 1 - collect messages
    debug_messages: list[str] = []
    _process_debug_logging(
        config, user_words_set, source_words, validation_set, exclusion_matcher, debug_messages
    )

    elapsed_time = time.time() - start_time

    return DictionaryData(
        validation_set=validation_set,
        filtered_validation_set=filtered_validation_set,
        exclusions=exclusions,
        exclusion_matcher=exclusion_matcher,
        adjacent_letters_map=(adjacent_letters_map if adjacent_letters_map is not None else {}),
        source_words=source_words,
        source_words_set=source_words_set,
        user_words_set=user_words_set,
        debug_messages=debug_messages,
        elapsed_time=elapsed_time,
    )
