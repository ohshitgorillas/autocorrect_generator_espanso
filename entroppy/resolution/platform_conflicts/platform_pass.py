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
from dataclasses import dataclass
from multiprocessing import Pool
import threading
from typing import TYPE_CHECKING, Any

from tqdm import tqdm

from entroppy.core.boundaries import BoundaryType
from entroppy.core.types import MatchDirection
from entroppy.platforms.qmk.formatting import format_boundary_markers
from entroppy.resolution.platform_conflicts import (
    build_length_buckets,
    check_bucket_conflicts,
)
from entroppy.resolution.platform_conflicts.logging import (
    log_platform_substring_conflict,
)
from entroppy.resolution.solver import Pass
from entroppy.resolution.state import RejectionReason

if TYPE_CHECKING:
    from entroppy.resolution.state import DictionaryState


@dataclass(frozen=True)
class FormattingContext:
    """Immutable context for formatting workers.

    This encapsulates the platform information needed for formatting corrections.
    The frozen dataclass ensures immutability and thread-safety.

    Attributes:
        is_qmk: Whether the platform is QMK (requires boundary formatting)
    """

    is_qmk: bool


# Thread-local storage for formatting worker context
_formatting_worker_context = threading.local()


def init_formatting_worker(context: FormattingContext) -> None:
    """Initialize worker process with formatting context.

    Args:
        context: FormattingContext to store in thread-local storage
    """
    _formatting_worker_context.value = context


def get_formatting_worker_context() -> FormattingContext:
    """Get the current worker's formatting context from thread-local storage.

    Returns:
        FormattingContext for this worker

    Raises:
        RuntimeError: If called before init_formatting_worker
    """
    try:
        context = _formatting_worker_context.value
        if not isinstance(context, FormattingContext):
            raise RuntimeError("Invalid formatting context type")
        return context
    except AttributeError as e:
        raise RuntimeError(
            "Formatting worker context not initialized. Call init_formatting_worker first."
        ) from e


def _format_correction_worker(
    correction: tuple[str, str, BoundaryType],
) -> tuple[tuple[str, str, BoundaryType], str]:
    """Worker function to format a single correction.

    Args:
        correction: Tuple of (typo, word, boundary)

    Returns:
        Tuple of (correction, formatted_typo)
    """
    context = get_formatting_worker_context()
    typo, _word, boundary = correction

    if context.is_qmk:
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

        # Determine if we should use parallel processing
        use_parallel = self.context.jobs > 1 and len(all_corrections) >= 100

        if use_parallel:
            # Create worker context (immutable, serializable)
            formatting_context = FormattingContext(is_qmk=is_qmk)

            # Process in parallel using initializer pattern (avoids pickle)
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
        state: "DictionaryState",
    ) -> tuple[
        list[tuple[tuple[str, str, BoundaryType], str]],
        dict[tuple[str, str, BoundaryType], tuple[str, str, BoundaryType]],
    ]:
        """Detect conflicts using character-based indexing and length buckets for efficiency.

        This uses:
        - Character-based indexing to reduce comparisons from O(N²) to O(N × K)
          where K = average candidates per character (typically < 50)
        - Length buckets to only check conflicts between adjacent length groups
          (a typo of length 3 can't be a substring of a typo of length 2)
        - Early termination to skip checking pairs where one correction is already marked

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
        all_corrections_to_remove = []
        all_conflict_pairs: dict[tuple[str, str, BoundaryType], tuple[str, str, BoundaryType]] = {}
        processed_pairs: set[frozenset[tuple[str, str, BoundaryType]]] = set()

        # Track corrections already marked for removal (early termination optimization)
        corrections_to_remove_set: set[tuple[str, str, BoundaryType]] = set()

        # Group formatted typos by length into buckets
        length_buckets = build_length_buckets(formatted_to_corrections)

        # Process buckets in length order (shortest first)
        sorted_lengths = sorted(length_buckets.keys())

        # Calculate total number of formatted typos for progress tracking
        total_formatted_typos = sum(len(bucket) for bucket in length_buckets.values())

        # Character-based index: char -> list of (formatted_typo, corrections)
        # This index accumulates shorter typos across all processed buckets
        candidates_by_char: dict[
            str,
            list[tuple[str, list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]]]],
        ] = defaultdict(list)

        if self.context.verbose:
            progress_bar: Any = tqdm(
                total=total_formatted_typos,
                desc=f"    {self.name} (checking conflicts)",
                unit="typo",
                leave=False,
            )
        else:
            progress_bar = None

        # Process each length bucket
        for length in sorted_lengths:
            current_bucket = length_buckets[length]

            corrections_to_remove, conflict_pairs = check_bucket_conflicts(
                current_bucket,
                candidates_by_char,
                match_direction,
                processed_pairs,
                corrections_to_remove_set,
                progress_bar=progress_bar,
                validation_index=self.context.validation_index,
                source_index=self.context.source_index,
                debug_words=state.debug_words,
                debug_typo_matcher=state.debug_typo_matcher,
            )

            all_corrections_to_remove.extend(corrections_to_remove)
            all_conflict_pairs.update(conflict_pairs)

        if progress_bar is not None:
            progress_bar.close()

        return all_corrections_to_remove, all_conflict_pairs

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
                pass_name=self.name,
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
