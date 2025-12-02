"""QMK ranking and scoring logic."""

from tqdm import tqdm

from entroppy.core import BoundaryType, Correction
from entroppy.utils.helpers import cached_word_frequency


def separate_by_type(
    corrections: list[Correction],
    patterns: list[Correction],
    pattern_replacements: dict[Correction, list[Correction]],
    user_words: set[str],
    cached_pattern_typos: set[tuple[str, str]] | None = None,
    cached_replaced_by_patterns: set[tuple[str, str]] | None = None,
) -> tuple[list[Correction], list[Correction], list[Correction]]:
    """Separate corrections into user words, patterns, and direct corrections.

    Args:
        corrections: List of corrections to separate
        patterns: List of pattern corrections
        pattern_replacements: Dictionary mapping patterns to their replacements
        user_words: Set of user-defined words
        cached_pattern_typos: Optional cached set of (typo, word) tuples for patterns
        cached_replaced_by_patterns: Optional cached set of (typo, word) tuples replaced by patterns

    Returns:
        Tuple of (user_corrections, pattern_corrections, direct_corrections)
    """
    user_corrections = []
    pattern_corrections = []
    direct_corrections = []

    # Use cached sets if provided, otherwise build them
    if cached_pattern_typos is not None:
        pattern_typos = cached_pattern_typos
    else:
        pattern_typos = {(p[0], p[1]) for p in patterns}

    if cached_replaced_by_patterns is not None:
        replaced_by_patterns = cached_replaced_by_patterns
    else:
        replaced_by_patterns = set()
        for pattern in patterns:
            pattern_key = (pattern[0], pattern[1], pattern[2])
            if pattern_key in pattern_replacements:
                for replaced in pattern_replacements[pattern_key]:
                    replaced_by_patterns.add((replaced[0], replaced[1]))

    for typo, word, boundary in corrections:
        if word in user_words:
            user_corrections.append((typo, word, boundary))
        elif (typo, word) in pattern_typos:
            pattern_corrections.append((typo, word, boundary))
        elif (typo, word) not in replaced_by_patterns:
            direct_corrections.append((typo, word, boundary))

    return user_corrections, pattern_corrections, direct_corrections


def _build_pattern_sets(
    patterns: list[Correction], pattern_replacements: dict[Correction, list[Correction]]
) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    """Build pattern sets for caching.

    Args:
        patterns: List of pattern corrections
        pattern_replacements: Dictionary mapping patterns to their replacements

    Returns:
        Tuple of (pattern_typos, replaced_by_patterns) sets
    """
    pattern_typos = {(p[0], p[1]) for p in patterns}

    replaced_by_patterns = set()
    for pattern in patterns:
        pattern_key = (pattern[0], pattern[1], pattern[2])
        if pattern_key in pattern_replacements:
            for replaced in pattern_replacements[pattern_key]:
                replaced_by_patterns.add((replaced[0], replaced[1]))

    return pattern_typos, replaced_by_patterns


def score_patterns(
    pattern_corrections: list[Correction],
    pattern_replacements: dict[Correction, list[Correction]],
    verbose: bool = False,
) -> list[tuple[float, str, str, BoundaryType]]:
    """Score patterns by sum of replaced word frequencies."""
    scores = []
    pattern_iter = pattern_corrections
    if verbose:
        pattern_iter = tqdm(
            pattern_corrections, desc="  Scoring patterns", unit="pattern", leave=False
        )

    for typo, word, boundary in pattern_iter:
        pattern_key = (typo, word, boundary)
        if pattern_key in pattern_replacements:
            total_freq = sum(
                cached_word_frequency(replaced_word, "en")
                for _, replaced_word, _ in pattern_replacements[pattern_key]
            )
            scores.append((total_freq, typo, word, boundary))
    return scores


def score_direct_corrections(
    direct_corrections: list[Correction], verbose: bool = False
) -> list[tuple[float, str, str, BoundaryType]]:
    """Score direct corrections by word frequency."""
    scores = []
    direct_iter = direct_corrections
    if verbose:
        direct_iter = tqdm(
            direct_corrections,
            desc="  Scoring direct corrections",
            unit="correction",
            leave=False,
        )

    for typo, word, boundary in direct_iter:
        freq = cached_word_frequency(word, "en")
        scores.append((freq, typo, word, boundary))
    return scores


def rank_corrections(
    corrections: list[Correction],
    patterns: list[Correction],
    pattern_replacements: dict[Correction, list[Correction]],
    user_words: set[str],
    max_corrections: int | None = None,
    cached_pattern_typos: set[tuple[str, str]] | None = None,
    cached_replaced_by_patterns: set[tuple[str, str]] | None = None,
    verbose: bool = False,
) -> tuple[
    list[Correction],
    list[Correction],
    list[tuple[float, str, str, BoundaryType]],
    list[tuple[float, str, str, BoundaryType]],
    list[tuple[float, str, str, BoundaryType]],
]:
    """
    Rank corrections by QMK-specific usefulness.

    Three-tier system:
    1. User words (infinite priority)
    2. Patterns (scored by sum of replaced word frequencies)
    3. Direct corrections (scored by word frequency)

    Optimized to use a single unified sort with tier-based comparison instead of
    separate sorts for patterns and direct corrections.

    Args:
        corrections: List of corrections to rank
        patterns: List of pattern corrections
        pattern_replacements: Dictionary mapping patterns to their replacements
        user_words: Set of user-defined words
        max_corrections: Optional limit on number of corrections
        cached_pattern_typos: Optional cached set of (typo, word) tuples for patterns
        cached_replaced_by_patterns: Optional cached set of (typo, word) tuples replaced by patterns
        verbose: Whether to show progress bars

    Returns:
        Tuple of (ranked_corrections, user_corrections, pattern_scores, direct_scores, all_scored)
    """
    user_corrections, pattern_corrections, direct_corrections = separate_by_type(
        corrections,
        patterns,
        pattern_replacements,
        user_words,
        cached_pattern_typos,
        cached_replaced_by_patterns,
    )

    # Score all corrections with unified tier-based scoring
    # Tier 0: User words (handled separately, infinite priority)
    # Tier 1: Patterns (scored by sum of replacement frequencies)
    # Tier 2: Direct corrections (scored by word frequency)
    all_scored_items = []

    # Score patterns
    pattern_scores = score_patterns(pattern_corrections, pattern_replacements, verbose)
    for score, typo, word, boundary in pattern_scores:
        # Tier 1 for patterns
        all_scored_items.append((1, score, typo, word, boundary))

    # Score direct corrections
    direct_scores = score_direct_corrections(direct_corrections, verbose)
    for score, typo, word, boundary in direct_scores:
        # Tier 2 for direct corrections
        all_scored_items.append((2, score, typo, word, boundary))

    # Single unified sort: by tier (ascending), then by score (descending)
    # This ensures patterns (tier 1) come before direct (tier 2), and within each tier,
    # higher scores come first
    all_scored_items.sort(key=lambda x: (x[0], -x[1]))

    # Extract the scored items in sorted order (without tier)
    all_scored = [
        (score, typo, word, boundary) for _, score, typo, word, boundary in all_scored_items
    ]

    # Build ranked list: user words first, then sorted patterns and direct corrections
    ranked = user_corrections + [(t, w, b) for _, t, w, b in all_scored]

    # Apply max_corrections limit if specified
    if max_corrections:
        ranked = ranked[:max_corrections]

    return ranked, user_corrections, pattern_scores, direct_scores, all_scored
