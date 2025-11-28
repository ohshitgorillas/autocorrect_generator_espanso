"""Exclusion pattern matching."""

from __future__ import annotations

from re import Pattern

from .config import BoundaryType, Correction
from .pattern_matching import PatternMatcher
from .utils import compile_wildcard_regex


class ExclusionMatcher:
    """Handle exclusion patterns with wildcards."""

    def __init__(self, exclusion_set: set[str]):
        self.exact = set()
        self.wildcards = []
        self.exact_typo_map: dict[str, tuple[str, BoundaryType | None]] = {}
        self.wildcard_typo_map: list[tuple[Pattern, str, BoundaryType | None]] = []

        # Collect word-only exclusion patterns
        word_only_patterns = set()

        for exclusion in exclusion_set:
            if "*" in exclusion or ":" in exclusion:
                self.wildcards.append(exclusion)
            else:
                self.exact.add(exclusion)

        # e.g., "accel* -> accelerate" or ":*ing -> *in"
        for pattern in exclusion_set:
            if "->" in pattern:
                typo_pat, word_pat = (p.strip() for p in pattern.split("->", 1))

                # Check for boundary specifiers
                required_boundary = None
                if typo_pat.startswith(":") and typo_pat.endswith(":"):
                    required_boundary = BoundaryType.BOTH
                    typo_pat = typo_pat[1:-1]
                elif typo_pat.startswith(":"):
                    required_boundary = BoundaryType.LEFT
                    typo_pat = typo_pat[1:]
                elif typo_pat.endswith(":"):
                    required_boundary = BoundaryType.RIGHT
                    typo_pat = typo_pat[:-1]

                if "*" in typo_pat:
                    regex = compile_wildcard_regex(typo_pat)
                    self.wildcard_typo_map.append((regex, word_pat, required_boundary))
                else:
                    self.exact_typo_map[typo_pat] = (word_pat, required_boundary)
            else:
                # These are word-only exclusions (e.g., "*ball") used for dictionary filtering
                word_only_patterns.add(pattern)

        # Use PatternMatcher for word-only exclusions
        self.word_pattern_matcher = PatternMatcher(word_only_patterns)

        # Create a PatternMatcher for word patterns used in typo->word mappings
        word_patterns_in_mappings = {
            word_pat for _, word_pat, _ in self.wildcard_typo_map
        }
        word_patterns_in_mappings.update(self.exact_typo_map.values())
        self.word_matcher = PatternMatcher(word_patterns_in_mappings)

    def _match_wildcard(self, text: str, pattern: str) -> bool:
        """Helper to match a string against a simple wildcard pattern."""
        if "*" not in pattern:
            return text == pattern
        regex = compile_wildcard_regex(pattern)
        return regex.match(text) is not None

    def should_exclude(self, correction: Correction) -> bool:
        """Check if a (typo, word) correction should be excluded."""
        typo, word, boundary = correction

        # Check for exact typo -> word match (with boundary support)
        exact_match = self.exact_typo_map.get(typo)
        if exact_match:
            word_pat, required_boundary = exact_match
            if word == word_pat:
                if required_boundary is None or required_boundary == boundary:
                    return True

        # Check for wildcard typo -> word match, e.g., "accel* -> accelerate"
        for typo_re, word_pat, required_boundary in self.wildcard_typo_map:
            if typo_re.match(typo) and self._match_wildcard(word, word_pat):
                # If boundary is specified, it must match
                if required_boundary is None or required_boundary == boundary:
                    return True

        return False

    def get_matching_rule(self, correction: Correction) -> str:
        """Get the exclusion rule that matches this correction (for reporting)."""
        typo, word, _ = correction

        # Check for exact typo -> word match
        exact_match = self.exact_typo_map.get(typo)
        if exact_match and exact_match[0] == word:
            return f"{typo} -> {word}"

        # Check for wildcard typo -> word match
        for typo_re, word_pat, _ in self.wildcard_typo_map:
            if typo_re.match(typo) and self._match_wildcard(word, word_pat):
                # This is imperfect, as it doesn't store the original rule with the parsed
                # components, but it's good enough for reporting.
                # We just find the first wildcard rule that could have produced this match.
                clean_re = typo_re.pattern.replace("^", "").replace("$", "")
                for original_pattern in self.wildcards:
                    if "->" in original_pattern and clean_re in original_pattern:
                        return original_pattern

        return "unknown rule"

    def should_ignore_in_validation(self, word: str) -> bool:
        """
        Check if a validation word should be ignored during boundary detection.

        This allows excluded patterns to not block valid typos.
        For example, if "*toin" is excluded, "allantoin" won't block "toin" as a typo.
        """
        return self.word_pattern_matcher.matches(word)

    def filter_validation_set(self, validation_set: set[str]) -> set[str]:
        """
        Create a filtered validation set for boundary detection.

        Removes words matching exclusion patterns so they don't block valid typos.
        """
        return self.word_pattern_matcher.filter_set(validation_set)
