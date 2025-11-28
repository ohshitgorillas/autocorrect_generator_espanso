"""Integration tests for conflict resolution refactoring.

These tests verify that the refactored conflict resolution module produces
identical behavior to the original implementation across all boundary types
and various real-world scenarios.
"""

from entroppy.config import BoundaryType
from entroppy.processing import remove_substring_conflicts


class TestRemoveSubstringConflictsIntegration:
    """Integration tests for remove_substring_conflicts() with refactored module."""

    def test_handles_empty_corrections_list(self) -> None:
        """Empty list produces empty result."""
        result = remove_substring_conflicts([])
        assert not result

    def test_preserves_single_correction(self) -> None:
        """Single correction is preserved unchanged."""
        corrections = [("teh", "the", BoundaryType.NONE)]
        result = remove_substring_conflicts(corrections)
        assert result == corrections

    def test_right_boundary_conflict_removes_longer(self) -> None:
        """RIGHT boundary: longer suffix is removed when shorter produces correct result."""
        corrections = [
            ("herre", "here", BoundaryType.RIGHT),
            ("wherre", "where", BoundaryType.RIGHT),
        ]
        result = remove_substring_conflicts(corrections)
        assert ("wherre", "where", BoundaryType.RIGHT) not in result

    def test_right_boundary_conflict_keeps_shorter(self) -> None:
        """RIGHT boundary: shorter suffix is kept when it blocks longer."""
        corrections = [
            ("herre", "here", BoundaryType.RIGHT),
            ("wherre", "where", BoundaryType.RIGHT),
        ]
        result = remove_substring_conflicts(corrections)
        assert ("herre", "here", BoundaryType.RIGHT) in result

    def test_left_boundary_conflict_removes_longer(self) -> None:
        """LEFT boundary: longer prefix is removed when shorter produces correct result."""
        corrections = [
            ("teh", "the", BoundaryType.LEFT),
            ("tehir", "their", BoundaryType.LEFT),
        ]
        result = remove_substring_conflicts(corrections)
        assert ("tehir", "their", BoundaryType.LEFT) not in result

    def test_left_boundary_conflict_keeps_shorter(self) -> None:
        """LEFT boundary: shorter prefix is kept when it blocks longer."""
        corrections = [
            ("teh", "the", BoundaryType.LEFT),
            ("tehir", "their", BoundaryType.LEFT),
        ]
        result = remove_substring_conflicts(corrections)
        assert ("teh", "the", BoundaryType.LEFT) in result

    def test_none_boundary_conflict_removes_longer(self) -> None:
        """NONE boundary: longer prefix is removed when shorter produces correct result."""
        corrections = [
            ("teh", "the", BoundaryType.NONE),
            ("tehir", "their", BoundaryType.NONE),
        ]
        result = remove_substring_conflicts(corrections)
        assert ("tehir", "their", BoundaryType.NONE) not in result

    def test_none_boundary_conflict_keeps_shorter(self) -> None:
        """NONE boundary: shorter prefix is kept when it blocks longer."""
        corrections = [
            ("teh", "the", BoundaryType.NONE),
            ("tehir", "their", BoundaryType.NONE),
        ]
        result = remove_substring_conflicts(corrections)
        assert ("teh", "the", BoundaryType.NONE) in result

    def test_both_boundary_conflict_removes_longer(self) -> None:
        """BOTH boundary: longer prefix is removed when shorter produces correct result."""
        corrections = [
            ("teh", "the", BoundaryType.BOTH),
            ("tehir", "their", BoundaryType.BOTH),
        ]
        result = remove_substring_conflicts(corrections)
        assert ("tehir", "their", BoundaryType.BOTH) not in result

    def test_both_boundary_conflict_keeps_shorter(self) -> None:
        """BOTH boundary: shorter prefix is kept when it blocks longer."""
        corrections = [
            ("teh", "the", BoundaryType.BOTH),
            ("tehir", "their", BoundaryType.BOTH),
        ]
        result = remove_substring_conflicts(corrections)
        assert ("teh", "the", BoundaryType.BOTH) in result

    def test_non_conflicting_first_correction_preserved(self) -> None:
        """First non-conflicting correction is preserved."""
        corrections = [
            ("abc", "xyz", BoundaryType.NONE),
            ("def", "uvw", BoundaryType.NONE),
        ]
        result = remove_substring_conflicts(corrections)
        assert ("abc", "xyz", BoundaryType.NONE) in result

    def test_non_conflicting_second_correction_preserved(self) -> None:
        """Second non-conflicting correction is preserved."""
        corrections = [
            ("abc", "xyz", BoundaryType.NONE),
            ("def", "uvw", BoundaryType.NONE),
        ]
        result = remove_substring_conflicts(corrections)
        assert ("def", "uvw", BoundaryType.NONE) in result

    def test_handles_mixed_boundaries_correctly(self) -> None:
        """Corrections with different boundaries don't conflict."""
        corrections = [
            ("teh", "the", BoundaryType.NONE),
            ("teh", "the", BoundaryType.LEFT),
            ("teh", "the", BoundaryType.RIGHT),
            ("teh", "the", BoundaryType.BOTH),
        ]
        result = remove_substring_conflicts(corrections)
        # All should be kept because they have different boundaries
        assert len(result) == 4

    def test_first_conflict_group_shorter_kept(self) -> None:
        """First conflict group: shorter correction is kept."""
        corrections = [
            ("teh", "the", BoundaryType.NONE),
            ("tehir", "their", BoundaryType.NONE),
            ("adn", "and", BoundaryType.NONE),
            ("adnroid", "android", BoundaryType.NONE),
        ]
        result = remove_substring_conflicts(corrections)
        assert ("teh", "the", BoundaryType.NONE) in result

    def test_first_conflict_group_longer_removed(self) -> None:
        """First conflict group: longer correction is removed."""
        corrections = [
            ("teh", "the", BoundaryType.NONE),
            ("tehir", "their", BoundaryType.NONE),
            ("adn", "and", BoundaryType.NONE),
            ("adnroid", "android", BoundaryType.NONE),
        ]
        result = remove_substring_conflicts(corrections)
        assert ("tehir", "their", BoundaryType.NONE) not in result

    def test_second_conflict_group_shorter_kept(self) -> None:
        """Second conflict group: shorter correction is kept."""
        corrections = [
            ("teh", "the", BoundaryType.NONE),
            ("tehir", "their", BoundaryType.NONE),
            ("adn", "and", BoundaryType.NONE),
            ("adnroid", "android", BoundaryType.NONE),
        ]
        result = remove_substring_conflicts(corrections)
        assert ("adn", "and", BoundaryType.NONE) in result

    def test_second_conflict_group_longer_removed(self) -> None:
        """Second conflict group: longer correction is removed."""
        corrections = [
            ("teh", "the", BoundaryType.NONE),
            ("tehir", "their", BoundaryType.NONE),
            ("adn", "and", BoundaryType.NONE),
            ("adnroid", "android", BoundaryType.NONE),
        ]
        result = remove_substring_conflicts(corrections)
        assert ("adnroid", "android", BoundaryType.NONE) not in result

    def test_transitive_conflict_shortest_kept(self) -> None:
        """Transitive conflicts: shortest correction is kept."""
        corrections = [
            ("er", "or", BoundaryType.RIGHT),
            ("ter", "tor", BoundaryType.RIGHT),
            ("ster", "stor", BoundaryType.RIGHT),
        ]
        result = remove_substring_conflicts(corrections)
        assert ("er", "or", BoundaryType.RIGHT) in result

    def test_transitive_conflict_middle_removed(self) -> None:
        """Transitive conflicts: middle correction is removed."""
        corrections = [
            ("er", "or", BoundaryType.RIGHT),
            ("ter", "tor", BoundaryType.RIGHT),
            ("ster", "stor", BoundaryType.RIGHT),
        ]
        result = remove_substring_conflicts(corrections)
        assert ("ter", "tor", BoundaryType.RIGHT) not in result

    def test_transitive_conflict_longest_removed(self) -> None:
        """Transitive conflicts: longest correction is removed."""
        corrections = [
            ("er", "or", BoundaryType.RIGHT),
            ("ter", "tor", BoundaryType.RIGHT),
            ("ster", "stor", BoundaryType.RIGHT),
        ]
        result = remove_substring_conflicts(corrections)
        assert ("ster", "stor", BoundaryType.RIGHT) not in result

    def test_keeps_corrections_that_dont_resolve_correctly(self) -> None:
        """Corrections that don't resolve to correct word are kept."""
        corrections = [
            ("herre", "hello", BoundaryType.RIGHT),
            ("wherre", "where", BoundaryType.RIGHT),
        ]
        result = remove_substring_conflicts(corrections)
        assert len(result) == 2

    def test_verbose_false_keeps_shorter_correction(self) -> None:
        """Verbose=False keeps shorter correction."""
        corrections = [
            ("teh", "the", BoundaryType.NONE),
            ("tehir", "their", BoundaryType.NONE),
        ]
        result = remove_substring_conflicts(corrections, verbose=False)
        assert ("teh", "the", BoundaryType.NONE) in result

    def test_verbose_true_keeps_shorter_correction(self) -> None:
        """Verbose=True keeps shorter correction."""
        corrections = [
            ("teh", "the", BoundaryType.NONE),
            ("tehir", "their", BoundaryType.NONE),
        ]
        result = remove_substring_conflicts(corrections, verbose=True)
        assert ("teh", "the", BoundaryType.NONE) in result

    def test_verbose_false_removes_longer_correction(self) -> None:
        """Verbose=False removes longer correction."""
        corrections = [
            ("teh", "the", BoundaryType.NONE),
            ("tehir", "their", BoundaryType.NONE),
        ]
        result = remove_substring_conflicts(corrections, verbose=False)
        assert ("tehir", "their", BoundaryType.NONE) not in result

    def test_verbose_true_removes_longer_correction(self) -> None:
        """Verbose=True removes longer correction."""
        corrections = [
            ("teh", "the", BoundaryType.NONE),
            ("tehir", "their", BoundaryType.NONE),
        ]
        result = remove_substring_conflicts(corrections, verbose=True)
        assert ("tehir", "their", BoundaryType.NONE) not in result
