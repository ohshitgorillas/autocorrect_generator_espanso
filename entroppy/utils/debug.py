"""Debug utilities for tracing words and typos through the pipeline."""

from dataclasses import dataclass
from re import Pattern

from loguru import logger

# Import at module level - these are safe because they don't import from utils
from entroppy.core.boundaries import BoundaryType
from entroppy.core.types import Correction
from entroppy.utils.helpers import compile_wildcard_regex


@dataclass(frozen=True)
class DebugTypoMatcher:
    """Matcher for debug typos with wildcard and boundary support.

    Patterns can include:
    - Exact matches: "teh"
    - Wildcards: "*tion", "err*", "*the*"
    - Boundaries: ":teh" (LEFT), "ing:" (RIGHT), ":teh:" (BOTH)
    - Combined: "err*:" (wildcard + boundary)
    """

    exact_patterns: frozenset[str]  # No wildcards, no boundaries
    wildcard_regexes: tuple[Pattern, ...]  # Compiled wildcard patterns
    wildcard_originals: tuple[str, ...]  # Original wildcard pattern strings

    # Boundary-specific patterns (exact matches only)
    left_boundary_patterns: frozenset[str]  # :pattern
    right_boundary_patterns: frozenset[str]  # pattern:
    both_boundary_patterns: frozenset[str]  # :pattern:

    # Wildcard patterns with boundaries
    left_wildcard_regexes: tuple[Pattern, ...]
    left_wildcard_originals: tuple[str, ...]
    right_wildcard_regexes: tuple[Pattern, ...]
    right_wildcard_originals: tuple[str, ...]
    both_wildcard_regexes: tuple[Pattern, ...]
    both_wildcard_originals: tuple[str, ...]

    @classmethod
    def from_patterns(cls, patterns: set[str]) -> "DebugTypoMatcher":
        """Create matcher from set of pattern strings.

        Args:
            patterns: Set of pattern strings (may include wildcards and boundaries)

        Returns:
            DebugTypoMatcher instance
        """
        exact = set()
        wildcard_regexes = []
        wildcard_originals = []

        left_boundary = set()
        right_boundary = set()
        both_boundary = set()

        left_wc_regexes = []
        left_wc_originals = []
        right_wc_regexes = []
        right_wc_originals = []
        both_wc_regexes = []
        both_wc_originals = []

        for pattern in patterns:
            if not pattern or pattern in (":", "::"):
                # Skip invalid patterns
                continue

            # Check for boundary markers
            starts_with_colon = pattern.startswith(":")
            ends_with_colon = pattern.endswith(":")

            # Remove boundary markers to get core pattern
            core = pattern.strip(":")

            if not core:
                # Empty after stripping colons
                continue

            # Determine if it's a wildcard pattern
            has_wildcard = "*" in core

            # Categorize by boundary type
            if starts_with_colon and ends_with_colon:
                # BOTH boundary
                if has_wildcard:
                    both_wc_regexes.append(compile_wildcard_regex(core))
                    both_wc_originals.append(pattern)
                else:
                    both_boundary.add(core)
            elif starts_with_colon:
                # LEFT boundary
                if has_wildcard:
                    left_wc_regexes.append(compile_wildcard_regex(core))
                    left_wc_originals.append(pattern)
                else:
                    left_boundary.add(core)
            elif ends_with_colon:
                # RIGHT boundary
                if has_wildcard:
                    right_wc_regexes.append(compile_wildcard_regex(core))
                    right_wc_originals.append(pattern)
                else:
                    right_boundary.add(core)
            else:
                # No boundary markers - matches any boundary
                if has_wildcard:
                    wildcard_regexes.append(compile_wildcard_regex(core))
                    wildcard_originals.append(pattern)
                else:
                    exact.add(core)

        return cls(
            exact_patterns=frozenset(exact),
            wildcard_regexes=tuple(wildcard_regexes),
            wildcard_originals=tuple(wildcard_originals),
            left_boundary_patterns=frozenset(left_boundary),
            right_boundary_patterns=frozenset(right_boundary),
            both_boundary_patterns=frozenset(both_boundary),
            left_wildcard_regexes=tuple(left_wc_regexes),
            left_wildcard_originals=tuple(left_wc_originals),
            right_wildcard_regexes=tuple(right_wc_regexes),
            right_wildcard_originals=tuple(right_wc_originals),
            both_wildcard_regexes=tuple(both_wc_regexes),
            both_wildcard_originals=tuple(both_wc_originals),
        )

    def matches(self, typo: str, boundary: BoundaryType) -> bool:
        """Check if typo matches any debug pattern, considering boundaries.

        Args:
            typo: The typo string to check
            boundary: The boundary type of the typo

        Returns:
            True if typo matches any pattern with compatible boundary
        """
        # Check exact patterns (no boundary restriction)
        if typo in self.exact_patterns:
            return True

        # Check wildcard patterns (no boundary restriction)
        for regex in self.wildcard_regexes:
            if regex.match(typo):
                return True

        # Check boundary-specific patterns
        if boundary in (BoundaryType.LEFT, BoundaryType.BOTH):
            if typo in self.left_boundary_patterns:
                return True
            for regex in self.left_wildcard_regexes:
                if regex.match(typo):
                    return True

        if boundary in (BoundaryType.RIGHT, BoundaryType.BOTH):
            if typo in self.right_boundary_patterns:
                return True
            for regex in self.right_wildcard_regexes:
                if regex.match(typo):
                    return True

        if boundary == BoundaryType.BOTH:
            if typo in self.both_boundary_patterns:
                return True
            for regex in self.both_wildcard_regexes:
                if regex.match(typo):
                    return True

        return False

    def get_matching_patterns(self, typo: str, boundary: BoundaryType) -> list[str]:
        """Get list of patterns that match the given typo.

        Args:
            typo: The typo string to check
            boundary: The boundary type of the typo

        Returns:
            List of matching pattern strings (for logging)
        """
        matches = []

        # Check exact patterns
        if typo in self.exact_patterns:
            matches.append(typo)

        # Check wildcard patterns
        for i, regex in enumerate(self.wildcard_regexes):
            if regex.match(typo):
                matches.append(self.wildcard_originals[i])

        # Check boundary-specific patterns
        if boundary in (BoundaryType.LEFT, BoundaryType.BOTH):
            if typo in self.left_boundary_patterns:
                matches.append(f":{typo}")
            for i, regex in enumerate(self.left_wildcard_regexes):
                if regex.match(typo):
                    matches.append(self.left_wildcard_originals[i])

        if boundary in (BoundaryType.RIGHT, BoundaryType.BOTH):
            if typo in self.right_boundary_patterns:
                matches.append(f"{typo}:")
            for i, regex in enumerate(self.right_wildcard_regexes):
                if regex.match(typo):
                    matches.append(self.right_wildcard_originals[i])

        if boundary == BoundaryType.BOTH:
            if typo in self.both_boundary_patterns:
                matches.append(f":{typo}:")
            for i, regex in enumerate(self.both_wildcard_regexes):
                if regex.match(typo):
                    matches.append(self.both_wildcard_originals[i])

        return matches


# Helper functions for checking debug status


def is_debug_word(word: str, debug_words: set[str] | frozenset[str]) -> bool:
    """Check if word is being debugged (exact match only).

    Args:
        word: The word to check
        debug_words: Set of debug words (lowercase)

    Returns:
        True if word is in debug_words
    """
    if not debug_words:
        return False
    return word.lower() in debug_words


def is_debug_typo(
    typo: str, boundary: BoundaryType, debug_typo_matcher: DebugTypoMatcher | None
) -> bool:
    """Check if typo matches any debug pattern.

    Args:
        typo: The typo to check
        boundary: The boundary type
        debug_typo_matcher: The debug typo matcher (or None)

    Returns:
        True if typo matches any debug pattern
    """
    if not debug_typo_matcher:
        return False
    return debug_typo_matcher.matches(typo, boundary)


def is_debug_correction(
    correction: Correction,
    debug_words: set[str],
    debug_typo_matcher: DebugTypoMatcher | None,
) -> bool:
    """Check if correction involves a debug word or typo.

    Args:
        correction: Tuple of (typo, word, boundary)
        debug_words: Set of debug words
        debug_typo_matcher: The debug typo matcher (or None)

    Returns:
        True if either the word or typo is being debugged
    """
    typo, word, boundary = correction
    return is_debug_word(word, debug_words) or is_debug_typo(typo, boundary, debug_typo_matcher)


# Logging functions


def log_debug_word(word: str, message: str, stage: str = "") -> None:
    """Log a debug message for a word.

    Args:
        word: The word being debugged
        message: The message to log
        stage: Optional stage name (e.g., "Stage 1")
    """
    stage_prefix = f"[{stage}] " if stage else ""
    logger.debug(f"[DEBUG WORD: '{word}'] {stage_prefix}{message}")


def log_debug_typo(
    typo: str, message: str, matched_patterns: list[str] | None = None, stage: str = ""
) -> None:
    """Log a debug message for a typo.

    Args:
        typo: The typo being debugged
        message: The message to log
        matched_patterns: List of patterns that matched (for pattern-based matching)
        stage: Optional stage name (e.g., "Stage 2")
    """
    stage_prefix = f"[{stage}] " if stage else ""
    if matched_patterns:
        patterns_str = ", ".join(matched_patterns)
        logger.debug(f"[DEBUG TYPO: '{typo}' (matched: {patterns_str})] {stage_prefix}{message}")
    else:
        logger.debug(f"[DEBUG TYPO: '{typo}'] {stage_prefix}{message}")


def log_debug_correction(
    correction: Correction,
    message: str,
    debug_words: set[str],
    debug_typo_matcher: DebugTypoMatcher | None,
    stage: str = "",
):
    """Log a debug message for a correction.

    Logs for both word and typo if both are being debugged.

    Args:
        correction: Tuple of (typo, word, boundary)
        message: The message to log
        debug_words: Set of debug words
        debug_typo_matcher: The debug typo matcher (or None)
        stage: Optional stage name (e.g., "Stage 3")
    """
    typo, word, boundary = correction

    # Check if word is being debugged
    if is_debug_word(word, debug_words):
        log_debug_word(word, f"{message} (typo: {typo})", stage)

    # Check if typo is being debugged
    if debug_typo_matcher:
        matched_patterns = debug_typo_matcher.get_matching_patterns(typo, boundary)
        if matched_patterns:
            log_debug_typo(typo, f"{message} (word: {word})", matched_patterns, stage)


def log_if_debug_correction(
    correction: Correction,
    message: str,
    debug_words: set[str],
    debug_typo_matcher: DebugTypoMatcher | None,
    stage: str = "",
) -> None:
    """Helper function to check if correction is debugged and log if so.

    This reduces code duplication by combining the common pattern of:
        if is_debug_correction(...):
            log_debug_correction(...)

    Args:
        correction: Tuple of (typo, word, boundary)
        message: The message to log
        debug_words: Set of debug words
        debug_typo_matcher: The debug typo matcher (or None)
        stage: Optional stage name (e.g., "Stage 3")
    """
    if is_debug_correction(correction, debug_words, debug_typo_matcher):
        log_debug_correction(correction, message, debug_words, debug_typo_matcher, stage)
