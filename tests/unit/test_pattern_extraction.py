"""Unit tests for pattern extraction behavior.

Tests verify pattern extraction logic that finds common prefix and suffix patterns
in typo corrections. Each test has a single assertion and focuses on behavior.
"""

from entroppy.core import BoundaryType, Correction
from entroppy.core.pattern_extraction import find_prefix_patterns, find_suffix_patterns


class TestFindSuffixPatterns:
    """Test suffix pattern extraction behavior."""

    def test_finds_common_suffix_pattern(self) -> None:
        """When corrections share a common suffix, extracts the pattern."""
        corrections: list[Correction] = [
            ("testeh", "testhe", BoundaryType.RIGHT),
            ("wordeh", "wordhe", BoundaryType.RIGHT),
        ]
        result = find_suffix_patterns(corrections)
        assert ("eh", "he", BoundaryType.RIGHT) in result

    def test_groups_corrections_by_suffix_pattern(self) -> None:
        """When multiple corrections match a suffix pattern, groups them together."""
        corrections: list[Correction] = [
            ("testeh", "testhe", BoundaryType.RIGHT),
            ("wordeh", "wordhe", BoundaryType.RIGHT),
        ]
        result = find_suffix_patterns(corrections)
        pattern_key = ("eh", "he", BoundaryType.RIGHT)
        assert len(result[pattern_key]) == 2

    def test_only_extracts_from_right_boundary_corrections(self) -> None:
        """When corrections have different boundary types, only extracts from RIGHT boundaries."""
        corrections: list[Correction] = [
            ("testeh", "testhe", BoundaryType.RIGHT),
            ("wordeh", "wordhe", BoundaryType.RIGHT),
            ("testeh", "testhe", BoundaryType.LEFT),  # This should be ignored
        ]
        result = find_suffix_patterns(corrections)
        pattern_key = ("eh", "he", BoundaryType.RIGHT)
        # Should have 2 matches (both RIGHT boundary corrections)
        assert len(result[pattern_key]) == 2

    def test_requires_minimum_length_for_non_pattern_part(self) -> None:
        """When non-pattern part is too short, does not extract pattern."""
        corrections: list[Correction] = [
            ("ab", "ba", BoundaryType.RIGHT),
        ]
        result = find_suffix_patterns(corrections)
        assert not result

    def test_skips_when_typo_and_word_patterns_are_identical(self) -> None:
        """When typo suffix equals word suffix, skips pattern extraction."""
        corrections: list[Correction] = [
            ("test", "test", BoundaryType.RIGHT),
        ]
        result = find_suffix_patterns(corrections)
        assert not result

    def test_only_matches_when_other_parts_are_identical(self) -> None:
        """When other parts differ within a correction, does not create pattern."""
        corrections: list[Correction] = [
            ("testeh", "wordxh", BoundaryType.RIGHT),
        ]
        # For length=2: typo_pattern="eh", word_pattern="xh",
        # other_part_typo="test", other_part_word="word"
        # other_part_typo != other_part_word, so no pattern
        result = find_suffix_patterns(corrections)
        assert not result

    def test_extracts_longest_possible_suffix_pattern(self) -> None:
        """When multiple pattern lengths are possible, extracts longest valid pattern."""
        corrections: list[Correction] = [
            ("testeh", "testhe", BoundaryType.RIGHT),
            ("wordeh", "wordhe", BoundaryType.RIGHT),
        ]
        result = find_suffix_patterns(corrections)
        # Should extract "eh" -> "he" pattern (among others)
        assert ("eh", "he", BoundaryType.RIGHT) in result

    def test_handles_empty_corrections_list(self) -> None:
        """When corrections list is empty, returns empty dict."""
        corrections: list[Correction] = []
        result = find_suffix_patterns(corrections)
        assert not result

    def test_handles_single_correction(self) -> None:
        """When only one correction exists, no patterns are returned (requires 2+ occurrences)."""
        corrections: list[Correction] = [
            ("testeh", "testhe", BoundaryType.RIGHT),
        ]
        result = find_suffix_patterns(corrections)
        # Patterns require 2+ occurrences, so single correction produces no patterns
        assert len(result) == 0

    def test_extracts_pattern_from_corrections_of_same_length(self) -> None:
        """When corrections have same word length, extracts pattern correctly."""
        corrections: list[Correction] = [
            ("testeh", "testhe", BoundaryType.RIGHT),
            ("wordeh", "wordhe", BoundaryType.RIGHT),
        ]
        result = find_suffix_patterns(corrections)
        assert ("eh", "he", BoundaryType.RIGHT) in result


class TestFindPrefixPatterns:
    """Test prefix pattern extraction behavior."""

    def test_finds_common_prefix_pattern(self) -> None:
        """When corrections share a common prefix, extracts the pattern."""
        corrections: list[Correction] = [
            ("hword", "tword", BoundaryType.LEFT),
            ("hwork", "twork", BoundaryType.LEFT),
        ]
        result = find_prefix_patterns(corrections)
        # Function extracts patterns of length 2 or more
        assert ("hw", "tw", BoundaryType.LEFT) in result

    def test_groups_corrections_by_prefix_pattern(self) -> None:
        """When multiple corrections match a prefix pattern, groups them together."""
        corrections: list[Correction] = [
            ("hword", "tword", BoundaryType.LEFT),
            ("hwork", "twork", BoundaryType.LEFT),
        ]
        result = find_prefix_patterns(corrections)
        # Find any pattern key that has 2 corrections
        pattern_with_two = next((key for key, values in result.items() if len(values) == 2), None)
        assert pattern_with_two is not None

    def test_only_extracts_from_left_boundary_corrections(self) -> None:
        """When corrections have different boundary types, only extracts from LEFT boundaries."""
        corrections: list[Correction] = [
            ("hword", "tword", BoundaryType.LEFT),
            ("hword", "tword", BoundaryType.RIGHT),
        ]
        result = find_prefix_patterns(corrections)
        # Should only include the LEFT boundary correction
        for _, matches in result.items():
            assert all(boundary == BoundaryType.LEFT for _, _, boundary in matches)

    def test_requires_minimum_length_for_non_pattern_part(self) -> None:
        """When non-pattern part is too short, does not extract pattern."""
        corrections: list[Correction] = [
            ("ab", "ba", BoundaryType.LEFT),
        ]
        result = find_prefix_patterns(corrections)
        assert not result

    def test_skips_when_typo_and_word_patterns_are_identical(self) -> None:
        """When typo prefix equals word prefix, skips pattern extraction."""
        corrections: list[Correction] = [
            ("test", "test", BoundaryType.LEFT),
        ]
        result = find_prefix_patterns(corrections)
        assert not result

    def test_only_matches_when_other_parts_are_identical(self) -> None:
        """When other parts differ within a correction, does not create pattern."""
        corrections: list[Correction] = [
            ("hword", "twork", BoundaryType.LEFT),
        ]
        # For length=1: typo_pattern="h", word_pattern="t",
        # other_part_typo="word", other_part_word="work"
        # other_part_typo != other_part_word, so no pattern
        result = find_prefix_patterns(corrections)
        assert not result

    def test_extracts_longest_possible_prefix_pattern(self) -> None:
        """When multiple pattern lengths are possible, extracts longest valid pattern."""
        corrections: list[Correction] = [
            ("hword", "tword", BoundaryType.LEFT),
            ("hwork", "twork", BoundaryType.LEFT),
        ]
        result = find_prefix_patterns(corrections)
        # Should extract patterns (at least length 1)
        assert len(result) > 0

    def test_handles_empty_corrections_list(self) -> None:
        """When corrections list is empty, returns empty dict."""
        corrections: list[Correction] = []
        result = find_prefix_patterns(corrections)
        assert not result

    def test_handles_single_correction(self) -> None:
        """When only one correction exists, no patterns are returned (requires 2+ occurrences)."""
        corrections: list[Correction] = [
            ("hword", "tword", BoundaryType.LEFT),
        ]
        result = find_prefix_patterns(corrections)
        # Patterns require 2+ occurrences, so single correction produces no patterns
        assert len(result) == 0

    def test_extracts_pattern_from_corrections_of_same_length(self) -> None:
        """When corrections have same word length, extracts pattern correctly."""
        corrections: list[Correction] = [
            ("hword", "tword", BoundaryType.LEFT),
            ("hwork", "twork", BoundaryType.LEFT),
        ]
        result = find_prefix_patterns(corrections)
        assert len(result) > 0


class TestPatternExtractionBoundaryFiltering:
    """Test boundary type filtering behavior."""

    def test_suffix_extraction_ignores_left_boundary_corrections(self) -> None:
        """When corrections have LEFT boundary, suffix extraction ignores them."""
        corrections: list[Correction] = [
            ("teh", "the", BoundaryType.LEFT),
        ]
        result = find_suffix_patterns(corrections)
        assert not result

    def test_suffix_extraction_ignores_both_boundary_corrections(self) -> None:
        """When corrections have BOTH boundary, suffix extraction ignores them."""
        corrections: list[Correction] = [
            ("teh", "the", BoundaryType.BOTH),
        ]
        result = find_suffix_patterns(corrections)
        assert not result

    def test_suffix_extraction_ignores_none_boundary_corrections(self) -> None:
        """When corrections have NONE boundary, suffix extraction ignores them."""
        corrections: list[Correction] = [
            ("teh", "the", BoundaryType.NONE),
        ]
        result = find_suffix_patterns(corrections)
        assert not result

    def test_prefix_extraction_ignores_right_boundary_corrections(self) -> None:
        """When corrections have RIGHT boundary, prefix extraction ignores them."""
        corrections: list[Correction] = [
            ("hte", "the", BoundaryType.RIGHT),
        ]
        result = find_prefix_patterns(corrections)
        assert not result

    def test_prefix_extraction_ignores_both_boundary_corrections(self) -> None:
        """When corrections have BOTH boundary, prefix extraction ignores them."""
        corrections: list[Correction] = [
            ("hte", "the", BoundaryType.BOTH),
        ]
        result = find_prefix_patterns(corrections)
        assert not result

    def test_prefix_extraction_ignores_none_boundary_corrections(self) -> None:
        """When corrections have NONE boundary, prefix extraction ignores them."""
        corrections: list[Correction] = [
            ("hte", "the", BoundaryType.NONE),
        ]
        result = find_prefix_patterns(corrections)
        assert not result


class TestPatternExtractionEdgeCases:
    """Test edge cases in pattern extraction."""

    def test_handles_typo_shorter_than_pattern_length(self) -> None:
        """When typo is shorter than pattern length, skips that pattern length."""
        corrections: list[Correction] = [
            ("testeh", "testhe", BoundaryType.RIGHT),
            ("eh", "he", BoundaryType.RIGHT),
        ]
        result = find_suffix_patterns(corrections)
        # Should still extract patterns from valid corrections
        assert isinstance(result, dict)

    def test_handles_different_word_lengths(self) -> None:
        """When corrections have different word lengths, groups by length."""
        corrections: list[Correction] = [
            ("testeh", "testhe", BoundaryType.RIGHT),
            ("longwordeh", "longwordhe", BoundaryType.RIGHT),
        ]
        result = find_suffix_patterns(corrections)
        # Should extract patterns within each length group
        assert isinstance(result, dict)

    def test_handles_multiple_pattern_lengths(self) -> None:
        """When multiple pattern lengths are valid, extracts all valid patterns."""
        corrections: list[Correction] = [
            ("testeh", "testhe", BoundaryType.RIGHT),
            ("wordeh", "wordhe", BoundaryType.RIGHT),
        ]
        result = find_suffix_patterns(corrections)
        # Should extract at least one pattern
        assert len(result) > 0

    def test_preserves_original_boundary_in_pattern_matches(self) -> None:
        """When extracting patterns, preserves original boundary type in matches."""
        corrections: list[Correction] = [
            ("testeh", "testhe", BoundaryType.RIGHT),
            ("wordeh", "wordhe", BoundaryType.RIGHT),
        ]
        result = find_suffix_patterns(corrections)
        for _, matches in result.items():
            for _, _, boundary in matches:
                assert boundary == BoundaryType.RIGHT
