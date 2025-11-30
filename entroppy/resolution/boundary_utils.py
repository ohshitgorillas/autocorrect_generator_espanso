"""Boundary type utilities for collision resolution."""

from typing import TYPE_CHECKING

from ..core import BoundaryType
from ..utils import is_debug_correction, log_debug_correction

if TYPE_CHECKING:
    from ..utils import DebugTypoMatcher


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


def _should_skip_short_typo(
    typo: str,
    word: str,
    min_typo_length: int,
    min_word_length: int,
) -> bool:
    """Check if a typo should be skipped due to being too short.

    A short typo is permissible if it corrects to a word that is also short,
    using the user's `min_word_length` as the threshold.

    Args:
        typo: The typo string
        word: The correct word
        min_typo_length: Minimum typo length
        min_word_length: Minimum word length

    Returns:
        True if the typo should be skipped, False otherwise
    """
    return len(typo) < min_typo_length and len(word) > min_word_length


def apply_user_word_boundary_override(
    word: str,
    boundary: BoundaryType,
    user_words: set[str],
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
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
        if is_debug_correction(correction, debug_words, debug_typo_matcher):
            log_debug_correction(
                correction,
                f"Forced BOTH boundary (2-letter user word, was {orig_boundary.value})",
                debug_words,
                debug_typo_matcher,
                "Stage 3",
            )
    return boundary

