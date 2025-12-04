"""Platform-specific cross-boundary substring conflict detection.

This pass detects substring conflicts that occur when the same typo text
appears with different boundaries, which can cause issues in platform output:

- QMK (RTL): Formatted strings like "aemr" and ":aemr" are substrings of
  each other, causing compiler errors
- Espanso (LTR): Same typo with different boundaries can cause runtime
  conflicts depending on matching order

This pass runs after ConflictRemovalPass to catch cross-boundary conflicts
that weren't detected within boundary groups.
"""

from collections import defaultdict
from multiprocessing import Pool
from typing import TYPE_CHECKING, Any

from tqdm import tqdm

from entroppy.core.boundaries import BoundaryType
from entroppy.core.types import MatchDirection
from entroppy.platforms.qmk.formatting import format_boundary_markers
from entroppy.resolution.platform_substring_conflict_logging import log_platform_substring_conflict
from entroppy.resolution.solver import Pass
from entroppy.resolution.state import RejectionReason

if TYPE_CHECKING:
    from entroppy.resolution.solver import PassContext
    from entroppy.resolution.state import DictionaryState

# Boundary priority mapping: more restrictive boundaries have higher priority
# Used to determine which correction to keep when resolving conflicts
BOUNDARY_PRIORITY = {
    BoundaryType.NONE: 0,
    BoundaryType.LEFT: 1,
    BoundaryType.RIGHT: 1,
    BoundaryType.BOTH: 2,
}


def _format_correction_worker(
    item: tuple[tuple[str, str, BoundaryType], bool],
) -> tuple[tuple[str, str, BoundaryType], str]:
    """Worker function to format a single correction.

    Args:
        item: Tuple of (correction, is_qmk) where correction is (typo, word, boundary)
              and is_qmk indicates if platform is QMK

    Returns:
        Tuple of (correction, formatted_typo)
    """
    correction, is_qmk = item
    typo, _word, boundary = correction

    if is_qmk:
        formatted_typo = format_boundary_markers(typo, boundary)
    else:
        # For non-QMK platforms, boundaries are handled separately
        formatted_typo = typo

    return correction, formatted_typo


class PlatformSubstringConflictPass(Pass):
    """Detects and removes cross-boundary substring conflicts.

    For platforms that format boundaries as part of the typo string (like QMK),
    this pass checks if formatted strings are substrings of each other and
    removes duplicates based on platform matching direction.

    For QMK (RTL):
    - Formats typos with boundary markers (e.g., "aemr" -> "aemr", ":aemr" -> ":aemr")
    - Checks if formatted strings are substrings
    - With RTL matching, the longer formatted string would match first
    - Removes the shorter one to prevent compiler errors

    For Espanso (LTR):
    - Checks if same typo text exists with different boundaries
    - With LTR matching, boundaries are handled separately in YAML
    - Still checks for substring relationships in the core typo text
    - Removes duplicates preferring less restrictive boundaries
    """

    @property
    def name(self) -> str:
        """Return the name of this pass."""
        return "PlatformSubstringConflicts"

    def run(self, state: "DictionaryState") -> None:
        """Run the platform substring conflict pass.

        Args:
            state: The dictionary state to modify
        """
        if not self.context.platform:
            # No platform specified, skip
            return

        # Get platform constraints
        constraints = self.context.platform.get_constraints()
        match_direction = constraints.match_direction

        # Combine active corrections and patterns
        all_corrections = list(state.active_corrections) + list(state.active_patterns)

        if not all_corrections:
            return

        # Phase 1: Format corrections (with parallelization)
        formatted_to_corrections, correction_to_formatted = self._format_corrections_parallel(
            all_corrections
        )

        # Phase 2: Detect conflicts (keeping original nested loop logic)
        corrections_to_remove, conflict_pairs = self._detect_conflicts(
            formatted_to_corrections, match_direction
        )

        # Phase 3: Remove conflicts and log (using stored conflict pairs)
        self._remove_conflicts_and_log(
            state, corrections_to_remove, conflict_pairs, correction_to_formatted
        )

    def _format_corrections_parallel(
        self, all_corrections: list[tuple[str, str, BoundaryType]]
    ) -> tuple[
        dict[str, list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]]],
        dict[tuple[str, str, BoundaryType], str],
    ]:
        """Format corrections in parallel and build lookup structures.

        Args:
            all_corrections: List of all corrections to format

        Returns:
            Tuple of:
            - formatted_to_corrections: Dict mapping formatted_typo ->
              list of (correction, typo, boundary)
            - correction_to_formatted: Dict mapping correction -> formatted_typo
        """
        is_qmk = self.context.platform.__class__.__name__ == "QMKBackend"

        # Determine if we should use parallel processing
        use_parallel = self.context.jobs > 1 and len(all_corrections) >= 100

        if use_parallel:
            # Prepare tasks for parallel processing
            tasks = [(correction, is_qmk) for correction in all_corrections]

            # Process in parallel
            with Pool(processes=self.context.jobs) as pool:
                if self.context.verbose:
                    results_iter = pool.imap(_format_correction_worker, tasks)
                    results: Any = tqdm(
                        results_iter,
                        desc=f"    {self.name}",
                        total=len(tasks),
                        unit="correction",
                        leave=False,
                    )
                else:
                    results = pool.imap(_format_correction_worker, tasks)

                formatted_results = list(results)
        else:
            # Sequential processing
            if self.context.verbose:
                corrections_iter: Any = tqdm(
                    all_corrections,
                    desc=f"    {self.name}",
                    unit="correction",
                    leave=False,
                )
            else:
                corrections_iter = all_corrections

            formatted_results = []
            for correction in corrections_iter:
                typo, _word, boundary = correction
                formatted_typo = self._format_typo_for_platform(typo, boundary)
                formatted_results.append((correction, formatted_typo))

        # Build lookup structures
        formatted_to_corrections: dict[
            str, list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]]
        ] = defaultdict(list)
        correction_to_formatted: dict[tuple[str, str, BoundaryType], str] = {}

        for correction, formatted_typo in formatted_results:
            typo, _word, boundary = correction
            formatted_to_corrections[formatted_typo].append((correction, typo, boundary))
            correction_to_formatted[correction] = formatted_typo

        return formatted_to_corrections, correction_to_formatted

    def _detect_conflicts(
        self,
        formatted_to_corrections: dict[
            str, list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]]
        ],
        match_direction: MatchDirection,
    ) -> tuple[
        list[tuple[tuple[str, str, BoundaryType], str]],
        dict[tuple[str, str, BoundaryType], tuple[str, str, BoundaryType]],
    ]:
        """Detect conflicts using TypoIndex-style algorithm (same logic as original, optimized).

        This uses the same conflict detection logic as the original nested loop approach,
        but processes in reverse order (for each longer typo, check all shorter ones)
        for better performance. Results are identical to the original.

        Args:
            formatted_to_corrections: Dict mapping formatted_typo ->
                list of (correction, typo, boundary)
            match_direction: Platform match direction

        Returns:
            Tuple of:
            - corrections_to_remove: List of (correction, reason) tuples
            - conflict_pairs: Dict mapping removed_correction -> conflicting_correction
        """
        corrections_to_remove = []
        conflict_pairs: dict[tuple[str, str, BoundaryType], tuple[str, str, BoundaryType]] = {}
        processed_pairs = set()

        # Sort formatted typos by length (shortest first) - O(n log n)
        sorted_formatted = sorted(formatted_to_corrections.keys(), key=len)

        # Track shorter formatted typos we've seen: formatted_typo -> list of corrections
        # This allows O(1) lookup instead of O(n) linear search
        shorter_formatted: dict[
            str, list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]]
        ] = {}

        if self.context.verbose:
            formatted_iter: Any = tqdm(
                sorted_formatted,
                desc=f"    {self.name} (checking conflicts)",
                unit="typo",
                leave=False,
            )
        else:
            formatted_iter = sorted_formatted

        # TypoIndex-style: for each longer formatted typo, check if it contains any shorter one
        # This is equivalent to the original nested loop but processes in reverse order
        for formatted_typo in formatted_iter:
            corrections_for_typo = formatted_to_corrections[formatted_typo]

            # Check if this formatted typo contains any shorter formatted typo as substring
            # Check all shorter formatted typos we've seen so far
            for shorter_formatted_typo, shorter_corrections in shorter_formatted.items():
                # Check if shorter is a substring of current (same check as original)
                if self._is_substring(shorter_formatted_typo, formatted_typo):
                    # Check all combinations of corrections (same as original)
                    for correction1, _, boundary1 in shorter_corrections:
                        for correction2, _, boundary2 in corrections_for_typo:
                            # Use frozenset to create unique pair identifier (same as original)
                            pair_id = frozenset([correction1, correction2])
                            if pair_id in processed_pairs:
                                continue
                            processed_pairs.add(pair_id)

                            # Determine which one to remove based on match direction (same logic)
                            _, word1, _ = correction1
                            _, word2, _ = correction2

                            if self._should_remove_shorter(
                                match_direction,
                                word1,
                                word2,
                                boundary1,
                                boundary2,
                            ):
                                # Remove the shorter formatted one (formatted1)
                                reason = (
                                    f"Cross-boundary substring conflict: "
                                    f"'{shorter_formatted_typo}' is substring of '{formatted_typo}'"
                                )
                                corrections_to_remove.append((correction1, reason))
                                conflict_pairs[correction1] = correction2
                            else:
                                # Remove the longer formatted one (formatted2)
                                reason = (
                                    f"Cross-boundary substring conflict: '{formatted_typo}' "
                                    f"contains substring '{shorter_formatted_typo}'"
                                )
                                corrections_to_remove.append((correction2, reason))
                                conflict_pairs[correction2] = correction1

            # Add to shorter_formatted for future checks (only if we've processed it)
            # This is safe because we process in length order, so all shorter ones are already added
            shorter_formatted[formatted_typo] = corrections_for_typo

        return corrections_to_remove, conflict_pairs

    def _remove_conflicts_and_log(
        self,
        state: "DictionaryState",
        corrections_to_remove: list[tuple[tuple[str, str, BoundaryType], str]],
        conflict_pairs: dict[tuple[str, str, BoundaryType], tuple[str, str, BoundaryType]],
        correction_to_formatted: dict[tuple[str, str, BoundaryType], str],
    ) -> None:
        """Remove conflicting corrections and perform debug logging.

        Args:
            state: The dictionary state to modify
            corrections_to_remove: List of (correction, reason) tuples
            conflict_pairs: Dict mapping removed_correction -> conflicting_correction
            correction_to_formatted: Dict mapping correction -> formatted_typo
        """
        # Deduplicate corrections to remove
        seen = set()
        for correction, reason in corrections_to_remove:
            if correction in seen:
                continue
            seen.add(correction)

            typo, word, boundary = correction

            # Get conflicting correction and formatted strings from stored pairs
            conflicting_correction = conflict_pairs.get(correction)
            formatted_removed = correction_to_formatted.get(correction, "")
            formatted_conflicting = (
                correction_to_formatted.get(conflicting_correction, "")
                if conflicting_correction
                else None
            )

            # Debug logging
            if conflicting_correction:
                log_platform_substring_conflict(
                    correction,
                    conflicting_correction,
                    formatted_removed,
                    formatted_conflicting or "",
                    reason,
                    state.debug_words,
                    state.debug_typo_matcher,
                )

            # Remove from active set
            if correction in state.active_corrections:
                state.remove_correction(typo, word, boundary, self.name, reason)
            elif correction in state.active_patterns:
                state.remove_pattern(typo, word, boundary, self.name, reason)

            # pylint: disable=duplicate-code
            # Intentional duplication: Same graveyard pattern used in multiple passes
            # (platform_constraints.py, platform_substring_conflicts.py) to ensure
            # consistent rejection handling across all platform-specific passes.
            state.add_to_graveyard(
                typo,
                word,
                boundary,
                RejectionReason.PLATFORM_CONSTRAINT,
                reason,
            )

    def _format_typo_for_platform(self, typo: str, boundary) -> str:
        """Format typo with platform-specific boundary markers.

        For QMK, boundaries are part of the formatted string (colon notation).
        For Espanso, boundaries are separate YAML fields, but we still need to
        check for substring conflicts in the core typo text.

        Args:
            typo: The core typo string
            boundary: The boundary type

        Returns:
            Formatted typo string with boundary markers (for QMK) or core typo (for others)
        """
        # For QMK, use colon notation (boundaries are part of the string)
        if self.context.platform.__class__.__name__ == "QMKBackend":
            return format_boundary_markers(typo, boundary)

        # For Espanso and other platforms, boundaries are handled separately
        # in output format, so we just use the core typo for substring checking
        # The same core typo with different boundaries are different matches
        # but we still check if core typos are substrings of each other
        return typo

    def _is_substring(self, shorter: str, longer: str) -> bool:
        """Check if shorter is a substring of longer.

        Args:
            shorter: The shorter string
            longer: The longer string

        Returns:
            True if shorter is a substring of longer
        """
        return shorter in longer and shorter != longer

    def _should_remove_shorter(
        self,
        match_direction: MatchDirection,
        shorter_word: str,
        longer_word: str,
        shorter_boundary,
        longer_boundary,
    ) -> bool:
        """Determine if the shorter formatted typo should be removed.

        Args:
            match_direction: Platform match direction
            shorter_word: Word for shorter typo
            longer_word: Word for longer typo
            shorter_boundary: Boundary type for shorter typo
            longer_boundary: Boundary type for longer typo

        Returns:
            True if shorter should be removed, False if longer should be removed
        """
        # If they map to the same word, prefer the more restrictive boundary
        # (keeps the one that's less likely to cause false triggers)
        if shorter_word == longer_word:
            shorter_priority = BOUNDARY_PRIORITY.get(shorter_boundary, 0)
            longer_priority = BOUNDARY_PRIORITY.get(longer_boundary, 0)

            if longer_priority > shorter_priority:
                return True  # Remove shorter (less restrictive)
            return False  # Remove longer (less restrictive)

        # For RTL (QMK): QMK's compiler rejects ANY substring relationship
        # We prefer to keep the more restrictive boundary
        # (longer formatted usually means more restrictive)
        if match_direction == MatchDirection.RIGHT_TO_LEFT:
            # Keep longer (more restrictive), remove shorter
            return True  # Remove shorter

        # For LTR (Espanso): shorter would match first, so longer never triggers
        # But boundaries are handled separately in YAML, so this is less critical
        # Still, prefer more restrictive boundary
        shorter_priority = BOUNDARY_PRIORITY.get(shorter_boundary, 0)
        longer_priority = BOUNDARY_PRIORITY.get(longer_boundary, 0)

        if longer_priority > shorter_priority:
            return True  # Remove shorter (less restrictive)
        return False  # Remove longer (less restrictive)
