"""Exclusion pattern matching."""

from .config import Correction


class ExclusionMatcher:
    """Handle exclusion patterns with wildcards."""

    def __init__(self, exclusion_set: set[str]):
        self.exact = set()
        self.wildcards = []

        for exclusion in exclusion_set:
            if "*" in exclusion:
                self.wildcards.append(exclusion)
            else:
                self.exact.add(exclusion)

    def should_exclude(self, correction: Correction) -> bool:
        """Check if correction should be excluded."""
        typo, word, _ = correction

        if typo in self.exact:
            return True

        for pattern in self.wildcards:
            if self._matches_wildcard(typo, pattern):
                return True

        return False

    def should_ignore_in_validation(self, word: str) -> bool:
        """
        Check if a validation word should be ignored during boundary detection.

        This allows excluded patterns to not block valid typos.
        For example, if "*toin" is excluded, "allantoin" won't block "toin" as a typo.
        """
        if word in self.exact:
            return True

        for pattern in self.wildcards:
            if self._matches_wildcard(word, pattern):
                return True

        return False

    def filter_validation_set(self, validation_set: set[str]) -> set[str]:
        """
        Create a filtered validation set for boundary detection.

        Removes words matching exclusion patterns so they don't block valid typos.
        """
        return {
            word
            for word in validation_set
            if not self.should_ignore_in_validation(word)
        }

    def _matches_wildcard(self, text: str, pattern: str) -> bool:
        """Check if text matches wildcard pattern."""
        if pattern.startswith("*") and pattern.endswith("*"):
            return pattern[1:-1] in text
        elif pattern.startswith("*"):
            return text.endswith(pattern[1:])
        elif pattern.endswith("*"):
            return text.startswith(pattern[:-1])
        return text == pattern
