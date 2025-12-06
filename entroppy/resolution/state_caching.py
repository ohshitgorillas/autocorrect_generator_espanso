"""Caching helpers for DictionaryState optimization."""

from typing import TYPE_CHECKING

from entroppy.core import BoundaryType

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

        # Import here to avoid circular dependency
        from entroppy.core.boundaries import determine_boundaries  # noqa: PLC0415

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

        # Import here to avoid circular dependency
        from entroppy.resolution.false_trigger_check import (  # noqa: PLC0415
            _check_false_trigger_with_details,
        )

        would_cause, details = _check_false_trigger_with_details(
            typo, boundary, validation_index, source_index, target_word=target_word
        )
        self._false_trigger_cache[cache_key] = (would_cause, details)
        return would_cause, details

    def clear_false_trigger_cache(self) -> None:
        """Clear false trigger cache (called at start of each iteration)."""
        self._false_trigger_cache.clear()

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
