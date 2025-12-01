"""Word processing and typo generation."""

from entroppy.core import BoundaryType, Correction, determine_boundaries, generate_all_typos
from entroppy.core.boundaries import BoundaryIndex
from entroppy.matching import PatternMatcher
from entroppy.utils.debug import DebugTypoMatcher, is_debug_word, is_debug_typo
from entroppy.utils.helpers import cached_word_frequency


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
    filtered_validation_set: set[str],
    source_words: set[str],
    typo_freq_threshold: float,
    adj_letters_map: dict[str, str] | None,
    exclusions: set[str],
    validation_index: BoundaryIndex,
    source_index: BoundaryIndex,
    debug_words: frozenset[str] = frozenset(),
    debug_typo_matcher: "DebugTypoMatcher | None" = None,
) -> tuple[list[Correction], list[str]]:
    """Process a single word and generate all valid corrections.

    Args:
        word: The word to generate typos for
        validation_set: Full validation dictionary (for checking if typo is a real word)
        filtered_validation_set: Filtered validation set
            (for boundary detection, excludes exclusion patterns)
        source_words: Set of source words
        typo_freq_threshold: Frequency threshold for typos
        adj_letters_map: Adjacent letters map for insertions/replacements
        exclusions: Set of exclusion patterns
        debug_words: Set of words to debug (exact matches)
        debug_typo_matcher: Matcher for debug typos (with wildcards/boundaries)

    Returns:
        Tuple of (corrections list, debug messages list)
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

        # Use filtered validation set for boundary detection
        # This allows excluded patterns to not block valid typos
        boundary_type = determine_boundaries(
            typo, filtered_validation_set, source_words, validation_index, source_index
        )

        if boundary_type is not None:
            # Now that we have the boundary, check if this typo matches any debug patterns
            if debug_typo_matcher:
                matched_patterns = debug_typo_matcher.get_matching_patterns(typo, boundary_type)
                if matched_patterns:
                    patterns_str = ", ".join(matched_patterns)
                    debug_messages.append(
                        f"[DEBUG TYPO: '{typo}' (matched: {patterns_str})] "
                        f"[Stage 2] Generated from word: {word} (boundary: {boundary_type.value})"
                    )

            if is_debug:
                debug_messages.append(
                    f"[DEBUG WORD: '{word}'] [Stage 2] Created correction: "
                    f"{typo} → {word} (boundary: {boundary_type.value})"
                )

            corrections.append((typo, word, boundary_type))
        else:
            # Boundary detection failed
            _add_debug_message(
                debug_messages,
                is_debug,
                typo_debug_check,
                word,
                typo,
                f"Typo '{typo}' filtered - boundary detection failed",
                "Filtered - boundary detection failed",
            )

    return corrections, debug_messages
