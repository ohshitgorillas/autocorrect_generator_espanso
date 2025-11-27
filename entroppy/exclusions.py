"""Exclusion pattern matching."""

from __future__ import annotations

from re import Pattern

from .config import BoundaryType, Correction
from .utils import compile_wildcard_regex


class ExclusionMatcher:
    """Handle exclusion patterns with wildcards."""

    def __init__(self, exclusion_set: set[str]):
        self.exact = set()
        self.wildcards = []
        self.exact_typo_map: dict[str, str] = {}
        self.wildcard_typo_map: list[tuple[Pattern, str, BoundaryType | None]] = []
        self.wildcard_words: set[Pattern] = set()
        self.exact_words: set[str] = set()

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
                    self.exact_typo_map[typo_pat] = word_pat
            else:
                # These are word-only exclusions (e.g., "*ball") used for dictionary filtering.
                # We can safely ignore them here, as they are not meant to filter
                # (typo, word) correction pairs.
                if "*" in pattern:
                    self.wildcard_words.add(compile_wildcard_regex(pattern))
                else:
                    self.exact_words.add(pattern)

    def _match_wildcard(self, text: str, pattern: str) -> bool:
        """Helper to match a string against a simple wildcard pattern."""
        if "*" not in pattern:
            return text == pattern
        regex = compile_wildcard_regex(pattern)
        return regex.match(text) is not None

    def should_exclude(self, correction: Correction) -> bool:
        """Check if a (typo, word) correction should be excluded."""
        typo, word, boundary = correction

        # Check for exact typo -> word match (no boundary support for exact)
        if self.exact_typo_map.get(typo) == word:
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
        if self.exact_typo_map.get(typo) == word:
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
        if word in self.exact:
            return True

        for pattern in self.wildcards:
            if self._match_wildcard(word, pattern):
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
