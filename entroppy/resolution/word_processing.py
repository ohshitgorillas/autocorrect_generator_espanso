"""Word processing and typo generation."""

from typing import TYPE_CHECKING

from entroppy.core import BoundaryType, generate_all_typos
from entroppy.matching import PatternMatcher
from entroppy.utils.debug import is_debug_typo, is_debug_word
from entroppy.utils.helpers import cached_word_frequency

from .word_processing_logging import (
    add_debug_message,
    log_typo_accepted,
    log_typo_generated,
    log_typo_pattern_match,
    log_word_processing_start,
)

if TYPE_CHECKING:
    from entroppy.resolution.state import DictionaryState
    from entroppy.utils.debug import DebugTypoMatcher


def _would_drop_s_suffix(typo: str, word: str) -> bool:
    """Check if typo would drop 's' suffix."""
    return len(typo) == len(word) + 1 and typo.endswith("s") and typo[:-1] == word


def _would_drop_ed_suffix(typo: str, word: str) -> bool:
    """Check if typo would drop 'ed' suffix."""
    # Case 1: Typo ends in 'ed' and is two chars longer
    if len(typo) == len(word) + 2 and typo.endswith("ed") and typo[:-2] == word:
        return True
    # Case 2: Typo ends in 'd' with 'e' as second-to-last, and is one char longer
    return (
        len(typo) == len(word) + 1
        and typo.endswith("d")
        and len(typo) >= 2
        and typo[-2] == "e"
        and typo[:-1] == word
    )


def _would_drop_er_suffix(typo: str, word: str) -> bool:
    """Check if typo would drop 'er' suffix."""
    # Case 1: Typo ends in 'er' and is two chars longer
    if len(typo) == len(word) + 2 and typo.endswith("er") and typo[:-2] == word:
        return True
    # Case 2: Typo ends in 'r' with 'e' as second-to-last, and is one char longer
    return (
        len(typo) == len(word) + 1
        and typo.endswith("r")
        and len(typo) >= 2
        and typo[-2] == "e"
        and typo[:-1] == word
    )


def _would_drop_or_suffix(typo: str, word: str) -> bool:
    """Check if typo would drop 'or' suffix."""
    # Case 1: Typo ends in 'or' and is two chars longer
    if len(typo) == len(word) + 2 and typo.endswith("or") and typo[:-2] == word:
        return True
    # Case 2: Typo ends in 'r' with 'o' as second-to-last, and is one char longer
    return (
        len(typo) == len(word) + 1
        and typo.endswith("r")
        and len(typo) >= 2
        and typo[-2] == "o"
        and typo[:-1] == word
    )


def _would_drop_valid_suffix(typo: str, word: str) -> bool:
    """Check if correcting typo to word would drop a valid grammatical suffix.

    This guard prevents corrections that would drop legitimate suffixes like:
    - 's' (plural): keyboards -> keyboard
    - 'ed' (past tense): depreciated -> depreciate
    - 'er' (comparative): typer -> type
    - 'or' (agent noun): actor -> act

    Args:
        typo: The typo string
        word: The correction word

    Returns:
        True if correcting typo to word would drop a valid suffix, False otherwise
    """
    # Typo must be longer than word for it to drop a suffix
    if len(typo) <= len(word):
        return False

    return (
        _would_drop_s_suffix(typo, word)
        or _would_drop_ed_suffix(typo, word)
        or _would_drop_er_suffix(typo, word)
        or _would_drop_or_suffix(typo, word)
    )


def _should_filter_typo(
    typo: str,
    word: str,
    source_words: set[str],
    validation_set: set[str],
    exclusion_matcher: PatternMatcher,
    typo_freq_threshold: float,
) -> tuple[bool, str | None]:
    """Check if a typo should be filtered and return the reason.

    Args:
        typo: The typo to check
        word: The correction word
        source_words: Set of source words
        validation_set: Full validation dictionary
        exclusion_matcher: Matcher for exclusion patterns
        typo_freq_threshold: Frequency threshold for typos

    Returns:
        Tuple of (should_filter, reason_message) where reason_message is None if
        typo should not be filtered
    """
    if typo in source_words:
        return True, "is a source word"

    if typo in validation_set:
        return True, "is a valid word in dictionary"

    is_explicitly_excluded = exclusion_matcher.matches(typo)
    if not is_explicitly_excluded and typo_freq_threshold > 0.0:
        typo_freq = cached_word_frequency(typo, "en")
        if typo_freq >= typo_freq_threshold:
            return True, f"frequency {typo_freq:.2e} >= threshold {typo_freq_threshold:.2e}"

    if _would_drop_valid_suffix(typo, word):
        return True, "would drop a protected suffix"

    return False, None


def process_word(
    word: str,
    validation_set: set[str],
    source_words: set[str],
    typo_freq_threshold: float,
    adj_letters_map: dict[str, str] | None,
    exclusions: set[str],
    debug_words: frozenset[str] = frozenset(),
    debug_typo_matcher: "DebugTypoMatcher | None" = None,
    state: "DictionaryState | None" = None,
) -> tuple[list[tuple[str, str]], list[str]]:
    """Process a single word and generate all valid typos.

    Args:
        word: The word to generate typos for
        validation_set: Full validation dictionary (for checking if typo is a real word)
        source_words: Set of source words
        typo_freq_threshold: Frequency threshold for typos
        adj_letters_map: Adjacent letters map for insertions/replacements
        exclusions: Set of exclusion patterns
        debug_words: Set of words to debug (exact matches)
        debug_typo_matcher: Matcher for debug typos (with wildcards/boundaries)
        state: Optional dictionary state for storing structured debug data

    Returns:
        Tuple of (list of (typo, word) pairs, debug messages list)
        Note: Boundaries are determined later in Stage 3 (collision resolution)
    """
    corrections = []
    debug_messages: list[str] = []
    is_debug = is_debug_word(word, debug_words)

    log_word_processing_start(debug_messages, word, debug_words, state)

    typos = generate_all_typos(word, adj_letters_map)

    # Filter out typo->word patterns, keep only single word exclusion patterns
    word_exclusion_patterns = {p for p in exclusions if "->" not in p}
    exclusion_matcher = PatternMatcher(word_exclusion_patterns)

    for typo in typos:
        if typo == word:
            continue

        # Check if this typo is being debugged (before we know boundary)
        # For now, check with NONE boundary as a placeholder
        typo_debug_check = is_debug_typo(typo, BoundaryType.NONE, debug_typo_matcher)

        log_typo_generated(debug_messages, word, typo, debug_words, state)

        # Check if typo should be filtered
        should_filter, filter_reason = _should_filter_typo(
            typo,
            word,
            source_words,
            validation_set,
            exclusion_matcher,
            typo_freq_threshold,
        )

        if should_filter:
            word_msg = f"Typo '{typo}' filtered - {filter_reason}"
            typo_msg = f"Filtered - {filter_reason}"
            add_debug_message(
                debug_messages,
                is_debug,
                typo_debug_check,
                word,
                typo,
                word_msg,
                typo_msg,
                debug_typo_matcher,
            )
            continue

        # Note: Boundaries are determined in Stage 3 (collision resolution) where
        # they can be properly evaluated in context of all competing words and typos.
        # For debug logging, we use NONE as a placeholder since boundary isn't determined yet.
        log_typo_pattern_match(debug_messages, typo, word, debug_typo_matcher, state)

        log_typo_accepted(debug_messages, word, typo, debug_words, state, BoundaryType.NONE)

        # Store only (typo, word) - boundary will be determined in Stage 3
        corrections.append((typo, word))

    return corrections, debug_messages
