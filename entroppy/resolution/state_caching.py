"""Caching helpers for DictionaryState optimization."""

from typing import TYPE_CHECKING

from entroppy.core import BoundaryType
from entroppy.core.boundaries import determine_boundaries
from entroppy.resolution.false_trigger_check import _check_false_trigger_with_details

if TYPE_CHECKING:
    from entroppy.core.boundaries.types import BoundaryIndex


class StateCaching:
    """Caching helpers for DictionaryState to optimize CandidateSelection pass."""

    def __init__(self) -> None:
        """Initialize caches."""
        # Boundary cache: typo -> BoundaryType (never invalidated, typo properties immutable)
        self._boundary_cache: dict[str, BoundaryType] = {}
        # Pattern coverage cache: typo -> bool (invalidated when patterns added/removed)
        self._pattern_coverage_cache: dict[str, bool] = {}
        # False trigger cache: (typo, boundary) -> (bool, dict) (cleared at start of each iteration)
        self._false_trigger_cache: dict[
            tuple[str, BoundaryType], tuple[bool, dict[str, bool | str | None]]
        ] = {}
        # Batch false trigger results: typo -> dict of batch check results
        # (cleared at start of each iteration)
        self._batch_false_trigger_results: dict[str, dict[str, bool]] = {}
        # Track uncovered typos for early termination
        self._uncovered_typos: set[str] = set()

    def get_cached_boundary(
        self,
        typo: str,
        validation_index: "BoundaryIndex",
        source_index: "BoundaryIndex",
    ) -> BoundaryType:
        """Get boundary for typo, using cache if available.

        Args:
            typo: The typo string
            validation_index: Boundary index for validation set
            source_index: Boundary index for source words

        Returns:
            BoundaryType for the typo
        """
        if typo in self._boundary_cache:
            return self._boundary_cache[typo]

        boundary = determine_boundaries(typo, validation_index, source_index)
        self._boundary_cache[typo] = boundary
        return boundary

    def get_cached_false_trigger(
        self,
        typo: str,
        boundary: BoundaryType,
        validation_index: "BoundaryIndex",
        source_index: "BoundaryIndex",
        target_word: str | None = None,
    ) -> tuple[bool, dict[str, bool | str | None]]:
        """Get false trigger check result, using cache if available.

        Args:
            typo: The typo string
            boundary: The boundary type to check
            validation_index: Boundary index for validation set
            source_index: Boundary index for source words
            target_word: Optional target word to check against

        Returns:
            Tuple of (would_cause_false_trigger, details_dict)
        """
        cache_key = (typo, boundary)
        if cache_key in self._false_trigger_cache:
            return self._false_trigger_cache[cache_key]

        # Use batch results if available
        batch_results = (
            self._batch_false_trigger_results if self._batch_false_trigger_results else None
        )
        would_cause, details = _check_false_trigger_with_details(
            typo,
            boundary,
            validation_index,
            source_index,
            target_word=target_word,
            batch_results=batch_results,
        )
        self._false_trigger_cache[cache_key] = (would_cause, details)
        return would_cause, details

    def set_batch_false_trigger_results(self, batch_results: dict[str, dict[str, bool]]) -> None:
        """Set batch false trigger results for use in individual checks.

        Args:
            batch_results: Dict mapping typo -> dict of batch check results
        """
        self._batch_false_trigger_results = batch_results

    def clear_false_trigger_cache(self) -> None:
        """Clear false trigger cache and batch results (called at start of each iteration)."""
        self._false_trigger_cache.clear()
        self._batch_false_trigger_results.clear()

    def invalidate_pattern_coverage_cache(self) -> None:
        """Invalidate pattern coverage cache (called when patterns change)."""
        self._pattern_coverage_cache.clear()

    def invalidate_pattern_coverage_for_typo(self, typo: str) -> None:
        """Invalidate pattern coverage cache for a specific typo.

        Args:
            typo: The typo to invalidate
        """
        self._pattern_coverage_cache.pop(typo, None)

    def is_typo_covered_by_pattern(
        self, typo: str, active_patterns: set[tuple[str, str, BoundaryType]]
    ) -> bool:
        """Check if typo is covered by patterns only.

        Args:
            typo: The typo to check
            active_patterns: Set of active patterns

        Returns:
            True if the typo is covered by any pattern
        """
        for pattern_typo, _, _ in active_patterns:
            if pattern_typo == typo:  # For now, exact match
                return True
        return False

    def is_typo_covered(
        self,
        typo: str,
        coverage_map: dict[str, set[tuple[str, str, BoundaryType]]],
        active_patterns: set[tuple[str, str, BoundaryType]],
    ) -> bool:
        """Check if a raw typo is covered by active corrections or patterns.

        Args:
            typo: The typo to check
            coverage_map: Map of typo -> set of corrections
            active_patterns: Set of active patterns

        Returns:
            True if the typo is covered by any active correction or pattern
        """
        # Check cache first
        cache = self._pattern_coverage_cache
        if typo in cache:
            return cache[typo]

        # Check if any active correction covers this typo (fast: O(1))
        if typo in coverage_map and coverage_map[typo]:
            cache[typo] = True
            return True

        # Check if any pattern covers this typo (slow: O(P) where P=2000-2300)
        # For now, exact match (patterns will be enhanced in PatternGeneralizationPass)
        for pattern_typo, _, _ in active_patterns:
            if pattern_typo == typo:
                cache[typo] = True
                return True

        # Not covered
        cache[typo] = False
        return False

    def get_uncovered_typos(self) -> set[str]:
        """Get uncovered typos set (for CandidateSelection pass optimization).

        Returns:
            Set of uncovered typos
        """
        return self._uncovered_typos
