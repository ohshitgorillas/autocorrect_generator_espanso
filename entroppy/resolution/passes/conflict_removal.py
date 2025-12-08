"""Conflict Removal Pass - removes substring conflicts."""

from collections import defaultdict
from multiprocessing import Pool
from typing import TYPE_CHECKING, Any

from tqdm import tqdm

from entroppy.core import BoundaryType
from entroppy.resolution.conflict_logging import log_blocked_correction, log_kept_correction
from entroppy.resolution.conflicts import get_detector_for_boundary
from entroppy.resolution.passes import conflict_removal_helpers
from entroppy.resolution.passes.conflict_removal_helpers import (
    find_blocker_typo,
    shard_large_group,
)
from entroppy.resolution.solver import Pass
from entroppy.resolution.state import RejectionReason

if TYPE_CHECKING:
    from entroppy.resolution.state import DictionaryState


def _process_conflict_batch_worker_wrapper(
    boundary: BoundaryType,
    corrections: list[tuple[str, str, BoundaryType]],
) -> tuple[
    list[tuple[str, str, BoundaryType]],  # blocked corrections
    list[tuple[str, str, BoundaryType, str]],  # graveyard entries
]:
    """Wrapper function for multiprocessing compatibility.

    This wrapper ensures the function can be properly pickled for multiprocessing.
    """
    return conflict_removal_helpers.process_conflict_batch_worker(boundary, corrections)


class ConflictRemovalPass(Pass):
    """Removes corrections that conflict with shorter corrections.

    This pass enforces substring/overlap rules:
    - For LEFT/NONE/BOTH boundaries: longer typos starting with shorter typos
    - For RIGHT boundaries: longer typos ending with shorter typos

    When a conflict is detected, the longer correction is removed and added
    to the graveyard. This triggers self-healing: in the next iteration,
    CandidateSelectionPass will retry with a stricter boundary.

    Example:
        - "teh" -> "the" (NONE boundary) is active
        - "tehir" -> "their" (NONE boundary) is added
        - This pass detects conflict: "tehir" starts with "teh"
        - Removes "tehir" with NONE, adds to graveyard
        - Next iteration: CandidateSelectionPass retries "tehir" with LEFT/RIGHT/BOTH
    """

    @property
    def name(self) -> str:
        """Return the name of this pass."""
        return "ConflictRemoval"

    def run(self, state: "DictionaryState") -> None:
        """Run the conflict removal pass.

        Args:
            state: The dictionary state to modify
        """
        # Combine active corrections and patterns - both can conflict with each other
        all_corrections = list(state.active_corrections) + list(state.active_patterns)

        if not all_corrections:
            return

        # Group by boundary type
        by_boundary = defaultdict(list)
        for correction in all_corrections:
            _, _, boundary = correction
            by_boundary[boundary].append(correction)

        # Determine if we should use parallel processing
        use_parallel = self.context.jobs > 1 and len(all_corrections) >= 100

        if use_parallel:
            self._process_parallel(state, by_boundary)
        else:
            # Process each boundary group sequentially
            if self.context.verbose:
                boundary_items: Any = tqdm(
                    by_boundary.items(),
                    desc=f"    {self.name}",
                    unit="boundary",
                    leave=False,
                )
            else:
                boundary_items = by_boundary.items()

            for boundary, corrections in boundary_items:
                self._process_boundary_group(state, corrections, boundary)

    def _prepare_parallel_tasks(
        self, by_boundary: dict[BoundaryType, list[tuple[str, str, BoundaryType]]]
    ) -> list[tuple[BoundaryType, list[tuple[str, str, BoundaryType]]]]:
        """Prepare tasks for parallel processing."""
        tasks = []
        for boundary, corrections in by_boundary.items():
            if not corrections:
                continue

            # For large groups (especially NONE), shard by first character
            if len(corrections) > 1000:
                shards = shard_large_group(corrections)
                for shard_corrections in shards:
                    tasks.append((boundary, shard_corrections))
            else:
                # Small group, process as-is
                tasks.append((boundary, corrections))

        return tasks

    def _aggregate_parallel_results(
        self,
        results: list[
            tuple[list[tuple[str, str, BoundaryType]], list[tuple[str, str, BoundaryType, str]]]
        ],
    ) -> tuple[list[tuple[str, str, BoundaryType]], list[tuple[str, str, BoundaryType, str]]]:
        """Aggregate results from parallel processing.

        Args:
            results: List of (blocked_corrections, graveyard_entries) tuples from workers

        Returns:
            Tuple of (all_blocked_corrections, all_graveyard_entries)
        """
        blocked_corrections = []
        graveyard_entries = []

        for blocked, graveyard in results:
            blocked_corrections.extend(blocked)
            graveyard_entries.extend(graveyard)

        return blocked_corrections, graveyard_entries

    def _log_blocked_correction_from_graveyard(
        self,
        state: "DictionaryState",
        correction: tuple[str, str, BoundaryType],
        blocker_typo: str,
    ) -> None:
        """Log a blocked correction using graveyard entry information.

        Args:
            state: The dictionary state
            correction: The blocked correction tuple
            blocker_typo: The typo that blocked this correction
        """
        typo_str, word, boundary_type = correction

        # Get detector for boundary to calculate expected result
        detector = get_detector_for_boundary(boundary_type)
        # Find blocking correction
        blocking_correction = None
        for corr in state.active_corrections | state.active_patterns:
            if corr[0] == blocker_typo and corr[2] == boundary_type:
                blocking_correction = corr
                break
        if blocking_correction:
            short_word = blocking_correction[1]
            long_word = word
            log_blocked_correction(
                correction,
                typo_str,
                blocker_typo,
                short_word,
                long_word,
                detector,
                state.debug_words,
                state.debug_typo_matcher,
            )

    def _apply_blocked_corrections_removal(
        self,
        state: "DictionaryState",
        blocked_corrections: list[tuple[str, str, BoundaryType]],
        graveyard_entries: list[tuple[str, str, BoundaryType, str]],
    ) -> None:
        """Apply removal of blocked corrections and add to graveyard.

        Args:
            state: The dictionary state
            blocked_corrections: List of corrections to remove
            graveyard_entries: List of graveyard entries to add
        """
        # Apply removals in main thread
        for correction in blocked_corrections:
            typo_str, word, boundary_type = correction

            # Find the blocker for logging
            blocker_typo = find_blocker_typo(correction, graveyard_entries)

            # Log blocked correction if it's a debug target
            if blocker_typo:
                self._log_blocked_correction_from_graveyard(state, correction, blocker_typo)

            # Remove from active set (check both corrections and patterns)
            if correction in state.active_corrections:
                state.remove_correction(
                    typo_str,
                    word,
                    boundary_type,
                    self.name,
                    "Blocked by substring conflict",
                )
            elif correction in state.active_patterns:
                state.remove_pattern(
                    typo_str,
                    word,
                    boundary_type,
                    self.name,
                    "Blocked by substring conflict",
                )

        # Add to graveyard
        for typo_str, word, boundary_type, blocker_typo in graveyard_entries:
            state.add_to_graveyard(
                typo_str,
                word,
                boundary_type,
                RejectionReason.BLOCKED_BY_CONFLICT,
                blocker_typo,
                pass_name=self.name,
            )

    def _process_parallel(
        self,
        state: "DictionaryState",
        by_boundary: dict[BoundaryType, list[tuple[str, str, BoundaryType]]],
    ) -> None:
        """Process boundary groups in parallel.

        Args:
            state: The dictionary state
            by_boundary: Dictionary mapping boundary types to their corrections
        """
        # Prepare tasks: each boundary group, and sharded large groups
        tasks = self._prepare_parallel_tasks(by_boundary)

        if not tasks:
            return

        # Process tasks in parallel
        with Pool(processes=self.context.jobs) as pool:
            if self.context.verbose:
                # Use starmap_async for progress tracking
                async_result = pool.starmap_async(_process_conflict_batch_worker_wrapper, tasks)
                # Show progress while waiting
                with tqdm(
                    total=len(tasks), desc=f"    {self.name}", unit="batch", leave=False
                ) as pbar:
                    while not async_result.ready():
                        async_result.wait(timeout=0.1)
                    results = async_result.get()
                    pbar.update(len(tasks))
            else:
                results = pool.starmap(_process_conflict_batch_worker_wrapper, tasks)

        # Aggregate results and apply removals
        blocked_corrections, graveyard_entries = self._aggregate_parallel_results(results)
        self._apply_blocked_corrections_removal(state, blocked_corrections, graveyard_entries)

    def _check_typo_against_candidates(
        self,
        state: "DictionaryState",
        typo: str,
        index_key: str,
        candidates_by_char: dict[str, list[str]],
        typo_to_correction: dict[str, tuple[str, str, BoundaryType]],
        detector,
    ) -> tuple[str, str, BoundaryType] | None:
        """Check if typo is blocked by any candidate, returning blocking correction if blocked."""
        if index_key not in candidates_by_char:
            return None

        for candidate in candidates_by_char[index_key]:
            blocking_correction = self._check_if_blocked(
                state,
                typo,
                candidate,
                typo_to_correction,
                detector,
            )
            if blocking_correction:
                return blocking_correction

        return None

    def _remove_blocked_corrections(
        self,
        state: "DictionaryState",
        typos_to_remove: set[str],
        typo_to_correction: dict[str, tuple[str, str, BoundaryType]],
        detector=None,
        blocking_map: (
            dict[tuple[str, str, BoundaryType], tuple[str, str, BoundaryType]] | None
        ) = None,
    ) -> None:
        """Remove all blocked corrections/patterns from state."""
        for typo in typos_to_remove:
            correction = typo_to_correction[typo]
            typo_str, word, boundary_type = correction

            # Log blocked correction if it's a debug target
            if detector and blocking_map and correction in blocking_map:
                blocking_correction = blocking_map[correction]
                blocker_typo = blocking_correction[0]
                short_word = blocking_correction[1]
                long_word = word
                log_blocked_correction(
                    correction,
                    typo_str,
                    blocker_typo,
                    short_word,
                    long_word,
                    detector,
                    state.debug_words,
                    state.debug_typo_matcher,
                )

            # Remove from active set (check both corrections and patterns)
            if correction in state.active_corrections:
                state.remove_correction(
                    typo_str,
                    word,
                    boundary_type,
                    self.name,
                    "Blocked by substring conflict",
                )
            elif correction in state.active_patterns:
                state.remove_pattern(
                    typo_str,
                    word,
                    boundary_type,
                    self.name,
                    "Blocked by substring conflict",
                )

    def _process_boundary_group(
        self,
        state: "DictionaryState",
        corrections: list[tuple[str, str, BoundaryType]],
        boundary: BoundaryType,
    ) -> None:
        """Process a single boundary group to find and remove conflicts.

        Args:
            state: The dictionary state
            corrections: List of corrections with the same boundary
            boundary: The boundary type for this group
        """
        if not corrections:
            return

        # Get the appropriate conflict detector for this boundary
        detector = get_detector_for_boundary(boundary)

        # Build lookup map from typo to full correction
        typo_to_correction = {c[0]: c for c in corrections}

        # Sort typos by length (shorter first)
        sorted_typos = sorted(typo_to_correction.keys(), key=len)

        # Track which typos are blocked
        typos_to_remove = set()
        blocking_map: dict[tuple[str, str, BoundaryType], tuple[str, str, BoundaryType]] = {}

        # Build character-based index for efficient lookup
        # Maps character → list of shorter typos with that character at the relevant position
        # pylint: disable=duplicate-code
        # Similar initialization pattern to conflicts.py, but logic diverges significantly
        # after this point (uses state and different conflict checking)
        candidates_by_char: dict[str, list[str]] = defaultdict(list)

        for typo in sorted_typos:
            if not typo:
                continue

            index_key = detector.get_index_key(typo)

            # Check against candidates that share the same index character
            blocking_correction = self._check_typo_against_candidates(
                state, typo, index_key, candidates_by_char, typo_to_correction, detector
            )
            if blocking_correction:
                typos_to_remove.add(typo)
                correction = typo_to_correction[typo]
                blocking_map[correction] = blocking_correction
            else:
                # If not blocked, add to index for future comparisons
                candidates_by_char[index_key].append(typo)
                # Log kept correction
                correction = typo_to_correction[typo]
                log_kept_correction(
                    correction,
                    boundary,
                    state.debug_words,
                    state.debug_typo_matcher,
                )

        # Remove all blocked corrections/patterns
        self._remove_blocked_corrections(
            state, typos_to_remove, typo_to_correction, detector, blocking_map
        )

    def _check_if_blocked(
        self,
        state: "DictionaryState",
        long_typo: str,
        short_typo: str,
        typo_to_correction: dict[str, tuple[str, str, BoundaryType]],
        detector,
    ) -> tuple[str, str, BoundaryType] | None:
        """Check if a typo is blocked by a shorter candidate.

        Args:
            state: The dictionary state
            long_typo: The longer typo to check
            short_typo: The shorter candidate that might block it
            typo_to_correction: Map from typo to full correction
            detector: Conflict detector for this boundary type

        Returns:
            The blocking correction if blocked, None otherwise
        """
        # Quick substring check first
        if not detector.contains_substring(long_typo, short_typo):
            return None

        # Get the corrections
        long_correction = typo_to_correction[long_typo]
        short_correction = typo_to_correction[short_typo]

        long_word = long_correction[1]
        short_word = short_correction[1]
        boundary = long_correction[2]

        # Full conflict check
        if not detector.check_conflict(long_typo, short_typo, long_word, short_word):
            return None

        # This is a conflict - log and add to graveyard
        log_blocked_correction(
            long_correction,
            long_typo,
            short_typo,
            short_word,
            long_word,
            detector,
            state.debug_words,
            state.debug_typo_matcher,
        )

        state.add_to_graveyard(
            long_typo,
            long_word,
            boundary,
            RejectionReason.BLOCKED_BY_CONFLICT,
            short_typo,
            pass_name=self.name,
        )

        return short_correction
