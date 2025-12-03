"""Candidate Selection Pass - promotes raw typos to active corrections."""

from collections import defaultdict
from multiprocessing import Pool
from typing import TYPE_CHECKING

from loguru import logger
from tqdm import tqdm

from entroppy.core import BoundaryType
from entroppy.core.boundaries import determine_boundaries
from entroppy.matching import ExclusionMatcher
from entroppy.resolution.state import RejectionReason
from entroppy.resolution.solver import Pass
from entroppy.resolution.worker_context import (
    CandidateSelectionContext,
    get_candidate_selection_worker_context,
    get_candidate_worker_indexes,
    init_candidate_selection_worker,
)
from entroppy.utils.helpers import cached_word_frequency

if TYPE_CHECKING:
    from entroppy.resolution.state import DictionaryState
    from entroppy.resolution.solver import PassContext


def _process_typo_batch_worker(
    batch: list[tuple[str, list[str]]],
) -> tuple[
    list[tuple[str, str, BoundaryType]],  # corrections
    list[tuple[str, str, BoundaryType, RejectionReason, str | None]],  # graveyard entries
]:
    """Worker function to process a batch of typos.

    Args:
        batch: List of (typo, word_list) tuples to process

    Returns:
        Tuple of (corrections, graveyard_entries)
        - corrections: List of (typo, word, boundary) tuples to add
        - graveyard_entries: List of (typo, word, boundary, reason, blocker) tuples
    """
    context = get_candidate_selection_worker_context()
    validation_index, source_index = get_candidate_worker_indexes()

    # Recreate ExclusionMatcher in worker (not serializable due to compiled regex)
    exclusion_matcher = (
        ExclusionMatcher(set(context.exclusion_set)) if context.exclusion_set else None
    )

    corrections = []
    graveyard_entries = []

    for typo, word_list in batch:
        # Skip if already covered
        if typo in context.covered_typos:
            continue

        # Get unique words for this typo
        unique_words = list(set(word_list))

        # Process based on number of words
        if len(unique_words) == 1:
            _process_single_word_worker(
                typo,
                unique_words[0],
                context,
                validation_index,
                source_index,
                exclusion_matcher,
                corrections,
                graveyard_entries,
            )
        else:
            _process_collision_worker(
                typo,
                unique_words,
                context,
                validation_index,
                source_index,
                exclusion_matcher,
                corrections,
                graveyard_entries,
            )

    return corrections, graveyard_entries


def _process_single_word_worker(
    typo: str,
    word: str,
    context: CandidateSelectionContext,
    validation_index,
    source_index,
    exclusion_matcher: ExclusionMatcher | None,
    corrections: list[tuple[str, str, BoundaryType]],
    graveyard_entries: list[tuple[str, str, BoundaryType, RejectionReason, str | None]],
) -> None:
    """Process a typo with a single word (no collision) in worker.

    Args:
        typo: The typo string
        word: The correct word
        context: Worker context
        validation_index: Boundary index for validation set
        source_index: Boundary index for source words
        exclusion_matcher: Exclusion matcher (or None)
        corrections: List to append corrections to
        graveyard_entries: List to append graveyard entries to
    """
    # Determine the natural boundary for this typo
    natural_boundary = determine_boundaries(typo, validation_index, source_index)

    # Try boundaries in order: NONE -> LEFT/RIGHT -> BOTH
    boundaries_to_try = _get_boundary_order(natural_boundary)

    for boundary in boundaries_to_try:
        # Check if this is in the graveyard
        if (typo, word, boundary) in context.graveyard:
            continue

        # Check length constraints
        if not _check_length_constraints_worker(typo, word, context.min_typo_length):
            graveyard_entries.append((typo, word, boundary, RejectionReason.TOO_SHORT, None))
            continue

        # Check exclusions
        if exclusion_matcher and exclusion_matcher.should_exclude((typo, word, boundary)):
            graveyard_entries.append(
                (typo, word, boundary, RejectionReason.EXCLUDED_BY_PATTERN, None)
            )
            continue

        # Add the correction
        corrections.append((typo, word, boundary))
        return  # Successfully added, no need to try other boundaries


def _process_collision_worker(
    typo: str,
    unique_words: list[str],
    context: CandidateSelectionContext,
    validation_index,
    source_index,
    exclusion_matcher: ExclusionMatcher | None,
    corrections: list[tuple[str, str, BoundaryType]],
    graveyard_entries: list[tuple[str, str, BoundaryType, RejectionReason, str | None]],
) -> None:
    """Process a typo with multiple competing words (collision) in worker.

    Args:
        typo: The typo string
        unique_words: List of competing words
        context: Worker context
        validation_index: Boundary index for validation set
        source_index: Boundary index for source words
        exclusion_matcher: Exclusion matcher (or None)
        corrections: List to append corrections to
        graveyard_entries: List to append graveyard entries to
    """
    # Determine boundaries for each word
    word_boundary_map = {}
    for word in unique_words:
        boundary = determine_boundaries(typo, validation_index, source_index)
        word_boundary_map[word] = boundary

    # Group words by boundary type
    by_boundary = defaultdict(list)
    for word, boundary in word_boundary_map.items():
        by_boundary[boundary].append(word)

    # Process each boundary group separately
    for boundary, words_in_group in by_boundary.items():
        if len(words_in_group) == 1:
            # No collision within this boundary
            word = words_in_group[0]
            _process_single_word_with_boundary_worker(
                typo,
                word,
                boundary,
                context,
                exclusion_matcher,
                corrections,
                graveyard_entries,
            )
        else:
            # Collision within this boundary - resolve by frequency
            _resolve_collision_by_frequency_worker(
                typo,
                words_in_group,
                boundary,
                context,
                exclusion_matcher,
                corrections,
                graveyard_entries,
            )


def _process_single_word_with_boundary_worker(
    typo: str,
    word: str,
    boundary: BoundaryType,
    context: CandidateSelectionContext,
    exclusion_matcher: ExclusionMatcher | None,
    corrections: list[tuple[str, str, BoundaryType]],
    graveyard_entries: list[tuple[str, str, BoundaryType, RejectionReason, str | None]],
) -> None:
    """Process a single word with a specific boundary in worker.

    Args:
        typo: The typo string
        word: The correct word
        boundary: The boundary type
        context: Worker context
        exclusion_matcher: Exclusion matcher (or None)
        corrections: List to append corrections to
        graveyard_entries: List to append graveyard entries to
    """
    # Try boundaries in order starting from the given boundary
    boundaries_to_try = _get_boundary_order(boundary)

    for bound in boundaries_to_try:
        # Check if this is in the graveyard
        if (typo, word, bound) in context.graveyard:
            continue

        # Check length constraints
        if not _check_length_constraints_worker(typo, word, context.min_typo_length):
            graveyard_entries.append((typo, word, bound, RejectionReason.TOO_SHORT, None))
            continue

        # Check exclusions
        if exclusion_matcher and exclusion_matcher.should_exclude((typo, word, bound)):
            graveyard_entries.append((typo, word, bound, RejectionReason.EXCLUDED_BY_PATTERN, None))
            continue

        # Add the correction
        corrections.append((typo, word, bound))
        return  # Successfully added


def _resolve_collision_by_frequency_worker(
    typo: str,
    words: list[str],
    boundary: BoundaryType,
    context: CandidateSelectionContext,
    exclusion_matcher: ExclusionMatcher | None,
    corrections: list[tuple[str, str, BoundaryType]],
    graveyard_entries: list[tuple[str, str, BoundaryType, RejectionReason, str | None]],
) -> None:
    """Resolve a collision using frequency analysis in worker.

    Args:
        typo: The typo string
        words: List of competing words
        boundary: The boundary type for this group
        context: Worker context
        exclusion_matcher: Exclusion matcher (or None)
        corrections: List to append corrections to
        graveyard_entries: List to append graveyard entries to
    """
    # Get frequencies for all words
    word_freqs = [(w, cached_word_frequency(w, "en")) for w in words]
    word_freqs.sort(key=lambda x: x[1], reverse=True)

    most_common = word_freqs[0]
    second_most = word_freqs[1] if len(word_freqs) > 1 else (None, 0)
    ratio = most_common[1] / second_most[1] if second_most[1] > 0 else float("inf")

    if ratio <= context.collision_threshold:
        # Ambiguous collision - add all words to graveyard
        for word in words:
            graveyard_entries.append(
                (typo, word, boundary, RejectionReason.COLLISION_AMBIGUOUS, f"ratio={ratio:.2f}")
            )
        return

    # Can resolve collision - use most common word
    word = most_common[0]

    # Try boundaries in order
    boundaries_to_try = _get_boundary_order(boundary)

    for bound in boundaries_to_try:
        # Check if this is in the graveyard
        if (typo, word, bound) in context.graveyard:
            continue

        # Check length constraints
        if not _check_length_constraints_worker(typo, word, context.min_typo_length):
            graveyard_entries.append((typo, word, bound, RejectionReason.TOO_SHORT, None))
            continue

        # Check exclusions
        if exclusion_matcher and exclusion_matcher.should_exclude((typo, word, bound)):
            graveyard_entries.append((typo, word, bound, RejectionReason.EXCLUDED_BY_PATTERN, None))
            continue

        # Add the correction
        corrections.append((typo, word, bound))
        return  # Successfully added


def _check_length_constraints_worker(typo: str, word: str, min_typo_length: int) -> bool:
    """Check if typo/word meet length constraints in worker.

    Args:
        typo: The typo string
        word: The correct word
        min_typo_length: Minimum typo length

    Returns:
        True if constraints are met
    """
    # If word is shorter than min_typo_length, typo must be at least min_typo_length
    if len(word) <= min_typo_length:
        return len(typo) >= min_typo_length
    return True


def _get_boundary_order(natural_boundary: BoundaryType) -> list[BoundaryType]:
    """Get the order of boundaries to try, starting with the natural one.

    This implements self-healing: if a less strict boundary fails,
    we automatically try stricter ones in subsequent iterations.

    Args:
        natural_boundary: The naturally determined boundary

    Returns:
        List of boundaries to try in order
    """
    # Order: try natural first, then stricter alternatives
    if natural_boundary == BoundaryType.NONE:
        # NONE is least strict - try all others if it fails
        return [
            BoundaryType.NONE,
            BoundaryType.LEFT,
            BoundaryType.RIGHT,
            BoundaryType.BOTH,
        ]
    if natural_boundary == BoundaryType.LEFT:
        return [BoundaryType.LEFT, BoundaryType.BOTH]
    if natural_boundary == BoundaryType.RIGHT:
        return [BoundaryType.RIGHT, BoundaryType.BOTH]
    # BOTH is most strict - only try it
    return [BoundaryType.BOTH]


class CandidateSelectionPass(Pass):
    """Selects and promotes raw typos to active corrections.

    This pass:
    1. Iterates through all raw typos
    2. Checks if each is already covered by active corrections or patterns
    3. If not covered, attempts to resolve collisions and add corrections
    4. Implements self-healing by checking the Graveyard:
       - If (typo, word, NONE) is dead, tries (typo, word, LEFT/RIGHT/BOTH)
       - This allows the solver to backtrack to stricter boundaries
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
        # Get typos to process (not already covered)
        typos_to_process = [
            (typo, word_list)
            for typo, word_list in state.raw_typo_map.items()
            if not state.is_typo_covered(typo)
        ]

        if not typos_to_process:
            return

        # Use multiprocessing if jobs > 1 and we have enough work
        if self.context.jobs > 1 and len(typos_to_process) > 100:
            self._run_parallel(state, typos_to_process)
        else:
            self._run_sequential(state, typos_to_process)

    def _run_sequential(
        self, state: "DictionaryState", typos_to_process: list[tuple[str, list[str]]]
    ) -> None:
        """Run candidate selection sequentially.

        Args:
            state: The dictionary state to modify
            typos_to_process: List of (typo, word_list) tuples to process
        """
        for typo, word_list in typos_to_process:
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
            validation_set=frozenset(self.context.validation_set),
            source_words=frozenset(self.context.source_words_set),
            min_typo_length=self.context.min_typo_length,
            collision_threshold=self.context.collision_threshold,
            exclusion_set=exclusion_set,
            covered_typos=covered_typos,
            graveyard=graveyard_set,
        )

        # Split into chunks (4 chunks per worker for load balancing)
        chunk_size = max(1, len(typos_to_process) // (self.context.jobs * 4))
        chunks = [
            typos_to_process[i : i + chunk_size]
            for i in range(0, len(typos_to_process), chunk_size)
        ]

        logger.info(f"  Using {self.context.jobs} parallel workers for candidate selection")
        logger.info(f"  Processing {len(typos_to_process)} typos in {len(chunks)} chunks")

        with Pool(
            processes=self.context.jobs,
            initializer=init_candidate_selection_worker,
            initargs=(worker_context,),
        ) as pool:
            results = pool.imap_unordered(_process_typo_batch_worker, chunks)

            # Wrap with progress bar
            results = tqdm(
                results,
                total=len(chunks),
                desc="    Processing typos",
                unit="chunk",
                leave=False,
            )

            # Collect results and apply to state
            for corrections, graveyard_entries in results:
                # Add corrections
                for typo, word, boundary in corrections:
                    state.add_correction(typo, word, boundary, self.name)

                # Add graveyard entries
                for typo, word, boundary, reason, blocker in graveyard_entries:
                    state.add_to_graveyard(typo, word, boundary, reason, blocker)

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
        # Determine the natural boundary for this typo
        natural_boundary = determine_boundaries(
            typo,
            self.context.validation_index,
            self.context.source_index,
        )

        # Try boundaries in order: NONE -> LEFT/RIGHT -> BOTH
        # This implements self-healing: if NONE fails, try stricter boundaries
        boundaries_to_try = _get_boundary_order(natural_boundary)

        for boundary in boundaries_to_try:
            # Check if this is in the graveyard
            if state.is_in_graveyard(typo, word, boundary):
                continue

            # Check length constraints
            if not self._check_length_constraints(typo, word):
                state.add_to_graveyard(
                    typo,
                    word,
                    boundary,
                    RejectionReason.TOO_SHORT,
                )
                continue

            # Check exclusions
            if self._is_excluded(typo, word, boundary):
                state.add_to_graveyard(
                    typo,
                    word,
                    boundary,
                    RejectionReason.EXCLUDED_BY_PATTERN,
                )
                continue

            # Add the correction
            state.add_correction(typo, word, boundary, self.name)
            return  # Successfully added, no need to try other boundaries

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
        # Determine boundaries for each word
        word_boundary_map = {}
        for word in unique_words:
            boundary = determine_boundaries(
                typo,
                self.context.validation_index,
                self.context.source_index,
            )
            word_boundary_map[word] = boundary

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
            # Check if this is in the graveyard
            if state.is_in_graveyard(typo, word, bound):
                continue

            # Check length constraints
            if not self._check_length_constraints(typo, word):
                state.add_to_graveyard(
                    typo,
                    word,
                    bound,
                    RejectionReason.TOO_SHORT,
                )
                continue

            # Check exclusions
            if self._is_excluded(typo, word, bound):
                state.add_to_graveyard(
                    typo,
                    word,
                    bound,
                    RejectionReason.EXCLUDED_BY_PATTERN,
                )
                continue

            # Add the correction
            state.add_correction(typo, word, bound, self.name)
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
            for word in words:
                state.add_to_graveyard(
                    typo,
                    word,
                    boundary,
                    RejectionReason.COLLISION_AMBIGUOUS,
                    f"ratio={ratio:.2f}",
                )
            return

        # Can resolve collision - use most common word
        word = most_common[0]

        # Try boundaries in order
        boundaries_to_try = _get_boundary_order(boundary)

        for bound in boundaries_to_try:
            # Check if this is in the graveyard
            if state.is_in_graveyard(typo, word, bound):
                continue

            # Check length constraints
            if not self._check_length_constraints(typo, word):
                state.add_to_graveyard(
                    typo,
                    word,
                    bound,
                    RejectionReason.TOO_SHORT,
                )
                continue

            # Check exclusions
            if self._is_excluded(typo, word, bound):
                state.add_to_graveyard(
                    typo,
                    word,
                    bound,
                    RejectionReason.EXCLUDED_BY_PATTERN,
                )
                continue

            # Add the correction
            state.add_correction(typo, word, bound, self.name)
            return  # Successfully added

    def _check_length_constraints(self, typo: str, word: str) -> bool:
        """Check if typo/word meet length constraints.

        Args:
            typo: The typo string
            word: The correct word

        Returns:
            True if constraints are met
        """
        # If word is shorter than min_word_length, typo must be at least min_typo_length
        # (This prevents very short typos for common words)
        if len(word) <= self.context.min_typo_length:
            return len(typo) >= self.context.min_typo_length
        return True

    def _is_excluded(self, typo: str, word: str, boundary: BoundaryType) -> bool:
        """Check if a correction is excluded by patterns.

        Args:
            typo: The typo string
            word: The correct word
            boundary: The boundary type

        Returns:
            True if excluded
        """
        if not self.context.exclusion_matcher:
            return False

        correction = (typo, word, boundary)
        return self.context.exclusion_matcher.should_exclude(correction)
