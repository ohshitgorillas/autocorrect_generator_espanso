"""Unit tests for boundary detection behavior.

Tests verify boundary detection logic that determines when typos need word boundaries
to prevent false triggers. Each test has a single assertion and focuses on behavior.
"""

from entroppy.boundaries import (
    is_substring_of_any,
    would_trigger_at_start,
    would_trigger_at_end,
    determine_boundaries,
)
from entroppy.config import BoundaryType


class TestIsSubstringOfAny:
    """Test substring detection behavior."""

    def test_detects_substring_in_middle_of_word(self) -> None:
        """When typo appears in the middle of a word, returns True."""
        result = is_substring_of_any("test", {"atestb"})
        assert result is True

    def test_ignores_exact_match(self) -> None:
        """When typo equals the word exactly, returns False."""
        result = is_substring_of_any("test", {"test"})
        assert result is False

    def test_detects_substring_at_start(self) -> None:
        """When typo is a prefix of a word, returns True."""
        result = is_substring_of_any("test", {"testing"})
        assert result is True

    def test_detects_substring_at_end(self) -> None:
        """When typo is a suffix of a word, returns True."""
        result = is_substring_of_any("ing", {"testing"})
        assert result is True

    def test_returns_false_when_not_found(self) -> None:
        """When typo is not in any word, returns False."""
        result = is_substring_of_any("test", {"hello", "world"})
        assert result is False

    def test_returns_false_for_empty_word_set(self) -> None:
        """When word set is empty, returns False."""
        result = is_substring_of_any("test", set())
        assert result is False

    def test_checks_multiple_words(self) -> None:
        """When typo is in one of multiple words, returns True."""
        result = is_substring_of_any("test", {"hello", "atestb", "world"})
        assert result is True


class TestWouldTriggerAtStart:
    """Test prefix detection behavior."""

    def test_detects_typo_as_word_prefix(self) -> None:
        """When typo is the start of a word, returns True."""
        result = would_trigger_at_start("test", {"testing"})
        assert result is True

    def test_ignores_exact_match(self) -> None:
        """When typo equals the word exactly, returns False."""
        result = would_trigger_at_start("test", {"test"})
        assert result is False

    def test_returns_false_when_not_prefix(self) -> None:
        """When typo is not a prefix of any word, returns False."""
        result = would_trigger_at_start("test", {"atest", "best"})
        assert result is False

    def test_returns_false_for_empty_set(self) -> None:
        """When validation set is empty, returns False."""
        result = would_trigger_at_start("test", set())
        assert result is False

    def test_checks_multiple_words(self) -> None:
        """When typo is prefix of one word among many, returns True."""
        result = would_trigger_at_start("test", {"hello", "testing", "world"})
        assert result is True


class TestWouldTriggerAtEnd:
    """Test suffix detection behavior."""

    def test_detects_typo_as_word_suffix(self) -> None:
        """When typo is the end of a word, returns True."""
        result = would_trigger_at_end("ing", {"testing"})
        assert result is True

    def test_ignores_exact_match(self) -> None:
        """When typo equals the word exactly, returns False."""
        result = would_trigger_at_end("test", {"test"})
        assert result is False

    def test_returns_false_when_not_suffix(self) -> None:
        """When typo is not a suffix of any word, returns False."""
        result = would_trigger_at_end("test", {"testa", "testb"})
        assert result is False

    def test_returns_false_for_empty_set(self) -> None:
        """When validation set is empty, returns False."""
        result = would_trigger_at_end("ing", set())
        assert result is False

    def test_checks_multiple_words(self) -> None:
        """When typo is suffix of one word among many, returns True."""
        result = would_trigger_at_end("ing", {"hello", "testing", "world"})
        assert result is True


class TestDetermineBoundariesStandalone:
    """Test boundary determination when typo is standalone."""

    def test_returns_none_when_not_a_substring(self) -> None:
        """When typo doesn't appear in any word, returns NONE boundary."""
        result = determine_boundaries("teh", {"hello", "world"}, {"test", "data"})
        assert result == BoundaryType.NONE

    def test_returns_none_when_only_exact_match_exists(self) -> None:
        """When typo appears only as exact match (not substring), returns NONE."""
        result = determine_boundaries("test", {"test"}, {"test"})
        assert result == BoundaryType.NONE


class TestDetermineBoundariesInfix:
    """Test boundary determination when typo appears in middle of words."""

    def test_returns_both_when_substring_but_not_prefix_or_suffix(self) -> None:
        """When typo appears in middle of words only, returns BOTH boundaries."""
        result = determine_boundaries("test", {"atestb"}, {"ctestd"})
        assert result == BoundaryType.BOTH

    def test_returns_both_when_substring_in_validation_only(self) -> None:
        """When typo is substring of validation words only, returns BOTH."""
        result = determine_boundaries("test", {"atestb"}, set())
        assert result == BoundaryType.BOTH

    def test_returns_both_when_substring_in_source_only(self) -> None:
        """When typo is substring of source words only, returns BOTH."""
        result = determine_boundaries("test", set(), {"atestb"})
        assert result == BoundaryType.BOTH


class TestDetermineBoundariesPrefix:
    """Test boundary determination when typo is a prefix."""

    def test_returns_right_when_only_appears_as_prefix(self) -> None:
        """When typo appears as prefix only, returns RIGHT boundary."""
        result = determine_boundaries("test", {"testing"}, set())
        assert result == BoundaryType.RIGHT

    def test_returns_right_when_prefix_in_both_sets(self) -> None:
        """When typo is prefix in both validation and source, returns RIGHT."""
        result = determine_boundaries("test", {"testing"}, {"testable"})
        assert result == BoundaryType.RIGHT


class TestDetermineBoundariesSuffix:
    """Test boundary determination when typo is a suffix."""

    def test_returns_left_when_only_appears_as_suffix(self) -> None:
        """When typo appears as suffix only, returns LEFT boundary."""
        result = determine_boundaries("ing", {"testing"}, set())
        assert result == BoundaryType.LEFT

    def test_returns_left_when_suffix_in_both_sets(self) -> None:
        """When typo is suffix in both validation and source, returns LEFT."""
        result = determine_boundaries("ing", {"testing"}, {"running"})
        assert result == BoundaryType.LEFT


class TestDetermineBoundariesBothPrefixAndSuffix:
    """Test boundary determination when typo is both prefix and suffix."""

    def test_returns_both_when_appears_as_prefix_and_suffix(self) -> None:
        """When typo appears as both prefix and suffix, returns BOTH."""
        result = determine_boundaries("test", {"testing", "attest"}, set())
        assert result == BoundaryType.BOTH


class TestDetermineBoundariesEdgeCases:
    """Test edge cases in boundary determination."""

    def test_handles_empty_validation_and_source_sets(self) -> None:
        """When both sets are empty, returns NONE."""
        result = determine_boundaries("test", set(), set())
        assert result == BoundaryType.NONE

    def test_handles_single_character_typo(self) -> None:
        """Single character typo is handled correctly."""
        result = determine_boundaries("a", {"abc"}, set())
        assert result == BoundaryType.RIGHT

    def test_prioritizes_validation_set_for_boundary_detection(self) -> None:
        """Boundary detection considers validation set for prefix/suffix checks."""
        # typo is substring in source, but validation determines boundaries
        result = determine_boundaries("test", {"testing"}, {"xtest"})
        assert result == BoundaryType.RIGHT

    def test_substring_in_source_triggers_boundary_requirement(self) -> None:
        """Being a substring in source set alone requires boundaries."""
        result = determine_boundaries("test", set(), {"atestb"})
        assert result == BoundaryType.BOTH

    def test_prefix_in_validation_requires_right_boundary(self) -> None:
        """Being a prefix in validation requires right boundary."""
        result = determine_boundaries("test", {"testing", "tested"}, set())
        assert result == BoundaryType.RIGHT

    def test_suffix_in_validation_requires_left_boundary(self) -> None:
        """Being a suffix in validation requires left boundary."""
        result = determine_boundaries("test", {"attest", "protest"}, set())
        assert result == BoundaryType.LEFT
