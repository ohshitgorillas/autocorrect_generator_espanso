"""Debug logging functions for dictionary loading stage."""

from typing import TYPE_CHECKING

from wordfreq import zipf_frequency

from entroppy.core import BoundaryType
from entroppy.utils.debug import log_debug_typo, log_debug_word

if TYPE_CHECKING:
    from entroppy.matching import ExclusionMatcher


def log_word_loading(
    word: str,
    user_words_set: set[str],
    source_words: list[str],
    config_top_n: int | None,
    config_max_word_length: int,
    config_min_word_length: int,
) -> None:
    """Log debug information about word loading for debug words.

    Args:
        word: The word to check
        user_words_set: Set of user-provided words
        source_words: List of source words from wordfreq
        config_top_n: Top N words configuration
        config_max_word_length: Maximum word length
        config_min_word_length: Minimum word length
    """
    # Check if word is in user words
    if word in user_words_set:
        log_debug_word(word, "Found in user word list (include file)", "Stage 1")

    # Check if word is in source words
    source_words_set = set(source_words)
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
        if config_top_n is None:
            log_debug_word(word, "NOT in source words (top_n not specified)", "Stage 1")
        elif len(word) > config_max_word_length:
            log_debug_word(
                word,
                f"NOT in source words (length {len(word)} > max_word_length "
                f"{config_max_word_length})",
                "Stage 1",
            )
        elif len(word) < config_min_word_length:
            log_debug_word(
                word,
                f"NOT in source words (length {len(word)} < min_word_length "
                f"{config_min_word_length})",
                "Stage 1",
            )
        else:
            freq = zipf_frequency(word, "en")
            log_debug_word(
                word,
                f"NOT in source words (not in top {config_top_n}, zipf freq: {freq:.2f})",
                "Stage 1",
            )


def log_typo_validation_check(
    typo: str,
    pattern_str: str,
    validation_set: set[str],
    exclusion_matcher: "ExclusionMatcher",
) -> None:
    """Log debug information about typo validation for debug typos.

    Args:
        typo: The typo to check
        pattern_str: The original pattern string
        validation_set: Set of validation words
        exclusion_matcher: Exclusion matcher for checking exclusion rules
    """
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
                f"Typo matches exclusion rule (boundary={boundary.value}): {matching_rule}",
                [pattern_str],
                "Stage 1",
            )
            break  # Only log once
