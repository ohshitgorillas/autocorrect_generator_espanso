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
from entroppy.resolution.platform_conflicts.conflict_processing import (
    process_conflict_combinations,
)
from entroppy.resolution.platform_conflicts.detection import is_substring
from entroppy.resolution.platform_conflicts.formatting import (
    FormattingContext,
    _format_correction_worker,
    init_formatting_worker,
)
from entroppy.resolution.platform_conflicts.logging import log_platform_substring_conflict
from entroppy.resolution.platform_conflicts.suffix_array_helpers import (
    build_suffix_array,
    find_substring_matches,
)
from entroppy.resolution.solver import Pass
from entroppy.resolution.state import RejectionReason

if TYPE_CHECKING:
    from pysuffixarray.core import SuffixArray

    from entroppy.resolution.state import DictionaryState


class PlatformSubstringConflictPass(Pass):
    """Detects and removes cross-boundary substring conflicts.

    For platforms that format boundaries as part of the typo string (like QMK),
    this pass checks if formatted strings are substrings of each other and
    removes duplicates based on platform matching direction.

    For QMK (RTL):
    - Formats typos with boundary markers (e.g., "aemr" -> "aemr", ":aemr" -> ":aemr")
    - Checks if formatted strings are substrings (QMK compiler rejects substring
      relationships)
    - Prefers less restrictive boundaries (NONE > LEFT/RIGHT > BOTH) when both
      passed false trigger checks
    - Removes the more restrictive one to prevent compiler errors while keeping
      the more useful correction

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
            formatted_to_corrections, match_direction, state
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
        use_parallel = self.context.jobs > 1 and len(all_corrections) >= 100

        if use_parallel:
            formatting_context = FormattingContext(is_qmk=is_qmk)

            with Pool(
                processes=self.context.jobs,
                initializer=init_formatting_worker,
                initargs=(formatting_context,),
            ) as pool:
                if self.context.verbose:
                    results_iter = pool.imap(_format_correction_worker, all_corrections)
                    results: Any = tqdm(
                        results_iter,
                        desc=f"    {self.name}",
                        total=len(all_corrections),
                        unit="correction",
                        leave=False,
                    )
                else:
                    results = pool.imap(_format_correction_worker, all_corrections)
                formatted_results = list(results)
        else:
            if self.context.verbose:
                corrections_iter: Any = tqdm(
                    all_corrections,
                    desc=f"    {self.name}",
                    unit="correction",
                    leave=False,
                )
            else:
                corrections_iter = all_corrections

            formatted_results = [
                (c, self._format_typo_for_platform(c[0], c[2])) for c in corrections_iter
            ]

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

    def _process_typo_conflicts(
        self,
        i: int,
        formatted_typo: str,
        corrections_for_typo: list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]],
        formatted_typos: list[str],
        formatted_to_corrections: dict[
            str, list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]]
        ],
        match_direction: MatchDirection,
        processed_pairs: set[frozenset[tuple[str, str, BoundaryType]]],
        corrections_to_remove_set: set[tuple[str, str, BoundaryType]],
        all_corrections_to_remove: list[tuple[tuple[str, str, BoundaryType], str]],
        all_conflict_pairs: dict[tuple[str, str, BoundaryType], tuple[str, str, BoundaryType]],
        sa: "SuffixArray",
        delimiter: str,
        state: "DictionaryState",
    ) -> None:
        """Process conflicts for a single formatted typo.

        Args:
            i: Index of current typo
            formatted_typo: Current formatted typo
            corrections_for_typo: Corrections for current typo
            formatted_typos: List of all formatted typos
            formatted_to_corrections: Dict mapping typo to corrections
            match_direction: Platform match direction
            processed_pairs: Set of processed pairs
            corrections_to_remove_set: Set of corrections to remove
            all_corrections_to_remove: List to append removals
            all_conflict_pairs: Dict to update with conflict pairs
            sa: Suffix array
            delimiter: Delimiter used in concatenated string
            state: Dictionary state
        """
        # Find which typos contain this as a substring using suffix array
        matched_typo_indices = find_substring_matches(
            sa, formatted_typo, formatted_typos, delimiter
        )

        # Check each match for conflicts
        for match_idx in matched_typo_indices:
            if match_idx == i:
                continue  # Skip self

            matched_typo = formatted_typos[match_idx]
            matched_corrections = formatted_to_corrections[matched_typo]

            # Determine which is shorter/longer for conflict resolution
            if len(formatted_typo) < len(matched_typo):
                shorter_typo = formatted_typo
                longer_typo = matched_typo
                shorter_corrections = corrections_for_typo
                longer_corrections = matched_corrections
            elif len(formatted_typo) > len(matched_typo):
                shorter_typo = matched_typo
                longer_typo = formatted_typo
                shorter_corrections = matched_corrections
                longer_corrections = corrections_for_typo
            else:
                # Same length - check if they're actually substrings
                if formatted_typo != matched_typo:
                    # Different strings of same length can't be substrings
                    continue
                # Same string - skip (duplicate)
                continue

            # Verify substring relationship
            if not is_substring(shorter_typo, longer_typo):
                continue

            # Process all combinations of corrections
            process_conflict_combinations(
                shorter_typo,
                longer_typo,
                shorter_corrections,
                longer_corrections,
                match_direction,
                processed_pairs,
                corrections_to_remove_set,
                all_corrections_to_remove,
                all_conflict_pairs,
                self.context.validation_index,
                self.context.source_index,
                state.debug_words,
                state.debug_typo_matcher,
            )

    def _detect_conflicts(
        self,
        formatted_to_corrections: dict[
            str, list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]]
        ],
        match_direction: MatchDirection,
        state: "DictionaryState",
    ) -> tuple[
        list[tuple[tuple[str, str, BoundaryType], str]],
        dict[tuple[str, str, BoundaryType], tuple[str, str, BoundaryType]],
    ]:
        """Detect conflicts using suffix array for efficient substring queries.

        This uses:
        - Suffix array to enable O(log N + M) substring queries instead of O(N²)
        - Build suffix array once from all formatted typos
        - Query for each typo to find all substring matches efficiently

        Args:
            formatted_to_corrections: Dict mapping formatted_typo ->
                list of (correction, typo, boundary)
            match_direction: Platform match direction
            state: The dictionary state (for debug words/typos)

        Returns:
            Tuple of:
            - corrections_to_remove: List of (correction, reason) tuples
            - conflict_pairs: Dict mapping removed_correction -> conflicting_correction
        """
        all_corrections_to_remove: list[tuple[tuple[str, str, BoundaryType], str]] = []
        all_conflict_pairs: dict[tuple[str, str, BoundaryType], tuple[str, str, BoundaryType]] = {}
        processed_pairs: set[frozenset[tuple[str, str, BoundaryType]]] = set()

        # Track corrections already marked for removal (early termination optimization)
        corrections_to_remove_set: set[tuple[str, str, BoundaryType]] = set()

        # Build suffix array from all formatted typos
        formatted_typos = list(formatted_to_corrections.keys())
        if not formatted_typos:
            return all_corrections_to_remove, all_conflict_pairs

        # Build suffix array
        sa, delimiter = build_suffix_array(formatted_typos, self.context.verbose, self.name)

        # Setup progress bar
        if self.context.verbose:
            progress_bar: Any = tqdm(
                total=len(formatted_typos),
                desc=f"    {self.name} (checking conflicts)",
                unit="typo",
                leave=False,
            )
        else:
            progress_bar = None

        # Process each formatted typo
        for i, formatted_typo in enumerate(formatted_typos):
            if progress_bar is not None:
                progress_bar.update(1)

            corrections_for_typo = formatted_to_corrections[formatted_typo]

            # Process conflicts for this typo
            self._process_typo_conflicts(
                i,
                formatted_typo,
                corrections_for_typo,
                formatted_typos,
                formatted_to_corrections,
                match_direction,
                processed_pairs,
                corrections_to_remove_set,
                all_corrections_to_remove,
                all_conflict_pairs,
                sa,
                delimiter,
                state,
            )

        if progress_bar is not None:
            progress_bar.close()

        return all_corrections_to_remove, all_conflict_pairs

    def _remove_single_conflict(
        self,
        state: "DictionaryState",
        correction: tuple[str, str, BoundaryType],
        reason: str,
        conflict_pairs: dict[tuple[str, str, BoundaryType], tuple[str, str, BoundaryType]],
        correction_to_formatted: dict[tuple[str, str, BoundaryType], str],
    ) -> None:
        """Remove a single conflicting correction and perform debug logging.

        Args:
            state: The dictionary state to modify
            correction: The correction to remove
            reason: Reason for removal
            conflict_pairs: Dict mapping removed_correction -> conflicting_correction
            correction_to_formatted: Dict mapping correction -> formatted_typo
        """
        typo, word, boundary = correction

        # Get conflicting correction and formatted strings
        conflicting_correction = conflict_pairs.get(correction)
        formatted_removed = correction_to_formatted.get(correction, "")
        formatted_conflicting = (
            correction_to_formatted.get(conflicting_correction, "")
            if conflicting_correction
            else ""
        )

        # Debug logging
        if conflicting_correction:
            log_platform_substring_conflict(
                correction,
                conflicting_correction,
                formatted_removed,
                formatted_conflicting,
                reason,
                state.debug_words,
                state.debug_typo_matcher,
            )

        # Remove from active set
        if correction in state.active_corrections:
            state.remove_correction(typo, word, boundary, self.name, reason)
        elif correction in state.active_patterns:
            state.remove_pattern(typo, word, boundary, self.name, reason)

        # Add to graveyard
        state.add_to_graveyard(
            typo,
            word,
            boundary,
            RejectionReason.PLATFORM_CONSTRAINT,
            reason,
            pass_name=self.name,
        )

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
            self._remove_single_conflict(
                state, correction, reason, conflict_pairs, correction_to_formatted
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
