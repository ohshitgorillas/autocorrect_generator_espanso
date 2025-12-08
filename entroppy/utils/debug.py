"""Debug utilities for tracing words and typos through the pipeline."""

from dataclasses import dataclass
import re
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
    def _add_to_boundary_collection(
        cls,
        core: str,
        pattern: str,
        has_wildcard: bool,
        boundary_collection: set[str],
        wildcard_regexes: list,
        wildcard_originals: list,
    ) -> None:
        """Add pattern to boundary-specific collection."""
        if has_wildcard:
            wildcard_regexes.append(compile_wildcard_regex(core))
            wildcard_originals.append(pattern)
        else:
            boundary_collection.add(core)

    @classmethod
    def _categorize_pattern(
        cls,
        pattern: str,
        exact: set[str],
        wildcard_regexes: list,
        wildcard_originals: list,
        left_boundary: set[str],
        right_boundary: set[str],
        both_boundary: set[str],
        left_wc_regexes: list,
        left_wc_originals: list,
        right_wc_regexes: list,
        right_wc_originals: list,
        both_wc_regexes: list,
        both_wc_originals: list,
    ) -> None:
        """Categorize a single pattern into appropriate collections."""
        if not pattern or pattern in (":", "::"):
            # Skip invalid patterns
            return

        # Check for boundary markers
        starts_with_colon = pattern.startswith(":")
        ends_with_colon = pattern.endswith(":")

        # Remove boundary markers to get core pattern
        core = pattern.strip(":")

        if not core:
            # Empty after stripping colons
            return

        # Determine if it's a wildcard pattern
        has_wildcard = "*" in core

        # Categorize by boundary type
        if starts_with_colon and ends_with_colon:
            # BOTH boundary
            cls._add_to_boundary_collection(
                core,
                pattern,
                has_wildcard,
                both_boundary,
                both_wc_regexes,
                both_wc_originals,
            )
        elif starts_with_colon:
            # LEFT boundary
            cls._add_to_boundary_collection(
                core,
                pattern,
                has_wildcard,
                left_boundary,
                left_wc_regexes,
                left_wc_originals,
            )
        elif ends_with_colon:
            # RIGHT boundary
            cls._add_to_boundary_collection(
                core,
                pattern,
                has_wildcard,
                right_boundary,
                right_wc_regexes,
                right_wc_originals,
            )
        else:
            # No boundary markers - matches any boundary
            cls._add_to_boundary_collection(
                core, pattern, has_wildcard, exact, wildcard_regexes, wildcard_originals
            )

    @classmethod
    def from_patterns(cls, patterns: set[str]) -> "DebugTypoMatcher":
        """Create matcher from set of pattern strings.

        Args:
            patterns: Set of pattern strings (may include wildcards and boundaries)

        Returns:
            DebugTypoMatcher instance
        """
        exact: set[str] = set()
        wildcard_regexes: list[re.Pattern[str]] = []
        wildcard_originals: list[str] = []

        left_boundary: set[str] = set()
        right_boundary: set[str] = set()
        both_boundary: set[str] = set()

        left_wc_regexes: list[re.Pattern[str]] = []
        left_wc_originals: list[str] = []
        right_wc_regexes: list[re.Pattern[str]] = []
        right_wc_originals: list[str] = []
        both_wc_regexes: list[re.Pattern[str]] = []
        both_wc_originals: list[str] = []

        for pattern in patterns:
            cls._categorize_pattern(
                pattern,
                exact,
                wildcard_regexes,
                wildcard_originals,
                left_boundary,
                right_boundary,
                both_boundary,
                left_wc_regexes,
                left_wc_originals,
                right_wc_regexes,
                right_wc_originals,
                both_wc_regexes,
                both_wc_originals,
            )

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

    def _check_left_boundary_patterns(self, typo: str) -> bool:
        """Check if typo matches left boundary patterns."""
        if typo in self.left_boundary_patterns:
            return True
        for regex in self.left_wildcard_regexes:
            if regex.match(typo):
                return True
        return False

    def _check_right_boundary_patterns(self, typo: str) -> bool:
        """Check if typo matches right boundary patterns."""
        if typo in self.right_boundary_patterns:
            return True
        for regex in self.right_wildcard_regexes:
            if regex.match(typo):
                return True
        return False

    def _check_both_boundary_patterns(self, typo: str) -> bool:
        """Check if typo matches both boundary patterns."""
        if typo in self.both_boundary_patterns:
            return True
        for regex in self.both_wildcard_regexes:
            if regex.match(typo):
                return True
        return False

    def _check_boundary_patterns(self, typo: str, boundary: BoundaryType) -> bool:
        """Check if typo matches boundary-specific patterns."""
        if boundary in (BoundaryType.LEFT, BoundaryType.BOTH):
            if self._check_left_boundary_patterns(typo):
                return True

        if boundary in (BoundaryType.RIGHT, BoundaryType.BOTH):
            if self._check_right_boundary_patterns(typo):
                return True

        if boundary == BoundaryType.BOTH:
            if self._check_both_boundary_patterns(typo):
                return True

        return False

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
        return self._check_boundary_patterns(typo, boundary)

    def _collect_left_boundary_matches(self, typo: str, matches: list[str]) -> None:
        """Collect matching left boundary patterns."""
        if typo in self.left_boundary_patterns:
            matches.append(f":{typo}")
        for i, regex in enumerate(self.left_wildcard_regexes):
            if regex.match(typo):
                matches.append(self.left_wildcard_originals[i])

    def _collect_right_boundary_matches(self, typo: str, matches: list[str]) -> None:
        """Collect matching right boundary patterns."""
        if typo in self.right_boundary_patterns:
            matches.append(f"{typo}:")
        for i, regex in enumerate(self.right_wildcard_regexes):
            if regex.match(typo):
                matches.append(self.right_wildcard_originals[i])

    def _collect_both_boundary_matches(self, typo: str, matches: list[str]) -> None:
        """Collect matching both boundary patterns."""
        if typo in self.both_boundary_patterns:
            matches.append(f":{typo}:")
        for i, regex in enumerate(self.both_wildcard_regexes):
            if regex.match(typo):
                matches.append(self.both_wildcard_originals[i])

    def _collect_boundary_pattern_matches(
        self, typo: str, boundary: BoundaryType, matches: list[str]
    ) -> None:
        """Collect matching boundary-specific patterns."""
        if boundary in (BoundaryType.LEFT, BoundaryType.BOTH):
            self._collect_left_boundary_matches(typo, matches)

        if boundary in (BoundaryType.RIGHT, BoundaryType.BOTH):
            self._collect_right_boundary_matches(typo, matches)

        if boundary == BoundaryType.BOTH:
            self._collect_both_boundary_matches(typo, matches)

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
        self._collect_boundary_pattern_matches(typo, boundary, matches)

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


def log_debug_word(
    word: str, message: str, stage: str = "", debug_messages: list[str] | None = None
) -> None:
    """Log a debug message for a word.

    Args:
        word: The word being debugged
        message: The message to log
        stage: Optional stage name (e.g., "Stage 1")
        debug_messages: Optional list to collect message into (for reports)
    """
    stage_prefix = f"[{stage}] " if stage else ""
    formatted_message = f"[DEBUG WORD: '{word}'] {stage_prefix}{message}"
    logger.debug(formatted_message)
    if debug_messages is not None:
        debug_messages.append(formatted_message)


def log_debug_typo(
    typo: str,
    message: str,
    matched_patterns: list[str] | None = None,
    stage: str = "",
    debug_messages: list[str] | None = None,
) -> None:
    """Log a debug message for a typo.

    Args:
        typo: The typo being debugged
        message: The message to log
        matched_patterns: List of patterns that matched (for pattern-based matching)
        stage: Optional stage name (e.g., "Stage 2")
        debug_messages: Optional list to collect message into (for reports)
    """
    stage_prefix = f"[{stage}] " if stage else ""
    if matched_patterns:
        patterns_str = ", ".join(matched_patterns)
        formatted_message = (
            f"[DEBUG TYPO: '{typo}' (matched: {patterns_str})] {stage_prefix}{message}"
        )
    else:
        formatted_message = f"[DEBUG TYPO: '{typo}'] {stage_prefix}{message}"
    logger.debug(formatted_message)
    if debug_messages is not None:
        debug_messages.append(formatted_message)


def log_debug_correction(
    correction: Correction,
    message: str,
    debug_words: set[str],
    debug_typo_matcher: DebugTypoMatcher | None,
    stage: str = "",
    debug_messages: list[str] | None = None,
):
    """Log a debug message for a correction.

    Logs for both word and typo if both are being debugged.

    Args:
        correction: Tuple of (typo, word, boundary)
        message: The message to log
        debug_words: Set of debug words
        debug_typo_matcher: The debug typo matcher (or None)
        stage: Optional stage name (e.g., "Stage 3")
        debug_messages: Optional list to collect messages into (for reports)
    """
    typo, word, boundary = correction

    # Check if word is being debugged
    if is_debug_word(word, debug_words):
        log_debug_word(word, f"{message} (typo: {typo})", stage, debug_messages)

    # Check if typo is being debugged
    if debug_typo_matcher:
        matched_patterns = debug_typo_matcher.get_matching_patterns(typo, boundary)
        if matched_patterns:
            log_debug_typo(
                typo, f"{message} (word: {word})", matched_patterns, stage, debug_messages
            )


def log_if_debug_correction(
    correction: Correction,
    message: str,
    debug_words: set[str],
    debug_typo_matcher: DebugTypoMatcher | None,
    stage: str = "",
    debug_messages: list[str] | None = None,
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
        debug_messages: Optional list to collect messages into (for reports)
    """
    if is_debug_correction(correction, debug_words, debug_typo_matcher):
        log_debug_correction(
            correction, message, debug_words, debug_typo_matcher, stage, debug_messages
        )
