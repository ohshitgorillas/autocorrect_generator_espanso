"""Conflict resolution for substring typo corrections.

Example for left-to-right matching:
- herre → here
- wherre → where

When typing "wherre":
- Espanso sees "herre" at the end first (shorter match)
- Triggers: "w" + "here" = "where" ✓
- The "wherre" correction is redundant, remove it
"""

from collections import defaultdict
from abc import ABC, abstractmethod

from .config import BoundaryType, Correction


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


def resolve_conflicts_for_group(
    corrections: list[Correction],
    boundary: BoundaryType,
) -> list[Correction]:
    """Remove substring conflicts from a group of corrections with the same boundary.

    Uses character-based indexing for efficient O(n*k) performance where:
    - n = number of corrections
    - k = average number of candidates per character (typically small)

    Args:
        corrections: List of corrections with the same boundary type
        boundary: The boundary type for this group

    Returns:
        List of corrections with conflicts removed
    """
    if not corrections:
        return []

    # Get the appropriate detector for this boundary type
    detector = get_detector_for_boundary(boundary)

    # Build lookup map from typo to full correction
    typo_to_correction = {c[0]: c for c in corrections}

    # Sort typos by length for efficient checking (shorter first)
    sorted_typos = sorted(typo_to_correction.keys(), key=len)

    # Track which typos are blocked
    typos_to_remove = set()

    # Build character-based index for efficient lookup
    # Maps character → list of typos with that character at the relevant position
    candidates_by_char = defaultdict(list)

    for typo in sorted_typos:
        is_blocked = False

        # Check against candidates that share the same index character
        if typo:
            index_key = detector.get_index_key(typo)
            if index_key in candidates_by_char:
                for candidate in candidates_by_char[index_key]:
                    # Quick substring check first
                    if detector.contains_substring(typo, candidate):
                        # Validate with full conflict detection
                        long_correction = typo_to_correction[typo]
                        short_correction = typo_to_correction[candidate]

                        long_word = long_correction[1]
                        short_word = short_correction[1]

                        if detector.check_conflict(
                            typo, candidate, long_word, short_word
                        ):
                            typos_to_remove.add(typo)
                            is_blocked = True
                            break

        # If not blocked, add to index for future comparisons
        if not is_blocked and typo:
            index_key = detector.get_index_key(typo)
            candidates_by_char[index_key].append(typo)

    # Return corrections that weren't removed
    return [c for c in corrections if c[0] not in typos_to_remove]
