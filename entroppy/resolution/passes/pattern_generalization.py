"""Pattern Generalization Pass - compresses specific corrections into patterns."""

from typing import TYPE_CHECKING

from loguru import logger

from entroppy.core.boundaries import BoundaryType
from entroppy.core.patterns import generalize_patterns
from entroppy.core.types import MatchDirection
from entroppy.resolution.solver import Pass
from entroppy.resolution.state import RejectionReason

if TYPE_CHECKING:
    from entroppy.resolution.solver import PassContext
    from entroppy.resolution.state import DictionaryState


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

    def __init__(self, context: "PassContext") -> None:
        """Initialize the pass with context and pattern extraction cache.

        Args:
            context: Shared context with resources
        """
        super().__init__(context)
        # Cache for pattern extraction results
        # Key: (typo, word, boundary, is_suffix) - correction + pattern type
        # Value: List of (typo_pattern, word_pattern, boundary, length) - extracted patterns
        self._pattern_cache: dict[
            tuple[str, str, BoundaryType, bool], list[tuple[str, str, BoundaryType, int]]
        ] = {}

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
                    self.context.filtered_validation_set,
                    self.context.source_words_set,
                    self.context.min_typo_length,
                    match_direction,
                    verbose=self.context.verbose,
                    debug_words=state.debug_words,
                    debug_typo_matcher=state.debug_typo_matcher,
                    jobs=self.context.jobs,
                    is_in_graveyard=state.is_in_graveyard,
                    pattern_cache=self._pattern_cache,
                )
            )

            # Store pattern replacements in state for reporting
            state.pattern_replacements.update(pattern_replacements)

            # Add rejected patterns to graveyard to prevent infinite loops
            for typo_pattern, word_pattern, boundary, reason in rejected_patterns:
                if not state.is_in_graveyard(typo_pattern, word_pattern, boundary):
                    state.add_to_graveyard(
                        typo_pattern,
                        word_pattern,
                        boundary,
                        RejectionReason.PATTERN_VALIDATION_FAILED,
                        blocker=reason,
                    )
                    # Log if this is a debug pattern
                    if state.debug_typo_matcher and state.debug_typo_matcher.matches(
                        typo_pattern, boundary
                    ):
                        logger.debug(
                            f"[GRAVEYARD] Added rejected pattern to graveyard: "
                            f"'{typo_pattern}' → '{word_pattern}' ({boundary.value}): {reason}"
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

        except (ValueError, KeyError, AttributeError) as e:
            # If pattern generalization fails, continue without patterns
            # This ensures the solver can continue even if pattern logic has issues
            # Catch specific exceptions that might occur during pattern processing
            if state.debug_words or (
                state.debug_typo_matcher is not None
                and hasattr(state.debug_typo_matcher, "matches")
            ):
                # Only log if debugging is enabled to avoid noise
                logger.debug(f"Pattern generalization failed: {e}")
