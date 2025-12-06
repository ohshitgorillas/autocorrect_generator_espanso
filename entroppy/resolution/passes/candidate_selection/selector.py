"""Candidate Selection Pass - promotes raw typos to active corrections."""

from collections import defaultdict
from multiprocessing import Pool
from typing import TYPE_CHECKING, Any

from loguru import logger
from tqdm import tqdm

from entroppy.core import BoundaryType
from entroppy.resolution.false_trigger_check import batch_check_false_triggers
from entroppy.resolution.passes.candidate_selection_workers import _process_typo_batch_worker
from entroppy.resolution.solver import Pass
from entroppy.resolution.state import RejectionReason
from entroppy.resolution.worker_context import (
    CandidateSelectionContext,
    init_candidate_selection_worker,
)
from entroppy.utils.helpers import cached_word_frequency

from .filters import _check_length_constraints, _is_excluded
from .helpers import _get_boundary_order

if TYPE_CHECKING:
    from entroppy.resolution.state import DictionaryState


class CandidateSelectionPass(Pass):
    """Selects and promotes raw typos to active corrections.

    Iterates through raw typos, checks coverage, resolves collisions, and adds corrections.
    Implements self-healing via Graveyard: if (typo, word, NONE) fails, tries stricter boundaries.
    """

    @property
    def name(self) -> str:
        """Return the name of this pass."""
        return "CandidateSelection"

    def run(self, state: "DictionaryState") -> None:
        """Run the candidate selection pass.

        Args:
            state: The dictionary state to modify
        """
        typos_to_process = self._get_typos_to_process(state)
        if not typos_to_process:
            return

        # Batch check all typos for false triggers (optimization)
        all_typos = [typo for typo, _ in typos_to_process]
        if all_typos:
            batch_results = batch_check_false_triggers(
                all_typos, self.context.validation_index, self.context.source_index
            )
            state.caching.set_batch_false_trigger_results(batch_results)

        # Use multiprocessing if jobs > 1 and we have enough work
        if self.context.jobs > 1 and len(typos_to_process) > 100:
            self._run_parallel(state, typos_to_process)
        else:
            self._run_sequential(state, typos_to_process)

    def _get_typos_to_process(self, state: "DictionaryState") -> list[tuple[str, list[str]]]:
        """Get list of typos to process in this iteration.

        Args:
            state: The dictionary state

        Returns:
            List of (typo, word_list) tuples to process
        """
        uncovered_typos = state.caching.get_uncovered_typos()
        if state.current_iteration == 1:
            # First iteration: check all typos and build uncovered set
            typos_to_process = []
            for typo, word_list in state.raw_typo_map.items():
                if not state.is_typo_covered(typo):
                    typos_to_process.append((typo, word_list))
                    uncovered_typos.add(typo)
            return typos_to_process

        # Subsequent iterations: early termination if no uncovered typos
        if not uncovered_typos:
            return []
        # Only process uncovered typos
        return [
            (typo, state.raw_typo_map[typo])
            for typo in uncovered_typos
            if typo in state.raw_typo_map
        ]

    def _run_sequential(
        self, state: "DictionaryState", typos_to_process: list[tuple[str, list[str]]]
    ) -> None:
        """Run candidate selection sequentially.

        Args:
            state: The dictionary state to modify
            typos_to_process: List of (typo, word_list) tuples to process
        """
        if self.context.verbose:
            typos_iter: Any = tqdm(
                typos_to_process,
                desc=f"    {self.name}",
                unit="typo",
                leave=False,
            )
        else:
            typos_iter = typos_to_process

        for typo, word_list in typos_iter:
            # Get unique words for this typo
            unique_words = list(set(word_list))

            # Process based on number of words
            if len(unique_words) == 1:
                self._process_single_word(state, typo, unique_words[0])
            else:
                self._process_collision(state, typo, unique_words)

    def _run_parallel(
        self, state: "DictionaryState", typos_to_process: list[tuple[str, list[str]]]
    ) -> None:
        """Run candidate selection in parallel.

        Args:
            state: The dictionary state to modify
            typos_to_process: List of (typo, word_list) tuples to process
        """
        # Build coverage and graveyard sets for workers
        covered_typos = frozenset(
            typo for typo in state.raw_typo_map.keys() if state.is_typo_covered(typo)
        )
        graveyard_set = frozenset(state.graveyard.keys())

        # Create worker context
        exclusion_set = frozenset(self.context.exclusion_set)

        worker_context = CandidateSelectionContext(
            validation_set=frozenset(self.context.filtered_validation_set),
            source_words=frozenset(self.context.source_words_set),
            min_typo_length=self.context.min_typo_length,
            collision_threshold=self.context.collision_threshold,
            exclusion_set=exclusion_set,
            covered_typos=covered_typos,
            graveyard=graveyard_set,
        )

        # Calculate optimal chunk size based on workload
        chunks = self._calculate_optimal_chunks(typos_to_process, self.context.jobs)

        logger.info(f"  Using {self.context.jobs} parallel workers for candidate selection")
        logger.info(f"  Processing {len(typos_to_process)} typos in {len(chunks)} chunks")

        with Pool(
            processes=self.context.jobs,
            initializer=init_candidate_selection_worker,
            initargs=(worker_context,),
        ) as pool:
            results = pool.imap_unordered(_process_typo_batch_worker, chunks)

            # Wrap with progress bar
            if self.context.verbose:
                results_wrapped_iter: Any = tqdm(
                    results,
                    total=len(chunks),
                    desc=f"    {self.name}",
                    unit="chunk",
                    leave=False,
                )
            else:
                results_wrapped_iter = results

            # Collect results and apply to state
            for result in results_wrapped_iter:
                # Defensive unpacking: ensure we get exactly 2 values
                if not isinstance(result, tuple):
                    raise ValueError(f"Worker returned non-tuple result: {type(result)} - {result}")
                if len(result) != 2:
                    raise ValueError(f"Worker returned {len(result)} values, expected 2: {result}")
                corrections, graveyard_entries = result

                # Add corrections
                for typo, word, boundary in corrections:
                    state.add_correction(typo, word, boundary, self.name)

                # Add graveyard entries
                for typo, word, boundary, reason, blocker in graveyard_entries:
                    state.add_to_graveyard(
                        typo, word, boundary, reason, blocker, pass_name=self.name
                    )

    @staticmethod
    def _calculate_optimal_chunks(
        typos_to_process: list[tuple[str, list[str]]], num_workers: int
    ) -> list[list[tuple[str, list[str]]]]:
        """Calculate optimal chunk size and split typos into chunks.

        Args:
            typos_to_process: List of (typo, word_list) tuples to process
            num_workers: Number of parallel workers

        Returns:
            List of chunks, each containing a list of (typo, word_list) tuples
        """
        # Estimate work per typo (single word vs collision)
        single_word_typos = sum(1 for _, words in typos_to_process if len(set(words)) == 1)
        collision_typos = len(typos_to_process) - single_word_typos

        # Collisions are 3-5x more expensive
        total_work_units = single_word_typos + (collision_typos * 4)

        # Target 50-100 work units per chunk (balances overhead vs granularity)
        optimal_chunks = max(num_workers, total_work_units // 75)
        optimal_chunks = min(optimal_chunks, num_workers * 10)  # Cap at 10 chunks per worker

        chunk_size = max(1, len(typos_to_process) // optimal_chunks)
        return [
            typos_to_process[i : i + chunk_size]
            for i in range(0, len(typos_to_process), chunk_size)
        ]

    def _try_boundary_for_correction(
        self,
        state: "DictionaryState",
        typo: str,
        word: str,
        boundary: BoundaryType,
    ) -> bool:
        """Try to add a correction with the given boundary.

        Args:
            state: The dictionary state
            typo: The typo string
            word: The correct word
            boundary: The boundary type to try

        Returns:
            True if correction was added, False otherwise
        """
        # Check if this is in the graveyard
        if state.is_in_graveyard(typo, word, boundary):
            return False

        # Check length constraints
        if not _check_length_constraints(typo, word, self.context.min_typo_length):
            state.add_to_graveyard(
                typo,
                word,
                boundary,
                RejectionReason.TOO_SHORT,
                pass_name=self.name,
            )
            return False

        # Check exclusions
        if _is_excluded(typo, word, boundary, self.context.exclusion_matcher):
            state.add_to_graveyard(
                typo,
                word,
                boundary,
                RejectionReason.EXCLUDED_BY_PATTERN,
                pass_name=self.name,
            )
            return False

        # Check for false triggers (using cache)
        would_cause, details = state.caching.get_cached_false_trigger(
            typo,
            boundary,
            self.context.validation_index,
            self.context.source_index,
            target_word=word,
        )
        if would_cause:
            # This boundary would cause false triggers - add to graveyard
            reason_value = details.get("reason", "false trigger")
            reason_str = reason_value if isinstance(reason_value, str) else "false trigger"
            state.add_to_graveyard(
                typo,
                word,
                boundary,
                RejectionReason.FALSE_TRIGGER,
                blocker=reason_str,
                pass_name=self.name,
            )
            return False

        # Add the correction
        state.add_correction(typo, word, boundary, self.name)
        return True

    def _process_single_word(
        self,
        state: "DictionaryState",
        typo: str,
        word: str,
    ) -> None:
        """Process a typo with a single word (no collision).

        Args:
            state: The dictionary state
            typo: The typo string
            word: The correct word
        """
        # Determine the natural boundary for this typo (using cache)
        natural_boundary = state.caching.get_cached_boundary(
            typo,
            self.context.validation_index,
            self.context.source_index,
        )

        # Try boundaries in order: NONE -> LEFT/RIGHT -> BOTH
        # This implements self-healing: if NONE fails, try stricter boundaries
        boundaries_to_try = _get_boundary_order(natural_boundary)

        for boundary in boundaries_to_try:
            if self._try_boundary_for_correction(state, typo, word, boundary):
                return  # Successfully added

    def _process_collision(
        self,
        state: "DictionaryState",
        typo: str,
        unique_words: list[str],
    ) -> None:
        """Process a typo with multiple competing words (collision).

        Args:
            state: The dictionary state
            typo: The typo string
            unique_words: List of competing words
        """
        # Determine boundaries for each word (using cache - same typo for all words)
        boundary = state.caching.get_cached_boundary(
            typo,
            self.context.validation_index,
            self.context.source_index,
        )
        # All words for the same typo will have the same boundary
        word_boundary_map = {word: boundary for word in unique_words}

        # Group words by boundary type
        by_boundary = defaultdict(list)
        for word, boundary in word_boundary_map.items():
            by_boundary[boundary].append(word)

        # Process each boundary group separately
        for boundary, words_in_group in by_boundary.items():
            if len(words_in_group) == 1:
                # No collision within this boundary
                word = words_in_group[0]
                self._process_single_word_with_boundary(state, typo, word, boundary)
            else:
                # Collision within this boundary - resolve by frequency
                self._resolve_collision_by_frequency(state, typo, words_in_group, boundary)

    def _process_single_word_with_boundary(
        self,
        state: "DictionaryState",
        typo: str,
        word: str,
        boundary: BoundaryType,
    ) -> None:
        """Process a single word with a specific boundary.

        Args:
            state: The dictionary state
            typo: The typo string
            word: The correct word
            boundary: The boundary type
        """
        # Try boundaries in order starting from the given boundary
        boundaries_to_try = _get_boundary_order(boundary)

        for bound in boundaries_to_try:
            if self._try_boundary_for_correction(state, typo, word, bound):
                return  # Successfully added

    def _resolve_collision_by_frequency(
        self,
        state: "DictionaryState",
        typo: str,
        words: list[str],
        boundary: BoundaryType,
    ) -> None:
        """Resolve a collision using frequency analysis.

        Args:
            state: The dictionary state
            typo: The typo string
            words: List of competing words
            boundary: The boundary type for this group
        """
        # Get frequencies for all words
        word_freqs = [(w, cached_word_frequency(w, "en")) for w in words]
        word_freqs.sort(key=lambda x: x[1], reverse=True)

        most_common = word_freqs[0]
        second_most = word_freqs[1] if len(word_freqs) > 1 else (None, 0)
        ratio = most_common[1] / second_most[1] if second_most[1] > 0 else float("inf")

        if ratio <= self.context.collision_threshold:
            # Ambiguous collision - add all words to graveyard
            self._handle_ambiguous_collision_sequential(state, typo, words, boundary, ratio)
            return

        # Can resolve collision - use most common word
        word = most_common[0]

        # Try boundaries in order
        self._try_boundaries_sequential(state, typo, word, boundary)

    def _handle_ambiguous_collision_sequential(
        self,
        state: "DictionaryState",
        typo: str,
        words: list[str],
        boundary: BoundaryType,
        ratio: float,
    ) -> None:
        """Handle ambiguous collision by adding all words to graveyard."""
        for word in words:
            state.add_to_graveyard(
                typo,
                word,
                boundary,
                RejectionReason.COLLISION_AMBIGUOUS,
                blocker=f"ratio={ratio:.2f}",
                pass_name=self.name,
            )

    def _try_boundaries_sequential(
        self,
        state: "DictionaryState",
        typo: str,
        word: str,
        boundary: BoundaryType,
    ) -> None:
        """Try boundaries in order to find a valid correction."""
        boundaries_to_try = _get_boundary_order(boundary)

        for bound in boundaries_to_try:
            if self._try_boundary_for_correction(state, typo, word, bound):
                return  # Successfully added
