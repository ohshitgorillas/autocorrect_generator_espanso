"""Stage 1: Dictionary loading and initialization."""

import time

from loguru import logger
from wordfreq import zipf_frequency

from entroppy.core import BoundaryType, Config
from entroppy.data import (
    load_adjacent_letters_map,
    load_exclusions,
    load_source_words,
    load_validation_dictionary,
    load_word_list,
)
from entroppy.matching import ExclusionMatcher
from entroppy.utils import log_debug_typo, log_debug_word
from entroppy.processing.stages.data_models import DictionaryData


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
        logger.info(f"Filtered {removed} words from validation set using exclusion patterns")

    # Load adjacent letters mapping
    adjacent_letters_map = load_adjacent_letters_map(config.adjacent_letters, verbose)

    # Load source words
    user_words = load_word_list(config.include, verbose)
    if verbose and user_words:
        logger.info(f"Loaded {len(user_words)} words from include file")

    user_words_set = set(user_words)
    source_words = load_source_words(config, verbose)
    source_words.extend(user_words)

    if verbose and user_words:
        logger.info(f"Included {len(user_words)} user words (bypassed filters)")

    source_words_set = set(source_words)

    # Debug logging for Stage 1
    if config.debug_words:
        for word in config.debug_words:
            # Check if word is in user words
            if word in user_words_set:
                log_debug_word(word, "Found in user word list (include file)", "Stage 1")

            # Check if word is in source words
            if word in source_words_set:
                # Get frequency and rank info
                freq = zipf_frequency(word, "en")
                rank = source_words.index(word) + 1 if word in source_words else "N/A"
                log_debug_word(
                    word,
                    f"Included from wordfreq (rank: {rank}, zipf freq: {freq:.2f})",
                    "Stage 1",
                )
            else:
                # Word not in source words - explain why
                if config.top_n is None:
                    log_debug_word(word, "NOT in source words (top_n not specified)", "Stage 1")
                elif len(word) > config.max_word_length:
                    log_debug_word(
                        word,
                        f"NOT in source words (length {len(word)} > max_word_length "
                        f"{config.max_word_length})",
                        "Stage 1",
                    )
                elif len(word) < config.min_word_length:
                    log_debug_word(
                        word,
                        f"NOT in source words (length {len(word)} < min_word_length "
                        f"{config.min_word_length})",
                        "Stage 1",
                    )
                else:
                    freq = zipf_frequency(word, "en")
                    log_debug_word(
                        word,
                        f"NOT in source words (not in top {config.top_n}, zipf freq: {freq:.2f})",
                        "Stage 1",
                    )

    if config.debug_typo_matcher:
        # Check all patterns against validation set
        # We'll check exact patterns (not wildcards) for validation

        # Get all unique patterns to check
        all_patterns = config.debug_typos
        for pattern_str in all_patterns:
            # For exact patterns, check directly
            if "*" not in pattern_str and ":" not in pattern_str:
                typo = pattern_str
                # Check if typo is a valid word
                if typo in validation_set:
                    log_debug_typo(
                        typo,
                        "WARNING: Typo exists as valid word in dictionary",
                        [pattern_str],
                        "Stage 1",
                    )

                # Check if typo would be excluded by any exclusion rule
                # We need to test with all boundary types since we don't know yet
                for boundary in [
                    BoundaryType.NONE,
                    BoundaryType.LEFT,
                    BoundaryType.RIGHT,
                    BoundaryType.BOTH,
                ]:
                    test_correction = (typo, "test", boundary)
                    if exclusion_matcher.should_exclude(test_correction):
                        matching_rule = exclusion_matcher.get_matching_rule(test_correction)
                        log_debug_typo(
                            typo,
                            f"Typo matches exclusion rule (boundary={boundary.value}): "
                            f"{matching_rule}",
                            [pattern_str],
                            "Stage 1",
                        )
                        break  # Only log once

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
