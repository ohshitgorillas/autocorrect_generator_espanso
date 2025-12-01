"""Word processing and typo generation."""

from typing import TYPE_CHECKING

from entroppy.core import BoundaryType, generate_all_typos
from entroppy.matching import PatternMatcher
from entroppy.utils.debug import is_debug_word, is_debug_typo
from entroppy.utils.helpers import cached_word_frequency

if TYPE_CHECKING:
    from entroppy.utils.debug import DebugTypoMatcher


def _add_debug_message(
    debug_messages: list[str],
    is_debug: bool,
    typo_debug_check: bool,
    word: str,
    typo: str,
    message_word: str,
    message_typo: str,
) -> None:
    """Add debug messages for both word and typo debugging.

    Args:
        debug_messages: List to append messages to
        is_debug: Whether the word is being debugged
        typo_debug_check: Whether the typo is being debugged
        word: The word being processed
        typo: The typo being processed
        message_word: Message to add for word debugging
        message_typo: Message to add for typo debugging
    """
    if is_debug:
        debug_messages.append(f"[DEBUG WORD: '{word}'] [Stage 2] {message_word}")
    if typo_debug_check:
        debug_messages.append(f"[DEBUG TYPO: '{typo}'] [Stage 2] {message_typo}")


def process_word(
    word: str,
    validation_set: set[str],
    source_words: set[str],
    typo_freq_threshold: float,
    adj_letters_map: dict[str, str] | None,
    exclusions: set[str],
    debug_words: frozenset[str] = frozenset(),
    debug_typo_matcher: "DebugTypoMatcher | None" = None,
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

    Returns:
        Tuple of (list of (typo, word) pairs, debug messages list)
        Note: Boundaries are determined later in Stage 3 (collision resolution)
    """
    corrections = []
    debug_messages = []
    is_debug = is_debug_word(word, debug_words)

    if is_debug:
        debug_messages.append(f"[DEBUG WORD: '{word}'] [Stage 2] Generating typos for debug word")

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

        if is_debug:
            debug_messages.append(f"[DEBUG WORD: '{word}'] [Stage 2] Generated typo: {typo}")

        # Skip if typo is a source word (from includes file)
        if typo in source_words:
            _add_debug_message(
                debug_messages,
                is_debug,
                typo_debug_check,
                word,
                typo,
                f"Typo '{typo}' filtered - is a source word",
                "Filtered - is a source word",
            )
            continue

        # Use full validation set to check if typo is a real word
        if typo in validation_set:
            _add_debug_message(
                debug_messages,
                is_debug,
                typo_debug_check,
                word,
                typo,
                f"Typo '{typo}' filtered - is a valid word",
                "Filtered - is a valid word in dictionary",
            )
            continue

        # If user explicitly excludes a typo, it bypasses the frequency check.
        # This makes the user's exclusion the final authority.
        is_explicitly_excluded = exclusion_matcher.matches(typo)

        if not is_explicitly_excluded and typo_freq_threshold > 0.0:
            typo_freq = cached_word_frequency(typo, "en")
            if typo_freq >= typo_freq_threshold:
                freq_msg = f"frequency {typo_freq:.2e} >= threshold {typo_freq_threshold:.2e}"
                _add_debug_message(
                    debug_messages,
                    is_debug,
                    typo_debug_check,
                    word,
                    typo,
                    f"Typo '{typo}' filtered - {freq_msg}",
                    f"Filtered - {freq_msg}",
                )
                continue

        # Note: Boundaries are determined in Stage 3 (collision resolution) where
        # they can be properly evaluated in context of all competing words and typos.
        # For debug logging, we use NONE as a placeholder since boundary isn't determined yet.
        placeholder_boundary = BoundaryType.NONE

        # Check if this typo matches any debug patterns
        if debug_typo_matcher:
            matched_patterns = debug_typo_matcher.get_matching_patterns(typo, placeholder_boundary)
            if matched_patterns:
                patterns_str = ", ".join(matched_patterns)
                debug_messages.append(
                    f"[DEBUG TYPO: '{typo}' (matched: {patterns_str})] "
                    f"[Stage 2] Generated from word: {word}"
                )

        if is_debug:
            debug_messages.append(
                f"[DEBUG WORD: '{word}'] [Stage 2] Generated typo: {typo} → {word}"
            )

        # Store only (typo, word) - boundary will be determined in Stage 3
        corrections.append((typo, word))

    return corrections, debug_messages
