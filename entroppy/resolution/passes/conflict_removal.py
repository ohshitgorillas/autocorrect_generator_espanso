"""Conflict Removal Pass - removes substring conflicts."""

from collections import defaultdict
from multiprocessing import Pool
from typing import TYPE_CHECKING, Any

from tqdm import tqdm

from entroppy.core import BoundaryType
from entroppy.resolution.conflicts import build_typo_index, get_detector_for_boundary
from entroppy.resolution.solver import Pass
from entroppy.resolution.state import RejectionReason

if TYPE_CHECKING:
    from entroppy.resolution.state import DictionaryState


def _process_conflict_batch_worker(
    boundary: BoundaryType,
    corrections: list[tuple[str, str, BoundaryType]],
) -> tuple[
    list[tuple[str, str, BoundaryType]],  # blocked corrections
    list[tuple[str, str, BoundaryType, str]],  # graveyard entries (typo, word, boundary, blocker)
]:
    """Worker function to process a batch of corrections for conflict detection.

    Args:
        boundary: The boundary type for this batch
        corrections: List of corrections to process

    Returns:
        Tuple of (blocked_corrections, graveyard_entries)
        - blocked_corrections: List of (typo, word, boundary) tuples to remove
        - graveyard_entries: List of (typo, word, boundary, blocker_typo) tuples
    """
    if not corrections:
        return [], []

    # Get the appropriate conflict detector for this boundary
    detector = get_detector_for_boundary(boundary)

    # Use existing build_typo_index function to avoid code duplication
    # Pass empty debug sets since we don't need debug logging in workers
    typos_to_remove, blocking_map = build_typo_index(
        corrections,
        detector,
        boundary,
        debug_words=set(),
        debug_typo_matcher=None,
        collect_blocking_map=True,
    )

    # Build lookup map from typo to full correction
    typo_to_correction = {c[0]: c for c in corrections}

    # Build return lists
    blocked_corrections = [typo_to_correction[typo] for typo in typos_to_remove]
    graveyard_entries = [
        (
            typo,
            typo_to_correction[typo][1],  # word
            boundary,
            blocking_map[typo_to_correction[typo]][
                0
            ],  # blocker_typo (first element of blocking correction)
        )
        for typo in typos_to_remove
        if typo_to_correction[typo] in blocking_map
    ]

    return blocked_corrections, graveyard_entries


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

    def _shard_large_group(
        self, corrections: list[tuple[str, str, BoundaryType]]
    ) -> list[list[tuple[str, str, BoundaryType]]]:
        """Shard a large group of corrections by first character."""
        sharded = defaultdict(list)
        for correction in corrections:
            typo = correction[0]
            if typo:
                first_char = typo[0].lower()
                sharded[first_char].append(correction)
            else:
                # Empty typos go to a special shard
                sharded[""].append(correction)

        return [shard for shard in sharded.values() if shard]

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
                shards = self._shard_large_group(corrections)
                for shard_corrections in shards:
                    tasks.append((boundary, shard_corrections))
            else:
                # Small group, process as-is
                tasks.append((boundary, corrections))

        return tasks

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
                async_result = pool.starmap_async(_process_conflict_batch_worker, tasks)
                # Show progress while waiting
                with tqdm(
                    total=len(tasks), desc=f"    {self.name}", unit="batch", leave=False
                ) as pbar:
                    while not async_result.ready():
                        async_result.wait(timeout=0.1)
                    results = async_result.get()
                    pbar.update(len(tasks))
            else:
                results = pool.starmap(_process_conflict_batch_worker, tasks)

        # Aggregate results and apply removals
        blocked_corrections = []
        graveyard_entries = []

        for blocked, graveyard in results:
            blocked_corrections.extend(blocked)
            graveyard_entries.extend(graveyard)

        # Apply removals in main thread
        for correction in blocked_corrections:
            typo_str, word, boundary_type = correction

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

    def _check_typo_against_candidates(
        self,
        state: "DictionaryState",
        typo: str,
        index_key: str,
        candidates_by_char: dict[str, list[str]],
        typo_to_correction: dict[str, tuple[str, str, BoundaryType]],
        detector,
    ) -> bool:
        """Check if typo is blocked by any candidate, returning True if blocked."""
        if index_key not in candidates_by_char:
            return False

        for candidate in candidates_by_char[index_key]:
            blocking_correction = self._check_if_blocked(
                state,
                typo,
                candidate,
                typo_to_correction,
                detector,
            )
            if blocking_correction:
                return True

        return False

    def _remove_blocked_corrections(
        self,
        state: "DictionaryState",
        typos_to_remove: set[str],
        typo_to_correction: dict[str, tuple[str, str, BoundaryType]],
    ) -> None:
        """Remove all blocked corrections/patterns from state."""
        for typo in typos_to_remove:
            correction = typo_to_correction[typo]
            typo_str, word, boundary_type = correction

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
            if self._check_typo_against_candidates(
                state, typo, index_key, candidates_by_char, typo_to_correction, detector
            ):
                typos_to_remove.add(typo)
            else:
                # If not blocked, add to index for future comparisons
                candidates_by_char[index_key].append(typo)

        # Remove all blocked corrections/patterns
        self._remove_blocked_corrections(state, typos_to_remove, typo_to_correction)

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

        # This is a conflict - add to graveyard
        state.add_to_graveyard(
            long_typo,
            long_word,
            boundary,
            RejectionReason.BLOCKED_BY_CONFLICT,
            short_typo,
            pass_name=self.name,
        )

        return short_correction
