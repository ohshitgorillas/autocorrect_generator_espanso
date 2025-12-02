"""Pattern Generalization Pass - compresses specific corrections into patterns."""

from typing import TYPE_CHECKING

from entroppy.core import BoundaryType
from entroppy.core.patterns import generalize_patterns
from entroppy.platforms.base import MatchDirection
from entroppy.resolution.solver import Pass

if TYPE_CHECKING:
    from entroppy.resolution.state import DictionaryState
    from entroppy.resolution.solver import PassContext


class PatternGeneralizationPass(Pass):
    """Compresses specific corrections into generalized patterns.

    This pass:
    1. Scans active corrections for repeated prefix/suffix patterns
    2. Validates patterns against the validation set
    3. Promotes valid patterns to active_patterns
    4. Removes specific corrections covered by patterns

    Example:
        - "aer" -> "are", "ehr" -> "her", "oer" -> "ore" (all have *er -> *re pattern)
        - Creates pattern "*er" -> "*re"
        - Removes the specific corrections
    """

    @property
    def name(self) -> str:
        """Return the name of this pass."""
        return "PatternGeneralization"

    def run(self, state: "DictionaryState") -> None:
        """Run the pattern generalization pass.

        Args:
            state: The dictionary state to modify
        """
        if not state.active_corrections:
            return

        # Get platform match direction
        match_direction = MatchDirection.LEFT_TO_RIGHT
        if self.context.platform:
            constraints = self.context.platform.get_constraints()
            match_direction = constraints.match_direction

        # Run pattern extraction and validation
        corrections_list = list(state.active_corrections)

        try:
            patterns, corrections_to_remove, pattern_replacements, rejected_patterns = (
                generalize_patterns(
                    corrections_list,
                    self.context.validation_set,
                    self.context.source_words_set,
                    self.context.min_typo_length,
                    match_direction,
                    verbose=False,
                    debug_words=state.debug_words,
                    debug_typo_matcher=state.debug_typo_matcher,
                    jobs=1,  # Single-threaded for now (can be parallelized later)
                )
            )

            # Add validated patterns to active set
            for pattern in patterns:
                typo, word, boundary = pattern
                # Check if already in graveyard
                if not state.is_in_graveyard(typo, word, boundary):
                    state.add_pattern(typo, word, boundary, self.name)

            # Remove corrections that are covered by patterns
            for correction in corrections_to_remove:
                typo, word, boundary = correction
                state.remove_correction(
                    typo,
                    word,
                    boundary,
                    self.name,
                    "Covered by pattern",
                )

        except Exception:
            # If pattern generalization fails, continue without patterns
            # This ensures the solver can continue even if pattern logic has issues
            pass
