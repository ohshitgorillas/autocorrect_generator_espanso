"""Conflict resolution for substring typo corrections.

Example for left-to-right matching:
- herre → here
- wherre → where

When typing "wherre":
- Espanso sees "herre" at the end first (shorter match)
- Triggers: "w" + "here" = "where" ✓
- The "wherre" correction is redundant, remove it
"""

from abc import ABC, abstractmethod
from collections import defaultdict

from entroppy.core import BoundaryType, Correction
from entroppy.utils.debug import (
    DebugTypoMatcher,
    is_debug_correction,
    log_debug_correction,
    log_if_debug_correction,
)


class ConflictDetector(ABC):
    """Base class for detecting conflicts between typo corrections.

    A conflict occurs when:
    1. Two words produce the same typo.
    2. A longer typo contains a shorter typo as a substring.
    3. The shorter typo would trigger first due to Espanso's left-to-right matching.
    4. The result of triggering the shorter typo produces the correct word.

    Different boundary types require different conflict detection strategies.
    """

    @abstractmethod
    def contains_substring(self, long_typo: str, short_typo: str) -> bool:
        """Check if long_typo contains short_typo in the relevant position."""

    @abstractmethod
    def calculate_result(self, long_typo: str, short_typo: str, short_word: str) -> str:
        """Calculate what Espanso would produce when triggering on short_typo."""

    @abstractmethod
    def get_index_key(self, typo: str) -> str:
        """Get the character key for indexing this typo."""

    def check_conflict(
        self,
        long_typo: str,
        short_typo: str,
        long_word: str,
        short_word: str,
    ) -> bool:
        """Check if long_typo conflicts with short_typo.

        Args:
            long_typo: The longer typo string
            short_typo: The shorter typo string that might block it
            long_word: The correct word for long_typo
            short_word: The correct word for short_typo

        Returns:
            True if long_typo is blocked by short_typo, False otherwise
        """
        if not self.contains_substring(long_typo, short_typo):
            return False

        # Calculate what Espanso would produce
        expected_result = self.calculate_result(long_typo, short_typo, short_word)

        # Only block if result would be correct
        return expected_result == long_word


class SuffixConflictDetector(ConflictDetector):
    """Detect conflicts for RIGHT boundary corrections (suffixes).

    For RIGHT boundaries, Espanso matches at the end of words. The conflict check
    verifies if a longer typo ends with a shorter typo, and if triggering the
    shorter typo would produce the correct result.

    Example:
        - Long: "wherre" → "where" (RIGHT)
        - Short: "herre" → "here" (RIGHT)

        When typing "wherre":
        - Espanso sees "herre" at the end first (shorter match)
        - Triggers: "w" + "here" = "where" ✓
        - The "wherre" correction is redundant, remove it
    """

    def contains_substring(self, long_typo: str, short_typo: str) -> bool:
        """Check if long_typo ends with short_typo."""
        return long_typo.endswith(short_typo)

    def calculate_result(self, long_typo: str, short_typo: str, short_word: str) -> str:
        """Calculate what Espanso produces: remaining_prefix + short_word."""
        remaining_prefix = long_typo[: -len(short_typo)]
        return remaining_prefix + short_word

    def get_index_key(self, typo: str) -> str:
        """Get last character for suffix indexing."""
        return typo[-1] if typo else ""


class PrefixConflictDetector(ConflictDetector):
    """Detect conflicts for LEFT/NONE/BOTH boundary corrections (prefixes).

    For these boundaries, Espanso matches at the start (or anywhere). The conflict
    check verifies if a longer typo starts with a shorter typo, and if triggering
    the shorter typo would produce the correct result.

    Example:
        - Long: "tehir" → "their" (LEFT)
        - Short: "teh" → "the" (LEFT)

        When typing "tehir":
        - Espanso sees "teh" at the start first (shorter match)
        - Triggers: "the" + "ir" = "their" ✓
        - The "tehir" correction is redundant, remove it
    """

    def contains_substring(self, long_typo: str, short_typo: str) -> bool:
        """Check if long_typo starts with short_typo."""
        return long_typo.startswith(short_typo)

    def calculate_result(self, long_typo: str, short_typo: str, short_word: str) -> str:
        """Calculate what Espanso produces: short_word + remaining_suffix."""
        remaining_suffix = long_typo[len(short_typo) :]
        return short_word + remaining_suffix

    def get_index_key(self, typo: str) -> str:
        """Get first character for prefix indexing."""
        return typo[0] if typo else ""


def get_detector_for_boundary(boundary: BoundaryType) -> ConflictDetector:
    """Get the appropriate conflict detector for a boundary type.

    Args:
        boundary: The boundary type

    Returns:
        ConflictDetector instance for that boundary type
    """
    if boundary == BoundaryType.RIGHT:
        return SuffixConflictDetector()  # LEFT, NONE, and BOTH all use prefix matching
    return PrefixConflictDetector()


def _log_blocked_correction(
    long_correction: Correction,
    typo: str,
    candidate: str,
    short_word: str,
    long_word: str,
    detector: ConflictDetector,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
) -> None:
    """Log that a correction was blocked by a shorter correction.

    Args:
        long_correction: The correction that was blocked
        typo: The typo string for the long correction
        candidate: The candidate typo that blocked it
        short_word: The correct word for the candidate typo
        long_word: The correct word for the long typo
        detector: Conflict detector for calculating expected result
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos
    """
    if is_debug_correction(long_correction, debug_words, debug_typo_matcher):
        expected_result = detector.calculate_result(typo, candidate, short_word)
        log_debug_correction(
            long_correction,
            f"REMOVED - blocked by shorter correction '{candidate} → {short_word}' "
            f"(typing '{typo}' triggers '{candidate}' producing '{expected_result}' = '{long_word}' ✓)",
            debug_words,
            debug_typo_matcher,
            "Stage 5",
        )


def _check_if_typo_is_blocked(
    typo: str,
    candidate: str,
    typo_to_correction: dict[str, Correction],
    detector: ConflictDetector,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
) -> Correction | None:
    """Check if a typo is blocked by a candidate typo.

    Args:
        typo: The typo to check
        candidate: The candidate typo that might block it
        typo_to_correction: Map from typo to full correction
        detector: Conflict detector for this boundary type
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos

    Returns:
        The blocking correction if the typo is blocked, None otherwise
    """
    # Quick substring check first
    if not detector.contains_substring(typo, candidate):
        return None

    # Validate with full conflict detection
    long_correction = typo_to_correction[typo]
    short_correction = typo_to_correction[candidate]

    long_word = long_correction[1]
    short_word = short_correction[1]

    if not detector.check_conflict(typo, candidate, long_word, short_word):
        return None

    # Debug logging for blocked corrections
    _log_blocked_correction(
        long_correction,
        typo,
        candidate,
        short_word,
        long_word,
        detector,
        debug_words,
        debug_typo_matcher,
    )

    return short_correction


def _log_kept_correction(
    correction: Correction,
    boundary: BoundaryType,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
) -> None:
    """Log that a correction was kept (not blocked).

    Args:
        correction: The correction that was kept
        boundary: The boundary type
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos
    """
    log_if_debug_correction(
        correction,
        f"Kept - no blocking substring conflicts found (boundary: {boundary.value})",
        debug_words,
        debug_typo_matcher,
        "Stage 5",
    )


def _process_typo_for_conflicts(
    typo: str,
    index_key: str,
    candidates_by_char: defaultdict[str, list[str]],
    typo_to_correction: dict[str, Correction],
    detector: ConflictDetector,
    typos_to_remove: set[str],
    blocking_map: dict[Correction, Correction],
    boundary: BoundaryType,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
) -> bool:
    """Process a single typo to check for conflicts and update the index.

    Args:
        typo: The typo to process
        index_key: The character key for indexing this typo
        candidates_by_char: Index mapping characters to candidate typos
        typo_to_correction: Map from typo to full correction
        detector: Conflict detector for this boundary type
        typos_to_remove: Set of typos that should be removed
        blocking_map: Map from blocked correction to blocking correction
        boundary: The boundary type
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos

    Returns:
        True if the typo was blocked, False otherwise
    """
    # Check against candidates that share the same index character
    if index_key in candidates_by_char:
        for candidate in candidates_by_char[index_key]:
            blocking_correction = _check_if_typo_is_blocked(
                typo,
                candidate,
                typo_to_correction,
                detector,
                debug_words,
                debug_typo_matcher,
            )
            if blocking_correction is not None:
                blocked_correction = typo_to_correction[typo]
                typos_to_remove.add(typo)
                blocking_map[blocked_correction] = blocking_correction
                return True

    # If not blocked, add to index for future comparisons
    candidates_by_char[index_key].append(typo)
    correction = typo_to_correction[typo]
    _log_kept_correction(correction, boundary, debug_words, debug_typo_matcher)
    return False


def _build_typo_index(
    corrections: list[Correction],
    detector: ConflictDetector,
    boundary: BoundaryType,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
    collect_blocking_map: bool = False,
) -> tuple[set[str], dict[Correction, Correction]]:
    """Build character-based index and identify blocked typos.

    Args:
        corrections: List of corrections with the same boundary type
        detector: Conflict detector for this boundary type
        boundary: The boundary type for this group
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos
        collect_blocking_map: Whether to build blocking map (for performance optimization)

    Returns:
        Tuple of (set of typos to remove, blocking map from blocked correction to blocking correction)
    """
    # Build lookup map from typo to full correction
    typo_to_correction = {c[0]: c for c in corrections}

    # Sort typos by length for efficient checking (shorter first)
    sorted_typos = sorted(typo_to_correction.keys(), key=len)

    # Track which typos are blocked
    typos_to_remove = set()

    # Map from blocked correction to blocking correction
    blocking_map: dict[Correction, Correction] = {}

    # Build character-based index for efficient lookup
    # Maps character → list of typos with that character at the relevant position
    candidates_by_char = defaultdict(list)

    for typo in sorted_typos:
        if not typo:
            continue

        index_key = detector.get_index_key(typo)
        _process_typo_for_conflicts(
            typo,
            index_key,
            candidates_by_char,
            typo_to_correction,
            detector,
            typos_to_remove,
            blocking_map if collect_blocking_map else {},
            boundary,
            debug_words,
            debug_typo_matcher,
        )

    return typos_to_remove, blocking_map


def resolve_conflicts_for_group(
    corrections: list[Correction],
    boundary: BoundaryType,
    debug_words: set[str] | None = None,
    debug_typo_matcher: "DebugTypoMatcher | None" = None,
    collect_blocking_map: bool = False,
) -> tuple[list[Correction], dict[Correction, Correction]]:
    """Remove substring conflicts from a group of corrections with the same boundary.

    Uses character-based indexing for efficient O(n*k) performance where:
    - n = number of corrections
    - k = average number of candidates per character (typically small)

    Args:
        corrections: List of corrections with the same boundary type
        boundary: The boundary type for this group
        debug_words: Set of words to debug (exact matches)
        debug_typo_matcher: Matcher for debug typos (with wildcards/boundaries)
        collect_blocking_map: Whether to build blocking map (for performance optimization)

    Returns:
        Tuple of (list of corrections with conflicts removed, blocking map)
    """
    if debug_words is None:
        debug_words = set()

    if not corrections:
        return [], {}

    # Get the appropriate detector for this boundary type
    detector = get_detector_for_boundary(boundary)

    # Build index and identify blocked typos
    typos_to_remove, blocking_map = _build_typo_index(
        corrections, detector, boundary, debug_words, debug_typo_matcher, collect_blocking_map
    )

    # Return corrections that weren't removed
    return [c for c in corrections if c[0] not in typos_to_remove], blocking_map
