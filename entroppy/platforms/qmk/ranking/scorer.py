"""Scoring functions for QMK ranking."""

from typing import TYPE_CHECKING, Iterable

from tqdm import tqdm

from entroppy.core import BoundaryType, Correction
from entroppy.platforms.qmk.qmk_logging import log_direct_scoring, log_pattern_scoring
from entroppy.utils.helpers import cached_word_frequency

if TYPE_CHECKING:
    from entroppy.utils.debug import DebugTypoMatcher


def _collect_all_words(
    pattern_corrections: list[Correction],
    direct_corrections: list[Correction],
    pattern_replacements: dict[Correction, list[Correction]],
) -> set[str]:
    """Collect all unique words that need frequency lookups.

    Args:
        pattern_corrections: List of pattern corrections
        direct_corrections: List of direct corrections
        pattern_replacements: Dictionary mapping patterns to their replacements

    Returns:
        Set of all unique words that need frequency lookups
    """
    all_words = set()

    # Collect words from direct corrections
    for _, word, _ in direct_corrections:
        all_words.add(word)

    # Collect words from pattern replacements
    for pattern in pattern_corrections:
        pattern_key = (pattern[0], pattern[1], pattern[2])
        if pattern_key in pattern_replacements:
            for _, replaced_word, _ in pattern_replacements[pattern_key]:
                all_words.add(replaced_word)

    return all_words


def _build_word_frequency_cache(all_words: set[str], verbose: bool = False) -> dict[str, float]:
    """Pre-compute word frequencies for all unique words.

    This batch lookup optimization eliminates redundant wordfreq library calls
    and provides O(1) lookups during scoring.

    Args:
        all_words: Set of all unique words to look up
        verbose: Whether to show progress bars

    Returns:
        Dictionary mapping words to their frequencies
    """
    word_iter: Iterable[str]
    if verbose:
        word_iter = tqdm(
            all_words, desc="  Pre-computing word frequencies", unit="word", leave=False
        )
    else:
        word_iter = all_words

    return {word: cached_word_frequency(word, "en") for word in word_iter}


def score_patterns(
    pattern_corrections: list[Correction],
    pattern_replacements: dict[Correction, list[Correction]],
    word_freq_cache: dict[str, float],
    verbose: bool = False,
    debug_words: set[str] | None = None,
    debug_typo_matcher: "DebugTypoMatcher | None" = None,
) -> list[tuple[float, str, str, BoundaryType]]:
    """Score patterns by sum of replaced word frequencies.

    Args:
        pattern_corrections: List of pattern corrections to score
        pattern_replacements: Dictionary mapping patterns to their replacements
        word_freq_cache: Pre-computed word frequency cache for O(1) lookups
        verbose: Whether to show progress bars
        debug_words: Set of words to debug (exact matches)
        debug_typo_matcher: Matcher for debug typos (with wildcards/boundaries)

    Returns:
        List of (score, typo, word, boundary) tuples
    """
    scores = []
    if verbose:
        pattern_iter: list[Correction] = list(
            tqdm(
                pattern_corrections,
                desc="  Scoring patterns",
                unit="pattern",
                leave=False,
            )
        )
    else:
        pattern_iter = pattern_corrections

    for typo, word, boundary in pattern_iter:
        pattern_key = (typo, word, boundary)
        correction = (typo, word, boundary)

        if pattern_key in pattern_replacements:
            replacements = pattern_replacements[pattern_key]
            # Use pre-computed word frequency cache for O(1) lookups
            total_freq = sum(
                word_freq_cache.get(replaced_word, 0.0) for _, replaced_word, _ in replacements
            )
            scores.append((total_freq, typo, word, boundary))

            # Only build replacement_words list if debug logging is needed
            if debug_words or debug_typo_matcher:
                replacement_words = [w for _, w, _ in replacements]
                replacement_list = ", ".join(replacement_words[:5])
                if len(replacement_words) > 5:
                    replacement_list += "..."
            else:
                replacement_list = ""

            log_pattern_scoring(
                correction,
                total_freq,
                len(replacements),
                replacement_list,
                debug_words or set(),
                debug_typo_matcher,
            )
    return scores


def score_direct_corrections(
    direct_corrections: list[Correction],
    word_freq_cache: dict[str, float],
    verbose: bool = False,
    debug_words: set[str] | None = None,
    debug_typo_matcher: "DebugTypoMatcher | None" = None,
) -> list[tuple[float, str, str, BoundaryType]]:
    """Score direct corrections by word frequency.

    Args:
        direct_corrections: List of direct corrections to score
        word_freq_cache: Pre-computed word frequency cache for O(1) lookups
        verbose: Whether to show progress bars
        debug_words: Set of words to debug (exact matches)
        debug_typo_matcher: Matcher for debug typos (with wildcards/boundaries)

    Returns:
        List of (score, typo, word, boundary) tuples
    """
    scores = []
    if verbose:
        direct_iter: list[Correction] = list(
            tqdm(
                direct_corrections,
                desc="  Scoring direct corrections",
                unit="correction",
                leave=False,
            )
        )
    else:
        direct_iter = direct_corrections

    for typo, word, boundary in direct_iter:
        correction = (typo, word, boundary)

        # Use pre-computed word frequency cache for O(1) lookups
        freq = word_freq_cache.get(word, 0.0)
        scores.append((freq, typo, word, boundary))
        log_direct_scoring(correction, freq, debug_words or set(), debug_typo_matcher)
    return scores
