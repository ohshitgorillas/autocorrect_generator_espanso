"""Unified pattern matching module for handling exact and wildcard patterns.

This module consolidates pattern matching logic used across the codebase,
providing efficient compilation, caching, and matching operations for both
exact string matches and wildcard patterns (using * syntax).
"""

from re import Pattern

from entroppy.utils import compile_wildcard_regex


class PatternMatcher:
    """Efficient matcher for exact strings and wildcard patterns.

    Separates exact matches from wildcard patterns for performance optimization.
    Wildcard patterns are compiled once and cached for repeated matching operations.

    Patterns containing '*' are treated as wildcards (e.g., '*ball', 'in*', '*teh*').
    All other patterns are treated as exact matches.
    """

    def __init__(self, patterns: set[str] | list[str]):
        """Initialize the pattern matcher with a set of patterns.

        Args:
            patterns: Set or list of patterns. Patterns with '*' are treated as wildcards,
                     others as exact matches.
        """
        self.exact_patterns: set[str] = set()
        self.wildcard_regexes: list[Pattern] = []
        self._original_wildcards: list[str] = []

        for pattern in patterns:
            if "*" in pattern:
                self.wildcard_regexes.append(compile_wildcard_regex(pattern))
                self._original_wildcards.append(pattern)
            else:
                self.exact_patterns.add(pattern)

    def matches(self, text: str) -> bool:
        """Check if text matches any pattern (exact or wildcard).

        Args:
            text: The string to check against all patterns.

        Returns:
            True if text matches any pattern, False otherwise.
        """
        # Check exact matches first (O(1) set lookup)
        if text in self.exact_patterns:
            return True

        # Check wildcard patterns (O(n) where n is number of wildcards)
        for regex in self.wildcard_regexes:
            if regex.match(text):
                return True

        return False

    def filter_set(self, items: set[str]) -> set[str]:
        """Return items that do NOT match any pattern.

        This is useful for filtering validation dictionaries or excluding
        certain words from processing.

        Args:
            items: Set of strings to filter.

        Returns:
            A new set containing only items that don't match any pattern.
        """
        # Use generator expression for memory efficiency
        return {item for item in items if not self.matches(item)}

    def get_matching_pattern(self, text: str) -> str | None:
        """Get the pattern that matches the given text.

        Useful for reporting which exclusion rule matched.

        Args:
            text: The string to find a matching pattern for.

        Returns:
            The matching pattern string, or None if no match.
        """
        if text in self.exact_patterns:
            return text

        for i, regex in enumerate(self.wildcard_regexes):
            if regex.match(text):
                return self._original_wildcards[i]

        return None

    def has_wildcards(self) -> bool:
        """Check if this matcher contains any wildcard patterns.

        Returns:
            True if any wildcard patterns exist, False otherwise.
        """
        return len(self.wildcard_regexes) > 0

    def has_exact(self) -> bool:
        """Check if this matcher contains any exact patterns.

        Returns:
            True if any exact patterns exist, False otherwise.
        """
        return len(self.exact_patterns) > 0
