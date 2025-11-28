"""Unit tests for the pattern_matching module.

Tests verify pattern compilation, matching behavior, filtering, and caching.
Each test has a single assertion and uses type hints.
"""

import pytest

from entroppy.pattern_matching import PatternMatcher

# pylint: disable=missing-function-docstring, protected-access


class TestPatternMatcherBehavior:
    """Test PatternMatcher behavior with various patterns and operations."""

    def test_empty_matcher_matches_nothing(self) -> None:
        matcher = PatternMatcher(set())
        assert matcher.matches("anything") is False

    def test_accepts_list_input(self) -> None:
        matcher = PatternMatcher(["word", "*ball"])
        assert matcher.matches("word") is True


class TestPatternMatcherMatches:
    """Test the matches() method with various patterns and text."""

    def test_matches_exact_pattern(self) -> None:
        matcher = PatternMatcher({"test"})
        assert matcher.matches("test") is True

    def test_does_not_match_different_exact(self) -> None:
        matcher = PatternMatcher({"test"})
        assert matcher.matches("other") is False

    def test_matches_prefix_wildcard(self) -> None:
        matcher = PatternMatcher({"*ball"})
        assert matcher.matches("football") is True

    def test_matches_suffix_wildcard(self) -> None:
        matcher = PatternMatcher({"in*"})
        assert matcher.matches("inside") is True

    def test_matches_middle_wildcard(self) -> None:
        matcher = PatternMatcher({"*teh*"})
        assert matcher.matches("tehsildar") is True

    def test_wildcard_does_not_match_partial(self) -> None:
        matcher = PatternMatcher({"*ball"})
        assert matcher.matches("bal") is False

    def test_matches_multiple_wildcards_in_pattern(self) -> None:
        matcher = PatternMatcher({"*a*b*"})
        assert matcher.matches("xaybz") is True

    def test_matches_with_empty_string(self) -> None:
        matcher = PatternMatcher({"test"})
        assert matcher.matches("") is False

    def test_matches_with_overlapping_patterns(self) -> None:
        matcher = PatternMatcher({"test", "*est"})
        assert matcher.matches("test") is True

    def test_does_not_match_when_no_patterns_match(self) -> None:
        matcher = PatternMatcher({"test", "*ball"})
        assert matcher.matches("other") is False


class TestPatternMatcherFilterSet:
    """Test the filter_set() method for removing matching items."""

    def test_filter_set_removes_exact_matches(self) -> None:
        matcher = PatternMatcher({"test"})
        result = matcher.filter_set({"test", "keep"})
        assert result == {"keep"}

    def test_filter_set_removes_wildcard_matches(self) -> None:
        matcher = PatternMatcher({"*ball"})
        result = matcher.filter_set({"football", "basketball", "shoe"})
        assert result == {"shoe"}

    def test_filter_set_with_empty_items(self) -> None:
        matcher = PatternMatcher({"test"})
        result = matcher.filter_set(set())
        assert result == set()

    def test_filter_set_keeps_non_matching_items(self) -> None:
        matcher = PatternMatcher({"test"})
        result = matcher.filter_set({"keep1", "keep2"})
        assert result == {"keep1", "keep2"}

    def test_filter_set_with_multiple_pattern_types(self) -> None:
        """Verify exact and wildcard patterns work together correctly."""
        matcher = PatternMatcher({"exact", "*wild"})
        result = matcher.filter_set({"exact", "gowild", "wildcard", "keep"})
        # "exact" matches exact pattern, "gowild" matches "*wild" pattern
        # "wildcard" and "keep" don't match any pattern
        assert result == {"wildcard", "keep"}


class TestPatternMatcherGetMatchingPattern:
    """Test the get_matching_pattern() method for identifying which pattern matched."""

    def test_get_matching_pattern_for_exact(self) -> None:
        matcher = PatternMatcher({"test"})
        result = matcher.get_matching_pattern("test")
        assert result == "test"

    def test_get_matching_pattern_for_wildcard(self) -> None:
        matcher = PatternMatcher({"*ball"})
        result = matcher.get_matching_pattern("football")
        assert result == "*ball"

    def test_get_matching_pattern_returns_none_when_no_match(self) -> None:
        matcher = PatternMatcher({"test"})
        result = matcher.get_matching_pattern("other")
        assert result is None

    def test_get_matching_pattern_with_overlapping_patterns(self) -> None:
        matcher = PatternMatcher({"test", "*est"})
        result = matcher.get_matching_pattern("test")
        assert result == "test"


@pytest.mark.parametrize(
    "pattern,text,expected",
    [
        ("*ball", "football", True),
        ("*ball", "basketball", True),
        ("*ball", "ball", True),
        ("*ball", "bal", False),
        ("in*", "inside", True),
        ("in*", "in", True),
        ("in*", "i", False),
        ("*teh*", "tehsildar", True),
        ("*teh*", "teh", True),
        ("*teh*", "te", False),
        ("exact", "exact", True),
        ("exact", "Exact", False),
        ("exact", "exact ", False),
        ("*", "anything", True),
        ("*", "", True),
    ],
)
def test_pattern_matching_edge_cases(pattern: str, text: str, expected: bool) -> None:
    """Test edge cases for pattern matching with various combinations."""
    matcher = PatternMatcher({pattern})
    assert matcher.matches(text) is expected


@pytest.mark.parametrize(
    "patterns,items,expected",
    [
        ({"*ball"}, {"football", "shoe"}, {"shoe"}),
        ({"test"}, {"test", "keep"}, {"keep"}),
        (
            {
                "*",
            },
            {"any", "thing"},
            set(),
        ),
        ({"none"}, {"keep1", "keep2"}, {"keep1", "keep2"}),
        (set(), {"keep1", "keep2"}, {"keep1", "keep2"}),
    ],
)
def test_filter_set_edge_cases(
    patterns: set[str], items: set[str], expected: set[str]
) -> None:
    """Test edge cases for filter_set with various pattern/item combinations."""
    matcher = PatternMatcher(patterns)
    assert matcher.filter_set(items) == expected


class TestPatternMatcherSpecialCharacters:
    """Test pattern matching with special regex characters."""

    def test_matches_pattern_with_dots(self) -> None:
        matcher = PatternMatcher({"test.txt"})
        assert matcher.matches("test.txt") is True

    def test_does_not_match_dot_as_regex_wildcard(self) -> None:
        matcher = PatternMatcher({"test.txt"})
        assert matcher.matches("testAtxt") is False

    def test_matches_pattern_with_brackets(self) -> None:
        matcher = PatternMatcher({"test[0]"})
        assert matcher.matches("test[0]") is True

    def test_matches_pattern_with_parens(self) -> None:
        matcher = PatternMatcher({"test(1)"})
        assert matcher.matches("test(1)") is True

    def test_wildcard_with_special_chars(self) -> None:
        matcher = PatternMatcher({"*.txt"})
        assert matcher.matches("file.txt") is True
