"""Helper functions for collision resolution in correction processing."""

from typing import TYPE_CHECKING

from entroppy.core import BoundaryType
from entroppy.utils.debug import log_debug_typo
from entroppy.utils.helpers import cached_word_frequency

if TYPE_CHECKING:
    from entroppy.utils.debug import DebugTypoMatcher


def _resolve_collision_by_frequency(
    words_in_group: list[str],
    freq_ratio: float,
) -> tuple[str | None, float]:
    """Resolve collision by frequency analysis.

    Args:
        words_in_group: List of words in collision
        freq_ratio: Minimum frequency ratio for resolution

    Returns:
        Tuple of (selected_word, ratio). selected_word is None if ambiguous.
    """
    word_freqs = [(w, cached_word_frequency(w, "en")) for w in words_in_group]
    word_freqs.sort(key=lambda x: x[1], reverse=True)

    most_common = word_freqs[0]
    second_most = word_freqs[1] if len(word_freqs) > 1 else (None, 0)
    ratio = most_common[1] / second_most[1] if second_most[1] > 0 else float("inf")

    if ratio > freq_ratio:
        return most_common[0], ratio
    return None, ratio


def _log_collision_debug(
    typo: str,
    words_in_group: list[str],
    boundary: BoundaryType,
    ratio: float,
    freq_ratio: float,
    is_resolved: bool,
    debug_typo_matcher: "DebugTypoMatcher | None",
) -> None:
    """Log debug information for collision resolution.

    Args:
        typo: The typo string
        words_in_group: List of words in collision
        boundary: The boundary type
        ratio: Frequency ratio
        freq_ratio: Minimum frequency ratio threshold
        is_resolved: Whether collision was resolved
        debug_typo_matcher: Matcher for debug typos
    """
    word_freqs = [(w, cached_word_frequency(w, "en")) for w in words_in_group]
    words_with_freqs = ", ".join([f"{w} (freq: {f:.2e})" for w, f in word_freqs])
    matched_patterns = (
        debug_typo_matcher.get_matching_patterns(typo, boundary) if debug_typo_matcher else None
    )

    if is_resolved:
        log_debug_typo(
            typo,
            f"Collision for boundary {boundary.value}: {typo} → [{words_with_freqs}] "
            f"(ratio: {ratio:.2f})",
            matched_patterns,
            "Stage 3",
        )
    else:
        log_debug_typo(
            typo,
            f"SKIPPED - ambiguous collision for boundary {boundary.value}: "
            f"{words_in_group}, ratio {ratio:.2f} <= threshold {freq_ratio}",
            matched_patterns,
            "Stage 3",
        )


def _log_initial_collision(
    typo: str,
    unique_words: list[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
) -> None:
    """Log initial collision detection for debugging.

    Args:
        typo: The typo string
        unique_words: List of unique words competing for this typo
        debug_typo_matcher: Matcher for debug typos
    """
    word_freqs = [(w, cached_word_frequency(w, "en")) for w in unique_words]
    words_with_freqs = ", ".join([f"{w} (freq: {f:.2e})" for w, f in word_freqs])
    matched_patterns = (
        debug_typo_matcher.get_matching_patterns(typo, BoundaryType.NONE)
        if debug_typo_matcher
        else None
    )
    log_debug_typo(
        typo,
        f"Collision detected: {typo} → [{words_with_freqs}]",
        matched_patterns,
        "Stage 3",
    )
