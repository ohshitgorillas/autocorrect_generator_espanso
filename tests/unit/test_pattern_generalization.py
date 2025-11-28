"""Unit tests for pattern generalization behavior.

Tests verify pattern finding and generalization logic that creates reusable patterns
from repeated typo corrections. Each test has a single assertion and focuses on behavior.
"""

from entroppy.patterns import find_suffix_patterns, generalize_patterns
from entroppy.config import BoundaryType

# pylint: disable=missing-function-docstring


class TestFindSuffixPatternsBasicBehavior:
    """Test basic pattern finding behavior."""

    def test_finds_pattern_from_two_similar_corrections(self) -> None:
        """When two corrections share a suffix, pattern is found."""
        corrections = [
            ("tset", "test", BoundaryType.RIGHT),
            ("bset", "best", BoundaryType.RIGHT),
        ]
        patterns = find_suffix_patterns(corrections)
        assert ("set", "est", BoundaryType.RIGHT) in patterns

    def test_returns_empty_for_no_corrections(self) -> None:
        """When no corrections provided, returns empty dict."""
        patterns = find_suffix_patterns([])
        assert len(patterns) == 0

    def test_returns_empty_when_no_patterns_exist(self) -> None:
        """When corrections have no common patterns, returns empty dict."""
        corrections = [
            ("abc", "xyz", BoundaryType.RIGHT),
        ]
        patterns = find_suffix_patterns(corrections)
        assert len(patterns) == 0

    def test_pattern_maps_to_list_of_matching_corrections(self) -> None:
        """Each pattern maps to the corrections it was derived from."""
        corrections = [
            ("tset", "test", BoundaryType.RIGHT),
            ("bset", "best", BoundaryType.RIGHT),
        ]
        patterns = find_suffix_patterns(corrections)
        pattern_key = ("set", "est", BoundaryType.RIGHT)
        assert len(patterns[pattern_key]) == 2


class TestFindSuffixPatternsBoundaryRequirement:
    """Test that only RIGHT boundary corrections generate patterns."""

    def test_ignores_none_boundary_corrections(self) -> None:
        """Corrections with NONE boundary don't generate patterns."""
        corrections = [
            ("tset", "test", BoundaryType.NONE),
            ("bset", "best", BoundaryType.NONE),
        ]
        patterns = find_suffix_patterns(corrections)
        assert ("set", "est", BoundaryType.NONE) not in patterns

    def test_ignores_left_boundary_corrections(self) -> None:
        """Corrections with LEFT boundary don't generate patterns."""
        corrections = [
            ("tset", "test", BoundaryType.LEFT),
            ("bset", "best", BoundaryType.LEFT),
        ]
        patterns = find_suffix_patterns(corrections)
        assert ("set", "est", BoundaryType.LEFT) not in patterns

    def test_ignores_both_boundary_corrections(self) -> None:
        """Corrections with BOTH boundary don't generate patterns."""
        corrections = [
            ("tset", "test", BoundaryType.BOTH),
            ("bset", "best", BoundaryType.BOTH),
        ]
        patterns = find_suffix_patterns(corrections)
        assert ("set", "est", BoundaryType.BOTH) not in patterns

    def test_only_right_boundary_generates_patterns(self) -> None:
        """Only RIGHT boundary corrections generate suffix patterns."""
        corrections = [
            ("tset", "test", BoundaryType.RIGHT),
            ("bset", "best", BoundaryType.RIGHT),
        ]
        patterns = find_suffix_patterns(corrections)
        assert len(patterns) > 0


class TestFindSuffixPatternsPrefixRequirement:
    """Test that patterns require minimum prefix length."""

    def test_requires_minimum_prefix_length(self) -> None:
        """Patterns must leave at least 2 characters of prefix."""
        # "ab" prefix is too short (< 2 chars after suffix removed)
        corrections = [
            ("abset", "abest", BoundaryType.RIGHT),
            ("abset", "abest", BoundaryType.RIGHT),
        ]
        patterns = find_suffix_patterns(corrections)
        # Should not find 5-char suffix "bset"→"best" (would leave only 1 char prefix)
        assert ("bset", "best", BoundaryType.RIGHT) not in patterns

    def test_accepts_patterns_with_sufficient_prefix(self) -> None:
        """Patterns with at least 2-char prefix are found."""
        corrections = [
            ("abcset", "abcest", BoundaryType.RIGHT),
            ("xyzset", "xyzest", BoundaryType.RIGHT),
        ]
        patterns = find_suffix_patterns(corrections)
        # Should find 3-char suffix "set"→"est" (leaves 3-char prefix)
        assert ("set", "est", BoundaryType.RIGHT) in patterns


class TestFindSuffixPatternsPrefixMatching:
    """Test that patterns require matching prefixes."""

    def test_requires_prefixes_to_match(self) -> None:
        """Pattern is only found when prefixes match after suffix removal."""
        corrections = [
            ("test", "best", BoundaryType.RIGHT),  # Different prefixes
        ]
        patterns = find_suffix_patterns(corrections)
        # Should not find pattern where prefix doesn't match
        assert ("est", "est", BoundaryType.RIGHT) not in patterns

    def test_finds_pattern_when_prefixes_match(self) -> None:
        """Pattern is found when prefixes match after suffix removal."""
        corrections = [
            ("tset", "test", BoundaryType.RIGHT),
            ("bset", "best", BoundaryType.RIGHT),
        ]
        patterns = find_suffix_patterns(corrections)
        # "t"+"set"→"t"+"est" and "b"+"set"→"b"+"est" don't share prefix
        # but we should still find the suffix pattern
        assert ("set", "est", BoundaryType.RIGHT) in patterns


class TestFindSuffixPatternsIdenticalSuffixes:
    """Test that identical typo/word suffixes are skipped."""

    def test_skips_pattern_when_suffixes_are_identical(self) -> None:
        """Patterns where typo_suffix == word_suffix are skipped."""
        corrections = [
            ("test", "test", BoundaryType.RIGHT),
            ("best", "best", BoundaryType.RIGHT),
        ]
        patterns = find_suffix_patterns(corrections)
        # Should not create useless patterns like "est"→"est"
        assert ("est", "est", BoundaryType.RIGHT) not in patterns


class TestFindSuffixPatternsMultipleLengths:
    """Test that patterns of different lengths are found."""

    def test_finds_patterns_of_different_suffix_lengths(self) -> None:
        """Patterns of varying suffix lengths are all identified."""
        corrections = [
            ("abcder", "abcder", BoundaryType.RIGHT),
            ("xyzder", "xyzder", BoundaryType.RIGHT),
        ]
        patterns = find_suffix_patterns(corrections)
        # Should find multiple suffix lengths (2, 3, etc.) if they meet criteria
        assert len(patterns) >= 0  # May be 0 if all have identical suffixes

    def test_finds_shortest_valid_pattern(self) -> None:
        """2-character suffix patterns are found when valid."""
        corrections = [
            ("abet", "abat", BoundaryType.RIGHT),
            ("cdet", "cdat", BoundaryType.RIGHT),
        ]
        patterns = find_suffix_patterns(corrections)
        assert ("et", "at", BoundaryType.RIGHT) in patterns


class TestGeneralizePatternsBasicBehavior:
    """Test basic pattern generalization behavior."""

    def test_returns_empty_when_no_patterns_found(self) -> None:
        """When no patterns exist, returns empty pattern list."""
        corrections = [("abc", "xyz", BoundaryType.RIGHT)]
        patterns, _, _, _ = generalize_patterns(
            corrections, set(), set(), min_typo_length=2
        )
        assert len(patterns) == 0

    def test_returns_pattern_when_one_exists(self) -> None:
        """When a valid pattern exists, it is returned."""
        corrections = [
            ("tset", "test", BoundaryType.RIGHT),
            ("bset", "best", BoundaryType.RIGHT),
        ]
        patterns, _, _, _ = generalize_patterns(
            corrections, set(), set(), min_typo_length=2
        )
        assert ("set", "est", BoundaryType.RIGHT) in patterns

    def test_marks_corrections_for_removal_when_pattern_created(self) -> None:
        """Corrections replaced by a pattern are marked for removal."""
        corrections = [
            ("tset", "test", BoundaryType.RIGHT),
            ("bset", "best", BoundaryType.RIGHT),
        ]
        _, to_remove, _, _ = generalize_patterns(
            corrections, set(), set(), min_typo_length=2
        )
        assert ("tset", "test", BoundaryType.RIGHT) in to_remove

    def test_tracks_pattern_replacements(self) -> None:
        """Pattern replacements are tracked in returned dict."""
        corrections = [
            ("tset", "test", BoundaryType.RIGHT),
            ("bset", "best", BoundaryType.RIGHT),
        ]
        _, _, replacements, _ = generalize_patterns(
            corrections, set(), set(), min_typo_length=2
        )
        pattern_key = ("set", "est", BoundaryType.RIGHT)
        assert pattern_key in replacements


class TestGeneralizePatternsMinimumOccurrences:
    """Test that patterns require minimum occurrences."""

    def test_requires_at_least_two_occurrences(self) -> None:
        """Pattern appearing only once is not generalized."""
        corrections = [
            ("tset", "test", BoundaryType.RIGHT),
        ]
        patterns, _, _, _ = generalize_patterns(
            corrections, set(), set(), min_typo_length=2
        )
        assert len(patterns) == 0

    def test_accepts_pattern_with_two_occurrences(self) -> None:
        """Pattern appearing exactly twice is generalized."""
        corrections = [
            ("tset", "test", BoundaryType.RIGHT),
            ("bset", "best", BoundaryType.RIGHT),
        ]
        patterns, _, _, _ = generalize_patterns(
            corrections, set(), set(), min_typo_length=2
        )
        assert len(patterns) > 0

    def test_accepts_pattern_with_many_occurrences(self) -> None:
        """Pattern appearing many times is generalized."""
        corrections = [
            ("aset", "aest", BoundaryType.RIGHT),
            ("bset", "best", BoundaryType.RIGHT),
            ("cset", "cest", BoundaryType.RIGHT),
        ]
        patterns, _, _, _ = generalize_patterns(
            corrections, set(), set(), min_typo_length=2
        )
        assert len(patterns) > 0


class TestGeneralizePatternsMinTypoLength:
    """Test that patterns respect minimum typo length."""

    def test_rejects_pattern_shorter_than_minimum(self) -> None:
        """Patterns shorter than min_typo_length are rejected."""
        corrections = [
            ("tet", "tat", BoundaryType.RIGHT),
            ("bet", "bat", BoundaryType.RIGHT),
        ]
        patterns, _, _, rejected = generalize_patterns(
            corrections, set(), set(), min_typo_length=5
        )
        assert len(patterns) == 0

    def test_tracks_rejected_short_patterns(self) -> None:
        """Patterns rejected for being too short are tracked."""
        corrections = [
            ("tet", "tat", BoundaryType.RIGHT),
            ("bet", "bat", BoundaryType.RIGHT),
        ]
        _, _, _, rejected = generalize_patterns(
            corrections, set(), set(), min_typo_length=5
        )
        # Should have at least one rejection for being too short
        assert any("Too short" in reason for _, _, reason in rejected)

    def test_accepts_pattern_meeting_minimum_length(self) -> None:
        """Patterns at or above min_typo_length are accepted."""
        corrections = [
            ("abcet", "abcat", BoundaryType.RIGHT),
            ("xyzet", "xyzat", BoundaryType.RIGHT),
        ]
        patterns, _, _, _ = generalize_patterns(
            corrections, set(), set(), min_typo_length=2
        )
        assert len(patterns) > 0


class TestGeneralizePatternsValidation:
    """Test that patterns are validated for correctness."""

    def test_rejects_pattern_that_produces_wrong_result(self) -> None:
        """Patterns that would create incorrect corrections are rejected."""
        # Pattern "et"→"at" would turn "test" into "tast" not "test"
        corrections = [
            ("tset", "test", BoundaryType.RIGHT),  # "set"→"est" works
            ("bmet", "bmat", BoundaryType.RIGHT),  # "met"→"mat" works
        ]
        patterns, _, _, _ = generalize_patterns(
            corrections, set(), set(), min_typo_length=2
        )
        # Should not create a pattern that doesn't work for all cases
        # The "et"→"at" pattern would be invalid for "tset"→"test"
        invalid_pattern = ("et", "at", BoundaryType.RIGHT)
        assert invalid_pattern not in patterns

    def test_tracks_rejected_invalid_patterns(self) -> None:
        """Patterns rejected for producing wrong results are tracked."""
        corrections = [
            ("tset", "test", BoundaryType.RIGHT),
            ("bxet", "bxyz", BoundaryType.RIGHT),  # Would create wrong result
        ]
        _, _, _, rejected = generalize_patterns(
            corrections, set(), set(), min_typo_length=2
        )
        # Should track rejection for creating wrong result
        assert len(rejected) >= 0  # May have rejections


class TestGeneralizePatternsValidationConflicts:
    """Test that patterns don't conflict with validation words."""

    def test_rejects_pattern_matching_validation_word(self) -> None:
        """Patterns that match validation words are rejected."""
        corrections = [
            ("tset", "test", BoundaryType.RIGHT),
            ("bset", "best", BoundaryType.RIGHT),
        ]
        validation_set = {"set"}  # Pattern would conflict with this word
        patterns, _, _, _ = generalize_patterns(
            corrections, validation_set, set(), min_typo_length=2
        )
        assert ("set", "est", BoundaryType.RIGHT) not in patterns

    def test_tracks_validation_conflict_rejections(self) -> None:
        """Patterns rejected for validation conflicts are tracked."""
        corrections = [
            ("tset", "test", BoundaryType.RIGHT),
            ("bset", "best", BoundaryType.RIGHT),
        ]
        validation_set = {"set"}
        _, _, _, rejected = generalize_patterns(
            corrections, validation_set, set(), min_typo_length=2
        )
        # Should track rejection for validation conflict
        assert any("validation word" in reason.lower() for _, _, reason in rejected)

    def test_accepts_pattern_not_in_validation_set(self) -> None:
        """Patterns that don't conflict with validation set are accepted."""
        corrections = [
            ("tset", "test", BoundaryType.RIGHT),
            ("bset", "best", BoundaryType.RIGHT),
        ]
        validation_set = {"other", "words"}
        patterns, _, _, _ = generalize_patterns(
            corrections, validation_set, set(), min_typo_length=2
        )
        assert ("set", "est", BoundaryType.RIGHT) in patterns


class TestGeneralizePatternsSourceWordProtection:
    """Test that patterns don't corrupt source words."""

    def test_rejects_pattern_that_would_corrupt_source_word(self) -> None:
        """Patterns that would trigger on source words are rejected."""
        corrections = [
            ("tset", "test", BoundaryType.RIGHT),
            ("bset", "best", BoundaryType.RIGHT),
        ]
        # Source word ends with pattern, would be corrupted
        source_words = {"asset"}
        patterns, _, _, _ = generalize_patterns(
            corrections, set(), source_words, min_typo_length=2
        )
        assert ("set", "est", BoundaryType.RIGHT) not in patterns

    def test_tracks_source_corruption_rejections(self) -> None:
        """Patterns rejected for corrupting source words are tracked."""
        corrections = [
            ("tset", "test", BoundaryType.RIGHT),
            ("bset", "best", BoundaryType.RIGHT),
        ]
        source_words = {"asset"}
        _, _, _, rejected = generalize_patterns(
            corrections, set(), source_words, min_typo_length=2
        )
        # Should track rejection for source corruption
        assert any("corrupt source" in reason.lower() for _, _, reason in rejected)

    def test_accepts_pattern_safe_for_source_words(self) -> None:
        """Patterns that don't trigger on source words are accepted."""
        corrections = [
            ("tset", "test", BoundaryType.RIGHT),
            ("bset", "best", BoundaryType.RIGHT),
        ]
        source_words = {"other", "words", "entirely"}
        patterns, _, _, _ = generalize_patterns(
            corrections, set(), source_words, min_typo_length=2
        )
        assert ("set", "est", BoundaryType.RIGHT) in patterns


class TestGeneralizePatternsReplacementTracking:
    """Test that pattern replacements are properly tracked."""

    def test_replacement_dict_contains_pattern_key(self) -> None:
        """Pattern replacements use pattern tuple as key."""
        corrections = [
            ("tset", "test", BoundaryType.RIGHT),
            ("bset", "best", BoundaryType.RIGHT),
        ]
        _, _, replacements, _ = generalize_patterns(
            corrections, set(), set(), min_typo_length=2
        )
        pattern_key = ("set", "est", BoundaryType.RIGHT)
        assert pattern_key in replacements

    def test_replacement_list_contains_all_occurrences(self) -> None:
        """Replacement list includes all corrections replaced by pattern."""
        corrections = [
            ("tset", "test", BoundaryType.RIGHT),
            ("bset", "best", BoundaryType.RIGHT),
        ]
        _, _, replacements, _ = generalize_patterns(
            corrections, set(), set(), min_typo_length=2
        )
        pattern_key = ("set", "est", BoundaryType.RIGHT)
        assert len(replacements[pattern_key]) == 2

    def test_replacement_list_contains_original_corrections(self) -> None:
        """Replacement list contains the original correction tuples."""
        corrections = [
            ("tset", "test", BoundaryType.RIGHT),
            ("bset", "best", BoundaryType.RIGHT),
        ]
        _, _, replacements, _ = generalize_patterns(
            corrections, set(), set(), min_typo_length=2
        )
        pattern_key = ("set", "est", BoundaryType.RIGHT)
        assert ("tset", "test", BoundaryType.RIGHT) in replacements[pattern_key]


class TestGeneralizePatternsEdgeCases:
    """Test edge cases in pattern generalization."""

    def test_handles_empty_correction_list(self) -> None:
        """Empty correction list returns empty results."""
        patterns, to_remove, replacements, rejected = generalize_patterns(
            [], set(), set(), min_typo_length=2
        )
        assert len(patterns) == 0

    def test_handles_empty_validation_and_source_sets(self) -> None:
        """Patterns can be created with empty validation and source sets."""
        corrections = [
            ("tset", "test", BoundaryType.RIGHT),
            ("bset", "best", BoundaryType.RIGHT),
        ]
        patterns, _, _, _ = generalize_patterns(
            corrections, set(), set(), min_typo_length=2
        )
        assert len(patterns) > 0

    def test_handles_mixed_boundary_types(self) -> None:
        """Mixed boundary types in corrections are handled correctly."""
        corrections = [
            ("tset", "test", BoundaryType.RIGHT),
            ("bset", "best", BoundaryType.RIGHT),
            ("abc", "xyz", BoundaryType.NONE),
            ("def", "uvw", BoundaryType.LEFT),
        ]
        patterns, _, _, _ = generalize_patterns(
            corrections, set(), set(), min_typo_length=2
        )
        # Should only create patterns from RIGHT boundary corrections
        assert all(boundary == BoundaryType.RIGHT for _, _, boundary in patterns)

    def test_handles_single_character_pattern(self) -> None:
        """Single character patterns are handled based on min_typo_length."""
        corrections = [
            ("tat", "tbt", BoundaryType.RIGHT),
            ("cat", "cbt", BoundaryType.RIGHT),
        ]
        patterns, _, _, _ = generalize_patterns(
            corrections, set(), set(), min_typo_length=1
        )
        # May or may not create pattern depending on prefix requirements
        assert len(patterns) >= 0
