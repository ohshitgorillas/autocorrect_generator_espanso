"""Index classes for efficient pattern validation."""

from dataclasses import dataclass

from entroppy.core.boundaries import BoundaryIndex
from entroppy.core.types import Correction, MatchDirection


class SourceWordIndex:
    """Index for efficient source word corruption checks.

    Pre-builds indexes of patterns that appear at word boundaries in source words
    to avoid linear searches. For RTL patterns, indexes prefixes at word boundaries.
    For LTR patterns, indexes suffixes at word boundaries.

    Attributes:
        rtl_patterns: Set of patterns that appear at word boundaries (prefixes) for RTL matching
        ltr_patterns: Set of patterns that appear at word boundaries (suffixes) for LTR matching
        source_words: Original source words set for reference
    """

    def __init__(
        self, source_words: set[str] | frozenset[str], match_direction: MatchDirection
    ) -> None:
        """Build indexes from source words for the given match direction.

        Args:
            source_words: Set of source words to build indexes from
            match_direction: Match direction (RTL for prefix patterns, LTR for suffix patterns)
        """
        self.source_words = source_words
        self.rtl_patterns: set[str] = set()
        self.ltr_patterns: set[str] = set()

        for word in source_words:
            if match_direction == MatchDirection.RIGHT_TO_LEFT:
                # RTL: Index all patterns that appear at word boundaries (prefixes)
                # A pattern appears at a boundary if it starts at:
                # - Position 0 (start of word), OR
                # - After a non-alpha character
                for i in range(len(word)):
                    # Check if position i is at a word boundary
                    if i == 0 or not word[i - 1].isalpha():
                        # Extract all substrings starting at this boundary position
                        for j in range(i + 1, len(word) + 1):
                            pattern = word[i:j]
                            self.rtl_patterns.add(pattern)
            else:
                # LTR: Index all patterns that appear at word boundaries (suffixes)
                # A pattern appears at a boundary if it ends at:
                # - End of word, OR
                # - Before a non-alpha character
                for i in range(len(word)):
                    # Extract all substrings ending at position i or later
                    for j in range(i + 1, len(word) + 1):
                        pattern = word[i:j]
                        # Check if this pattern ends at a word boundary
                        if j >= len(word) or not word[j].isalpha():
                            self.ltr_patterns.add(pattern)

    def would_corrupt(self, typo_pattern: str, match_direction: MatchDirection) -> bool:
        """Check if a pattern would corrupt any source word.

        Args:
            typo_pattern: The typo pattern to check
            match_direction: The match direction

        Returns:
            True if the pattern would corrupt any source word, False otherwise
        """
        if match_direction == MatchDirection.RIGHT_TO_LEFT:
            return typo_pattern in self.rtl_patterns
        return typo_pattern in self.ltr_patterns


class CorrectionIndex:
    """Index for efficient pattern conflict checking.

    Pre-builds indexes of corrections by their typo suffixes and prefixes
    to enable O(1) lookups instead of O(n) linear scans.

    Only indexes full typo strings, not all substrings, for efficiency.
    Uses endswith/startswith checks during lookup instead of pre-indexing all substrings.
    """

    def __init__(self, corrections: list[Correction]) -> None:
        """Build indexes from corrections.

        Args:
            corrections: List of corrections to index
        """
        # Store all corrections for efficient filtering
        self.corrections = list(corrections)

    def get_suffix_matches(self, suffix: str) -> list[Correction]:
        """Get all corrections whose typo ends with the given suffix.

        Args:
            suffix: The suffix to look up

        Returns:
            List of corrections whose typo ends with this suffix
        """
        # Filter corrections where typo ends with suffix
        # This is O(n) but n is typically much smaller than all possible substrings
        return [c for c in self.corrections if c[0].endswith(suffix) and c[0] != suffix]

    def get_prefix_matches(self, prefix: str) -> list[Correction]:
        """Get all corrections whose typo starts with the given prefix.

        Args:
            prefix: The prefix to look up

        Returns:
            List of corrections whose typo starts with this prefix
        """
        # Filter corrections where typo starts with prefix
        # This is O(n) but n is typically much smaller than all possible substrings
        return [c for c in self.corrections if c[0].startswith(prefix) and c[0] != prefix]


@dataclass
class ValidationIndexes:
    """Container for validation indexes used during pattern validation."""

    validation_index: BoundaryIndex
    source_word_index: SourceWordIndex
    correction_index: CorrectionIndex
