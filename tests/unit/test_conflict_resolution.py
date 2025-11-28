"""Unit tests for the conflict_resolution module.

Tests verify conflict detection and resolution behavior across different boundary types.
Each test has a single assertion and uses type hints.
"""

from entroppy.config import BoundaryType
from entroppy.conflict_resolution import resolve_conflicts_for_group

# pylint: disable=missing-function-docstring


class TestRightBoundaryConflicts:
    """Test conflict resolution for RIGHT boundary corrections (suffixes)."""

    def test_shorter_suffix_that_resolves_correctly_blocks_longer(self) -> None:
        """wherre→where is blocked when herre→here produces correct result."""
        corrections = [
            ("herre", "here", BoundaryType.RIGHT),
            ("wherre", "where", BoundaryType.RIGHT),
        ]
        result = resolve_conflicts_for_group(corrections, BoundaryType.RIGHT)
        assert ("wherre", "where", BoundaryType.RIGHT) not in result

    def test_shorter_suffix_is_kept_when_it_blocks_longer(self) -> None:
        """herre→here is kept when it blocks wherre→where."""
        corrections = [
            ("herre", "here", BoundaryType.RIGHT),
            ("wherre", "where", BoundaryType.RIGHT),
        ]
        result = resolve_conflicts_for_group(corrections, BoundaryType.RIGHT)
        assert ("herre", "here", BoundaryType.RIGHT) in result

    def test_longer_suffix_kept_when_shorter_produces_wrong_result(self) -> None:
        """wherre→where is kept when herre→hello does not produce 'where'."""
        corrections = [
            ("herre", "hello", BoundaryType.RIGHT),
            ("wherre", "where", BoundaryType.RIGHT),
        ]
        result = resolve_conflicts_for_group(corrections, BoundaryType.RIGHT)
        assert ("wherre", "where", BoundaryType.RIGHT) in result

    def test_shorter_suffix_kept_when_longer_produces_wrong_result(self) -> None:
        """herre→hello is kept when wherre→where would not block it."""
        corrections = [
            ("herre", "hello", BoundaryType.RIGHT),
            ("wherre", "where", BoundaryType.RIGHT),
        ]
        result = resolve_conflicts_for_group(corrections, BoundaryType.RIGHT)
        assert ("herre", "hello", BoundaryType.RIGHT) in result


class TestPrefixBoundaryConflicts:
    """Test conflict resolution for LEFT/NONE/BOTH boundary corrections (prefixes)."""

    def test_shorter_prefix_that_resolves_correctly_blocks_longer(self) -> None:
        """tehir→their is blocked when teh→the produces correct result."""
        corrections = [
            ("teh", "the", BoundaryType.LEFT),
            ("tehir", "their", BoundaryType.LEFT),
        ]
        result = resolve_conflicts_for_group(corrections, BoundaryType.LEFT)
        assert ("tehir", "their", BoundaryType.LEFT) not in result

    def test_shorter_prefix_is_kept_when_it_blocks_longer(self) -> None:
        """teh→the is kept when it blocks tehir→their."""
        corrections = [
            ("teh", "the", BoundaryType.LEFT),
            ("tehir", "their", BoundaryType.LEFT),
        ]
        result = resolve_conflicts_for_group(corrections, BoundaryType.LEFT)
        assert ("teh", "the", BoundaryType.LEFT) in result

    def test_longer_prefix_kept_when_shorter_produces_wrong_result(self) -> None:
        """tehir→their is kept when teh→them does not produce 'their'."""
        corrections = [
            ("teh", "them", BoundaryType.LEFT),
            ("tehir", "their", BoundaryType.LEFT),
        ]
        result = resolve_conflicts_for_group(corrections, BoundaryType.LEFT)
        assert ("tehir", "their", BoundaryType.LEFT) in result

    def test_shorter_prefix_kept_when_longer_produces_wrong_result(self) -> None:
        """teh→them is kept when tehir→their would not block it."""
        corrections = [
            ("teh", "them", BoundaryType.LEFT),
            ("tehir", "their", BoundaryType.LEFT),
        ]
        result = resolve_conflicts_for_group(corrections, BoundaryType.LEFT)
        assert ("teh", "them", BoundaryType.LEFT) in result

    def test_none_boundary_blocks_longer_prefix(self) -> None:
        """NONE boundary: tehir→their is blocked when teh→the produces correct result."""
        corrections = [
            ("teh", "the", BoundaryType.NONE),
            ("tehir", "their", BoundaryType.NONE),
        ]
        result = resolve_conflicts_for_group(corrections, BoundaryType.NONE)
        assert ("tehir", "their", BoundaryType.NONE) not in result

    def test_both_boundary_blocks_longer_prefix(self) -> None:
        """BOTH boundary: tehir→their is blocked when teh→the produces correct result."""
        corrections = [
            ("teh", "the", BoundaryType.BOTH),
            ("tehir", "their", BoundaryType.BOTH),
        ]
        result = resolve_conflicts_for_group(corrections, BoundaryType.BOTH)
        assert ("tehir", "their", BoundaryType.BOTH) not in result


class TestEdgeCases:
    """Test edge cases in conflict resolution."""

    def test_empty_list_returns_empty(self) -> None:
        result = resolve_conflicts_for_group([], BoundaryType.NONE)
        assert result == []

    def test_single_correction_is_kept(self) -> None:
        corrections = [("teh", "the", BoundaryType.NONE)]
        result = resolve_conflicts_for_group(corrections, BoundaryType.NONE)
        assert ("teh", "the", BoundaryType.NONE) in result

    def test_non_overlapping_first_typo_kept(self) -> None:
        """First non-overlapping typo is kept."""
        corrections = [
            ("abc", "xyz", BoundaryType.NONE),
            ("def", "uvw", BoundaryType.NONE),
        ]
        result = resolve_conflicts_for_group(corrections, BoundaryType.NONE)
        assert ("abc", "xyz", BoundaryType.NONE) in result

    def test_non_overlapping_second_typo_kept(self) -> None:
        """Second non-overlapping typo is kept."""
        corrections = [
            ("abc", "xyz", BoundaryType.NONE),
            ("def", "uvw", BoundaryType.NONE),
        ]
        result = resolve_conflicts_for_group(corrections, BoundaryType.NONE)
        assert ("def", "uvw", BoundaryType.NONE) in result

    def test_same_typo_first_correction_kept(self) -> None:
        """First correction for same typo is kept."""
        corrections = [
            ("teh", "the", BoundaryType.NONE),
            ("teh", "tea", BoundaryType.NONE),
        ]
        result = resolve_conflicts_for_group(corrections, BoundaryType.NONE)
        assert ("teh", "the", BoundaryType.NONE) in result

    def test_same_typo_second_correction_kept(self) -> None:
        """Second correction for same typo is kept."""
        corrections = [
            ("teh", "the", BoundaryType.NONE),
            ("teh", "tea", BoundaryType.NONE),
        ]
        result = resolve_conflicts_for_group(corrections, BoundaryType.NONE)
        assert ("teh", "tea", BoundaryType.NONE) in result


class TestConflictChains:
    """Test scenarios with chains of potential conflicts."""

    def test_shortest_in_chain_is_kept(self) -> None:
        """Shortest suffix in a chain of conflicts is kept."""
        corrections = [
            ("er", "or", BoundaryType.RIGHT),
            ("ter", "tor", BoundaryType.RIGHT),
            ("ster", "stor", BoundaryType.RIGHT),
        ]
        result = resolve_conflicts_for_group(corrections, BoundaryType.RIGHT)
        assert ("er", "or", BoundaryType.RIGHT) in result

    def test_middle_in_chain_is_blocked(self) -> None:
        """Middle suffix in a chain of conflicts is blocked."""
        corrections = [
            ("er", "or", BoundaryType.RIGHT),
            ("ter", "tor", BoundaryType.RIGHT),
            ("ster", "stor", BoundaryType.RIGHT),
        ]
        result = resolve_conflicts_for_group(corrections, BoundaryType.RIGHT)
        assert ("ter", "tor", BoundaryType.RIGHT) not in result

    def test_longest_in_chain_is_blocked(self) -> None:
        """Longest suffix in a chain of conflicts is blocked."""
        corrections = [
            ("er", "or", BoundaryType.RIGHT),
            ("ter", "tor", BoundaryType.RIGHT),
            ("ster", "stor", BoundaryType.RIGHT),
        ]
        result = resolve_conflicts_for_group(corrections, BoundaryType.RIGHT)
        assert ("ster", "stor", BoundaryType.RIGHT) not in result

    def test_first_independent_conflict_pair_shorter_kept(self) -> None:
        """First shorter correction in independent conflict pairs is kept."""
        corrections = [
            ("teh", "the", BoundaryType.NONE),
            ("tehir", "their", BoundaryType.NONE),
            ("adn", "and", BoundaryType.NONE),
            ("adnroid", "android", BoundaryType.NONE),
        ]
        result = resolve_conflicts_for_group(corrections, BoundaryType.NONE)
        assert ("teh", "the", BoundaryType.NONE) in result

    def test_first_independent_conflict_pair_longer_blocked(self) -> None:
        """First longer correction in independent conflict pairs is blocked."""
        corrections = [
            ("teh", "the", BoundaryType.NONE),
            ("tehir", "their", BoundaryType.NONE),
            ("adn", "and", BoundaryType.NONE),
            ("adnroid", "android", BoundaryType.NONE),
        ]
        result = resolve_conflicts_for_group(corrections, BoundaryType.NONE)
        assert ("tehir", "their", BoundaryType.NONE) not in result

    def test_second_independent_conflict_pair_shorter_kept(self) -> None:
        """Second shorter correction in independent conflict pairs is kept."""
        corrections = [
            ("teh", "the", BoundaryType.NONE),
            ("tehir", "their", BoundaryType.NONE),
            ("adn", "and", BoundaryType.NONE),
            ("adnroid", "android", BoundaryType.NONE),
        ]
        result = resolve_conflicts_for_group(corrections, BoundaryType.NONE)
        assert ("adn", "and", BoundaryType.NONE) in result

    def test_second_independent_conflict_pair_longer_blocked(self) -> None:
        """Second longer correction in independent conflict pairs is blocked."""
        corrections = [
            ("teh", "the", BoundaryType.NONE),
            ("tehir", "their", BoundaryType.NONE),
            ("adn", "and", BoundaryType.NONE),
            ("adnroid", "android", BoundaryType.NONE),
        ]
        result = resolve_conflicts_for_group(corrections, BoundaryType.NONE)
        assert ("adnroid", "android", BoundaryType.NONE) not in result


class TestBehaviorConsistency:
    """Test that behavior is consistent across different scenarios."""

    def test_shorter_kept_regardless_of_input_order(self) -> None:
        """Shorter correction is kept regardless of whether it comes first or last."""
        corrections_normal = [
            ("teh", "the", BoundaryType.NONE),
            ("tehir", "their", BoundaryType.NONE),
        ]
        corrections_reversed = [
            ("tehir", "their", BoundaryType.NONE),
            ("teh", "the", BoundaryType.NONE),
        ]

        result_normal = resolve_conflicts_for_group(corrections_normal, BoundaryType.NONE)
        result_reversed = resolve_conflicts_for_group(corrections_reversed, BoundaryType.NONE)

        assert ("teh", "the", BoundaryType.NONE) in result_normal
        assert ("teh", "the", BoundaryType.NONE) in result_reversed

    def test_longer_blocked_regardless_of_input_order(self) -> None:
        """Longer correction is blocked regardless of whether it comes first or last."""
        corrections_normal = [
            ("teh", "the", BoundaryType.NONE),
            ("tehir", "their", BoundaryType.NONE),
        ]
        corrections_reversed = [
            ("tehir", "their", BoundaryType.NONE),
            ("teh", "the", BoundaryType.NONE),
        ]

        result_normal = resolve_conflicts_for_group(corrections_normal, BoundaryType.NONE)
        result_reversed = resolve_conflicts_for_group(corrections_reversed, BoundaryType.NONE)

        assert ("tehir", "their", BoundaryType.NONE) not in result_normal
        assert ("tehir", "their", BoundaryType.NONE) not in result_reversed

    def test_first_non_conflicting_correction_preserved(self) -> None:
        """First non-conflicting correction is preserved."""
        corrections = [
            ("abc", "xyz", BoundaryType.NONE),
            ("teh", "the", BoundaryType.NONE),
            ("tehir", "their", BoundaryType.NONE),
        ]
        result = resolve_conflicts_for_group(corrections, BoundaryType.NONE)
        assert ("abc", "xyz", BoundaryType.NONE) in result

    def test_last_non_conflicting_correction_preserved(self) -> None:
        """Last non-conflicting correction is preserved."""
        corrections = [
            ("teh", "the", BoundaryType.NONE),
            ("tehir", "their", BoundaryType.NONE),
            ("def", "uvw", BoundaryType.NONE),
        ]
        result = resolve_conflicts_for_group(corrections, BoundaryType.NONE)
        assert ("def", "uvw", BoundaryType.NONE) in result

    def test_shorter_in_middle_of_non_conflicting_kept(self) -> None:
        """Shorter correction between non-conflicting corrections is kept."""
        corrections = [
            ("abc", "xyz", BoundaryType.NONE),
            ("teh", "the", BoundaryType.NONE),
            ("tehir", "their", BoundaryType.NONE),
            ("def", "uvw", BoundaryType.NONE),
        ]
        result = resolve_conflicts_for_group(corrections, BoundaryType.NONE)
        assert ("teh", "the", BoundaryType.NONE) in result

    def test_longer_in_middle_of_non_conflicting_blocked(self) -> None:
        """Longer correction between non-conflicting corrections is blocked."""
        corrections = [
            ("abc", "xyz", BoundaryType.NONE),
            ("teh", "the", BoundaryType.NONE),
            ("tehir", "their", BoundaryType.NONE),
            ("def", "uvw", BoundaryType.NONE),
        ]
        result = resolve_conflicts_for_group(corrections, BoundaryType.NONE)
        assert ("tehir", "their", BoundaryType.NONE) not in result
