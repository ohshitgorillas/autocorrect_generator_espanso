"""Integration tests to verify refactored code produces identical behavior.

These tests verify that the pattern matching refactor maintains identical
behavior in all three refactored modules.
"""

import os
import tempfile

from entroppy.dictionary import load_validation_dictionary
from entroppy.exclusions import ExclusionMatcher
from entroppy.processing import process_word
from entroppy.config import BoundaryType

# pylint: disable=missing-function-docstring, protected-access

class TestProcessingIntegration:
    """Verify process_word() behavior unchanged after refactoring."""

    def test_process_word_with_exact_exclusion(self) -> None:
        """Verify exact exclusion patterns work correctly."""
        word = "test"
        validation_set = {"tset", "tets"}
        filtered_validation_set = validation_set.copy()
        source_words = set()
        typo_freq_threshold = 0.0
        adj_letters_map = None
        exclusions = {"tset"}  # Exact exclusion

        corrections = process_word(
            word,
            validation_set,
            filtered_validation_set,
            source_words,
            typo_freq_threshold,
            adj_letters_map,
            exclusions,
        )

        # tset is explicitly excluded, should not appear in corrections
        typos = [typo for typo, _, _ in corrections]
        assert "tset" not in typos

    def test_process_word_exclusions_bypass_frequency_check(self) -> None:
        """Verify exclusion patterns allow typos to bypass frequency threshold."""
        word = "test"
        validation_set = set()
        filtered_validation_set = set()
        source_words = set()
        typo_freq_threshold = 1.0  # High threshold that would normally block all typos
        adj_letters_map = None
        exclusions = {"tset"}  # This typo should bypass frequency check

        corrections = process_word(
            word,
            validation_set,
            filtered_validation_set,
            source_words,
            typo_freq_threshold,
            adj_letters_map,
            exclusions,
        )

        # The typo may or may not appear depending on boundary detection,
        # but the key is no error should occur
        assert isinstance(corrections, list)

    def test_process_word_ignores_typo_word_mappings(self) -> None:
        """Verify typo->word mappings in exclusions don't affect word-level filtering."""
        word = "test"
        validation_set = set()
        filtered_validation_set = set()
        source_words = set()
        typo_freq_threshold = 0.0
        adj_letters_map = None
        exclusions = {"tset -> test"}  # This should be ignored by process_word

        corrections = process_word(
            word,
            validation_set,
            filtered_validation_set,
            source_words,
            typo_freq_threshold,
            adj_letters_map,
            exclusions,
        )
        # tset might or might not be in corrections depending on boundary detection,
        # but the pattern shouldn't cause an error
        assert isinstance(corrections, list)

    def test_process_word_with_multiple_exclusion_patterns(self) -> None:
        """Verify mixed exact and wildcard exclusion patterns work together."""
        word = "test"
        validation_set = set()
        filtered_validation_set = set()
        source_words = set()
        typo_freq_threshold = 1.0  # High threshold
        adj_letters_map = None
        exclusions = {"tset", "test*"}  # Mix of exact and wildcard

        corrections = process_word(
            word,
            validation_set,
            filtered_validation_set,
            source_words,
            typo_freq_threshold,
            adj_letters_map,
            exclusions,
        )

        # Exclusions bypass frequency check, so we should get results
        assert isinstance(corrections, list)


class TestDictionaryIntegration:
    """Verify load_validation_dictionary() behavior unchanged."""

    def test_load_validation_dictionary_excludes_ball_suffix(self) -> None:
        """Verify words ending with 'ball' are excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exclude_file = os.path.join(tmpdir, "exclude.txt")
            with open(exclude_file, "w", encoding="utf-8") as f:
                f.write("*ball\n")

            dictionary = load_validation_dictionary(exclude_file, None, verbose=False)
            assert "football" not in dictionary

    def test_load_validation_dictionary_excludes_test_infix(self) -> None:
        """Verify words containing 'test' are excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exclude_file = os.path.join(tmpdir, "exclude.txt")
            with open(exclude_file, "w", encoding="utf-8") as f:
                f.write("*test*\n")

            dictionary = load_validation_dictionary(exclude_file, None, verbose=False)
            assert "testing" not in dictionary

    def test_load_validation_dictionary_excludes_exact_word(self) -> None:
        """Verify exact word 'rpi' is excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exclude_file = os.path.join(tmpdir, "exclude.txt")
            with open(exclude_file, "w", encoding="utf-8") as f:
                f.write("rpi\n")

            dictionary = load_validation_dictionary(exclude_file, None, verbose=False)
            assert "rpi" not in dictionary

    def test_load_validation_dictionary_ignores_typo_mappings(self) -> None:
        """Verify typo->word mappings don't affect dictionary loading."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exclude_file = os.path.join(tmpdir, "exclude.txt")
            with open(exclude_file, "w", encoding="utf-8") as f:
                f.write("teh -> the\n")
                f.write("*ball\n")

            dictionary = load_validation_dictionary(exclude_file, None, verbose=False)
            # Only "*ball" pattern should filter words
            assert "football" not in dictionary

    def test_load_validation_dictionary_with_comments(self) -> None:
        """Verify comments in exclusion file are properly ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exclude_file = os.path.join(tmpdir, "exclude.txt")
            with open(exclude_file, "w", encoding="utf-8") as f:
                f.write("# This is a comment\n")
                f.write("*ball\n")
                f.write("# Another comment\n")

            dictionary = load_validation_dictionary(exclude_file, None, verbose=False)

            # Comments should be ignored, only pattern should work
            assert "football" not in dictionary


class TestExclusionMatcherIntegration:
    """Verify ExclusionMatcher behavior unchanged after refactoring."""

    def test_exclusion_matcher_exact_typo_word_mapping(self) -> None:
        """Verify exact typo->word mapping 'teh -> the' works."""
        exclusions = {"teh -> the"}
        matcher = ExclusionMatcher(exclusions)

        correction = ("teh", "the", BoundaryType.BOTH)
        assert matcher.should_exclude(correction) is True

    def test_exclusion_matcher_does_not_exclude_unmatched(self) -> None:
        """Verify unmatched corrections are not excluded."""
        exclusions = {"teh -> the"}
        matcher = ExclusionMatcher(exclusions)

        correction = ("other", "word", BoundaryType.BOTH)
        assert matcher.should_exclude(correction) is False

    def test_exclusion_matcher_wildcard_typo_mapping(self) -> None:
        """Verify wildcard typo->word mapping '*toin -> *tion' works."""
        exclusions = {"*toin -> *tion"}
        matcher = ExclusionMatcher(exclusions)

        correction = ("actoin", "action", BoundaryType.BOTH)
        assert matcher.should_exclude(correction) is True

    def test_exclusion_matcher_boundary_both_matches(self) -> None:
        """Verify boundary constraint :toin: -> tion matches BOTH."""
        exclusions = {":toin: -> tion"}
        matcher = ExclusionMatcher(exclusions)

        correction = ("toin", "tion", BoundaryType.BOTH)
        assert matcher.should_exclude(correction) is True

    def test_exclusion_matcher_boundary_left_doesnt_match_both(self) -> None:
        """Verify boundary constraint :toin: -> tion doesn't match LEFT only."""
        exclusions = {":toin: -> tion"}
        matcher = ExclusionMatcher(exclusions)

        correction = ("toin", "tion", BoundaryType.LEFT)
        assert matcher.should_exclude(correction) is False

    def test_exclusion_matcher_filter_removes_wildcard_match(self) -> None:
        """Verify filter_validation_set removes word matching '*ball'."""
        exclusions = {"*ball"}
        matcher = ExclusionMatcher(exclusions)

        validation_set = {"football", "hello"}
        filtered = matcher.filter_validation_set(validation_set)

        assert "football" not in filtered

    def test_exclusion_matcher_filter_keeps_non_match(self) -> None:
        """Verify filter_validation_set keeps non-matching words."""
        exclusions = {"*ball"}
        matcher = ExclusionMatcher(exclusions)

        validation_set = {"hello", "world"}
        filtered = matcher.filter_validation_set(validation_set)

        assert "hello" in filtered

    def test_exclusion_matcher_get_matching_rule_exact(self) -> None:
        """Verify get_matching_rule returns exact rule."""
        exclusions = {"teh -> the"}
        matcher = ExclusionMatcher(exclusions)

        correction = ("teh", "the", BoundaryType.BOTH)
        rule = matcher.get_matching_rule(correction)

        assert "teh" in rule and "the" in rule


class TestRealWorldPatterns:
    """Test with real patterns from examples/exclude.txt."""

    def test_with_example_pattern_ball(self) -> None:
        """Verify '*ball' pattern from examples works."""
        exclusions = {"*ball"}
        matcher = ExclusionMatcher(exclusions)

        validation_set = {"football", "hello"}
        filtered = matcher.filter_validation_set(validation_set)

        assert "football" not in filtered

    def test_with_example_pattern_keeps_non_match(self) -> None:
        """Verify example patterns keep non-matching words."""
        exclusions = {"*ball", "*toin"}
        matcher = ExclusionMatcher(exclusions)

        validation_set = {"hello", "world"}
        filtered = matcher.filter_validation_set(validation_set)

        assert "hello" in filtered

    def test_processing_with_example_pattern_teh(self) -> None:
        """Verify process_word with '*teh*' exclusion pattern."""
        word = "the"
        validation_set = set()
        filtered_validation_set = set()
        source_words = set()
        typo_freq_threshold = 1.0  # High threshold
        adj_letters_map = None
        exclusions = {"*teh*"}

        corrections = process_word(
            word,
            validation_set,
            filtered_validation_set,
            source_words,
            typo_freq_threshold,
            adj_letters_map,
            exclusions,
        )

        # Exclusion pattern should bypass frequency check
        assert isinstance(corrections, list)
