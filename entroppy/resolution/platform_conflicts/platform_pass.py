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

from typing import TYPE_CHECKING, Any

from tqdm import tqdm

from entroppy.core.boundaries import BoundaryType
from entroppy.core.types import MatchDirection
from entroppy.platforms.qmk.formatting import format_boundary_markers
from entroppy.resolution.platform_conflicts.formatting_helpers import (
    format_corrections_parallel,
)
from entroppy.resolution.platform_conflicts.logging import log_platform_substring_conflict
from entroppy.resolution.platform_conflicts.resolution import should_remove_shorter
from entroppy.resolution.platform_conflicts.suffix_array_helpers import (
    build_suffix_array,
    find_substring_matches,
)
from entroppy.resolution.platform_conflicts.utils import (
    bulk_remove_losing_formatted_typos,
    determine_shorter_longer_formatted_typo,
)
from entroppy.resolution.solver import Pass
from entroppy.resolution.state import RejectionReason
from entroppy.utils.suffix_array import SubstringIndex

if TYPE_CHECKING:
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

        # Phase 2: Detect conflicts (suffix array is already integrated in _detect_conflicts)
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
        return format_corrections_parallel(
            all_corrections,
            is_qmk,
            self.context.jobs,
            self.context.verbose,
            self.name,
            self._format_typo_for_platform,
        )

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
        processed_formatted_pairs: set[frozenset[str]],
        formatted_typos_to_remove: set[str],
        losing_to_winning_formatted: dict[str, str],
        sa: SubstringIndex,
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
            processed_formatted_pairs: Set of processed formatted typo pairs
            formatted_typos_to_remove: Set of formatted typos to remove (in-place)
            losing_to_winning_formatted: Dict mapping losing -> winning formatted typo
            sa: Suffix array
            state: Dictionary state
        """
        # Find which typos contain this as a substring using suffix array
        matched_typo_indices = find_substring_matches(sa, formatted_typo)

        # Check each match for conflicts
        for match_idx in matched_typo_indices:
            if match_idx == i:
                continue  # Skip self

            matched_typo = formatted_typos[match_idx]

            # Skip if either formatted typo is already marked for removal
            if (
                formatted_typo in formatted_typos_to_remove
                or matched_typo in formatted_typos_to_remove
            ):
                continue

            # Check if we've already processed this formatted typo pair
            pair_key = frozenset({formatted_typo, matched_typo})
            if pair_key in processed_formatted_pairs:
                continue
            processed_formatted_pairs.add(pair_key)

            # Determine which is shorter/longer and validate substring relationship
            result = determine_shorter_longer_formatted_typo(
                formatted_typo,
                matched_typo,
                corrections_for_typo,
                formatted_to_corrections[matched_typo],
            )
            if result is None:
                continue
            shorter_typo, longer_typo, shorter_corrections, longer_corrections = result

            # Sample one correction from each formatted typo to make decision
            # This determines which formatted typo should be removed (all corrections with it)
            if not shorter_corrections or not longer_corrections:
                continue

            shorter_correction, _, shorter_boundary = shorter_corrections[0]
            longer_correction, _, longer_boundary = longer_corrections[0]
            shorter_typo_core, shorter_word, _ = shorter_correction
            longer_typo_core, longer_word, _ = longer_correction

            # Use existing resolution logic to decide which formatted typo to remove
            remove_shorter = should_remove_shorter(
                match_direction,
                shorter_typo_core,
                longer_typo_core,
                shorter_word,
                longer_word,
                shorter_boundary,
                longer_boundary,
                self.context.validation_index,
                self.context.source_index,
                state.debug_words,
                state.debug_typo_matcher,
            )

            # Mark the losing formatted typo for removal
            if remove_shorter:
                formatted_typos_to_remove.add(shorter_typo)
                losing_to_winning_formatted[shorter_typo] = longer_typo
            else:
                formatted_typos_to_remove.add(longer_typo)
                losing_to_winning_formatted[longer_typo] = shorter_typo

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
        """Detect conflicts using suffix array helpers.

        This uses suffix array to enable O(log N + M) substring queries instead of O(N²).

        This uses:
        - Suffix array to enable O(log N + M) substring queries instead of O(N²)
        - Build suffix array once from all formatted typos
        - Query for each typo to find all substring matches efficiently
        - Track formatted typo-level removals for efficient bulk removal

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
        processed_formatted_pairs: set[frozenset[str]] = set()

        # Track formatted typos to remove and their conflicting winners (efficient bulk removal)
        formatted_typos_to_remove: set[str] = set()
        losing_to_winning_formatted: dict[str, str] = {}

        # Build suffix array from all formatted typos
        formatted_typos = list(formatted_to_corrections.keys())
        if not formatted_typos:
            return all_corrections_to_remove, all_conflict_pairs

        # Build suffix array
        sa = build_suffix_array(formatted_typos, self.context.verbose, self.name)

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

            # Skip if this formatted typo is already marked for removal
            if formatted_typo in formatted_typos_to_remove:
                continue

            corrections_for_typo = formatted_to_corrections[formatted_typo]

            # Process conflicts for this typo
            self._process_typo_conflicts(
                i,
                formatted_typo,
                corrections_for_typo,
                formatted_typos,
                formatted_to_corrections,
                match_direction,
                processed_formatted_pairs,
                formatted_typos_to_remove,
                losing_to_winning_formatted,
                sa,
                state,
            )

        if progress_bar is not None:
            progress_bar.close()

        # Bulk remove ALL corrections with losing formatted typos
        bulk_remove_losing_formatted_typos(
            formatted_typos_to_remove,
            losing_to_winning_formatted,
            formatted_to_corrections,
            all_corrections_to_remove,
            all_conflict_pairs,
        )

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
                state,
            )

        # Remove from active set
        if correction in state.active_corrections:
            state.remove_correction(typo, word, boundary, self.name, reason)
        elif correction in state.active_patterns:
            state.remove_pattern(typo, word, boundary, self.name, reason)

        # Add to graveyard
        # pylint: disable=duplicate-code
        # Acceptable pattern: This is a function call to state.add_to_graveyard
        # with standard parameters. The similar code in platform_constraints.py
        # calls the same function with the same parameters. This is expected when
        # multiple places need to add items to the graveyard for the same reason.
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
