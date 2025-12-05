"""Boundary type utilities for collision resolution."""

from entroppy.core import BoundaryType
from entroppy.core.boundaries import BoundaryIndex
from entroppy.utils.debug import DebugTypoMatcher, log_if_debug_correction


def _should_skip_short_typo(
    typo: str, word: str, min_typo_length: int, min_word_length: int
) -> bool:
    """Check if a typo should be skipped for being too short.

    Args:
        typo: The typo string
        word: The correct word
        min_typo_length: Minimum typo length
        min_word_length: Minimum word length

    Returns:
        True if typo should be skipped (typo is too short and word is long enough)
    """
    return len(typo) < min_typo_length and len(word) > min_word_length


def choose_strictest_boundary(boundaries: list[BoundaryType]) -> BoundaryType:
    """Choose the strictest boundary type."""
    if BoundaryType.BOTH in boundaries:
        return BoundaryType.BOTH
    if BoundaryType.LEFT in boundaries and BoundaryType.RIGHT in boundaries:
        return BoundaryType.BOTH
    if BoundaryType.LEFT in boundaries:
        return BoundaryType.LEFT
    if BoundaryType.RIGHT in boundaries:
        return BoundaryType.RIGHT
    return BoundaryType.NONE


def apply_user_word_boundary_override(
    word: str,
    boundary: BoundaryType,
    user_words: set[str],
    debug_words: set[str],
    debug_typo_matcher: DebugTypoMatcher | None,
    typo: str,
) -> BoundaryType:
    """Apply boundary override for 2-letter user words.

    Args:
        word: The word
        boundary: Current boundary type
        user_words: Set of user-provided words
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos
        typo: The typo (for debug logging)

    Returns:
        Updated boundary type (BOTH if word is 2-letter user word, otherwise original)
    """
    if word in user_words and len(word) == 2:
        orig_boundary = boundary
        boundary = BoundaryType.BOTH
        # Debug logging for forced BOTH boundary
        correction = (typo, word, boundary)
        log_if_debug_correction(
            correction,
            f"Forced BOTH boundary (2-letter user word, was {orig_boundary.value})",
            debug_words,
            debug_typo_matcher,
            "Stage 3",
        )
    return boundary


def _check_typo_in_target_word(
    typo: str,
    target_word: str | None,
) -> tuple[bool, bool, bool]:
    """Check if typo appears as prefix, suffix, or substring in target word.

    Args:
        typo: The typo string to check
        target_word: The target word to check against (None if not available)

    Returns:
        Tuple of (is_prefix, is_suffix, is_substring)
    """
    if target_word is None:
        return False, False, False

    # Check if typo is a prefix (excluding exact match)
    is_prefix = target_word.startswith(typo) and typo != target_word

    # Check if typo is a suffix (excluding exact match)
    is_suffix = target_word.endswith(typo) and typo != target_word

    # Check if typo is a substring (excluding exact match and prefix/suffix cases)
    is_substring = typo in target_word and typo != target_word and not is_prefix and not is_suffix

    return is_prefix, is_suffix, is_substring


def _get_example_words_with_prefix(
    typo: str, validation_index: BoundaryIndex, source_index: BoundaryIndex
) -> list[str]:
    """Get example words that have typo as a prefix.

    Args:
        typo: The typo string
        validation_index: Boundary index for validation set
        source_index: Boundary index for source words

    Returns:
        List of example words (up to 3 total, prioritizing validation words)
    """
    examples: list[str] = []
    # Check validation index first
    if typo in validation_index.prefix_index:
        for word in validation_index.prefix_index[typo]:
            if word != typo and len(examples) < 3:
                examples.append(word)
    # Then check source index if we need more examples
    if len(examples) < 3 and typo in source_index.prefix_index:
        for word in source_index.prefix_index[typo]:
            if word != typo and word not in examples and len(examples) < 3:
                examples.append(word)
    return examples


def _get_example_words_with_suffix(
    typo: str, validation_index: BoundaryIndex, source_index: BoundaryIndex
) -> list[str]:
    """Get example words that have typo as a suffix.

    Args:
        typo: The typo string
        validation_index: Boundary index for validation set
        source_index: Boundary index for source words

    Returns:
        List of example words (up to 3 total, prioritizing validation words)
    """
    examples: list[str] = []
    # Check validation index first
    if typo in validation_index.suffix_index:
        for word in validation_index.suffix_index[typo]:
            if word != typo and len(examples) < 3:
                examples.append(word)
    # Then check source index if we need more examples
    if len(examples) < 3 and typo in source_index.suffix_index:
        for word in source_index.suffix_index[typo]:
            if word != typo and word not in examples and len(examples) < 3:
                examples.append(word)
    return examples


def _get_example_words_with_substring(
    typo: str, validation_index: BoundaryIndex, source_index: BoundaryIndex
) -> list[str]:
    """Get example words that contain typo as a substring (not prefix/suffix).

    Args:
        typo: The typo string
        validation_index: Boundary index for validation set
        source_index: Boundary index for source words

    Returns:
        List of example words (up to 3 total, prioritizing validation words)
    """
    examples: list[str] = []
    # Check validation index first
    for word in validation_index.word_set:
        if (
            typo in word
            and word != typo
            and not word.startswith(typo)
            and not word.endswith(typo)
            and len(examples) < 3
        ):
            examples.append(word)
    # Then check source index if we need more examples
    if len(examples) < 3:
        for word in source_index.word_set:
            if (
                typo in word
                and word != typo
                and not word.startswith(typo)
                and not word.endswith(typo)
                and word not in examples
                and len(examples) < 3
            ):
                examples.append(word)
    return examples


def _format_incorrect_transformation(conflict_word: str, typo_str: str, word_str: str) -> str:
    """Format how the correction would incorrectly apply.

    Args:
        conflict_word: The word that would be incorrectly transformed
        typo_str: The typo string
        word_str: The target word string

    Returns:
        Formatted string showing the incorrect transformation
    """
    if conflict_word.startswith(typo_str):
        # Prefix case
        replacement = conflict_word.replace(typo_str, word_str, 1)
        return f'"{typo_str}" -> "{word_str}" in {conflict_word} -> {replacement}  xx INCORRECT'
    if conflict_word.endswith(typo_str):
        # Suffix case
        replacement = conflict_word.rsplit(typo_str, 1)[0] + word_str
        return f'"{typo_str}" -> "{word_str}" in {conflict_word} -> {replacement}  xx INCORRECT'
    # Middle substring case
    replacement = conflict_word.replace(typo_str, word_str, 1)
    return f'"{typo_str}" -> "{word_str}" in {conflict_word} -> {replacement}  xx INCORRECT'
