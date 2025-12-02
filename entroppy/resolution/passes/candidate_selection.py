"""Candidate Selection Pass - promotes raw typos to active corrections."""

from typing import TYPE_CHECKING

from entroppy.core import BoundaryType
from entroppy.core.boundaries import determine_boundaries
from entroppy.resolution.state import RejectionReason
from entroppy.resolution.solver import Pass
from entroppy.utils.helpers import cached_word_frequency

if TYPE_CHECKING:
    from entroppy.resolution.state import DictionaryState
    from entroppy.resolution.solver import PassContext


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
        # Iterate through all raw typos
        for typo, word_list in state.raw_typo_map.items():
            # Skip if already covered
            if state.is_typo_covered(typo):
                continue

            # Get unique words for this typo
            unique_words = list(set(word_list))

            # Process based on number of words
            if len(unique_words) == 1:
                self._process_single_word(state, typo, unique_words[0])
            else:
                self._process_collision(state, typo, unique_words)

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
        boundaries_to_try = self._get_boundary_order(natural_boundary)

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
        from collections import defaultdict

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
        boundaries_to_try = self._get_boundary_order(boundary)

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
        boundaries_to_try = self._get_boundary_order(boundary)

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
        return self.context.exclusion_matcher.matches_correction(correction)

    @staticmethod
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
