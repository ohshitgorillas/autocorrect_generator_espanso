"""Dictionary state management for the iterative solver."""

from collections import defaultdict
import time
from typing import TYPE_CHECKING

from entroppy.core import BoundaryType, Correction
from entroppy.resolution.history import (
    CorrectionHistoryEntry,
    GraveyardHistoryEntry,
    PatternHistoryEntry,
    RejectionReason,
)
from entroppy.resolution.state_caching import StateCaching
from entroppy.resolution.state_debug import is_debug_target
from entroppy.resolution.state_types import DebugTraceEntry, GraveyardEntry
from entroppy.utils.debug import DebugTypoMatcher, log_if_debug_correction

if TYPE_CHECKING:
    pass


class DictionaryState:
    """Central state manager for the iterative solver.

    Manages raw typos, active corrections/patterns, graveyard, and debug context.
    This is the "Source of Truth" for the dictionary optimization process.
    """

    def __init__(
        self,
        raw_typo_map: dict[str, list[str]],
        debug_words: set[str] | None = None,
        debug_typo_matcher: DebugTypoMatcher | None = None,
        debug_graveyard: bool = False,
        debug_patterns: bool = False,
        debug_corrections: bool = False,
    ) -> None:
        """Initialize the dictionary state.

        Args:
            raw_typo_map: The typo map from Stage 2
            debug_words: Optional set of words to track
            debug_typo_matcher: Optional matcher for debug typos
            debug_graveyard: Whether to track comprehensive graveyard history
            debug_patterns: Whether to track comprehensive pattern history
            debug_corrections: Whether to track comprehensive correction history
        """
        self.raw_typo_map = raw_typo_map
        self.active_corrections: set[Correction] = set()
        self.active_patterns: set[Correction] = set()
        self.graveyard: dict[tuple[str, str, BoundaryType], GraveyardEntry] = {}
        self.debug_words = debug_words or set()
        self.debug_typo_matcher = debug_typo_matcher
        self.debug_trace: list[DebugTraceEntry] = []
        self.debug_messages: list[str] = []  # Collect Stage 3+ debug messages for reports
        self.is_dirty = True  # Start dirty to trigger first iteration
        self.current_iteration = 0

        # Structured debug data for reports (populated during execution)
        self.pattern_extractions: list = []
        self.pattern_validations: list = []
        self.platform_conflicts: list = []
        self.ranking_info: list = []
        self.stage2_word_events: list = []  # Stage 2 word processing events

        # Debug flags for comprehensive history tracking
        self.debug_graveyard = debug_graveyard
        self.debug_patterns = debug_patterns
        self.debug_corrections = debug_corrections

        # History tracking (only populated if debug flags enabled)
        self.graveyard_history: list[GraveyardHistoryEntry] = []
        self.pattern_history: list[PatternHistoryEntry] = []
        self.correction_history: list[CorrectionHistoryEntry] = []

        # Track what corrections cover which raw typos
        self._coverage_map: dict[str, set[Correction]] = defaultdict(set)

        # Track pattern replacements for reporting
        self.pattern_replacements: dict[Correction, list[Correction]] = {}

        # Cache for formatted correction strings (typo with boundary markers)
        self._formatted_cache: dict[Correction, str] = {}

        # Optimization caches for CandidateSelection pass
        self.caching = StateCaching()

    def is_in_graveyard(
        self,
        typo: str,
        word: str,
        boundary: BoundaryType,
    ) -> bool:
        """Check if a correction is in the graveyard.

        Args:
            typo: The typo string
            word: The correct word
            boundary: The boundary type

        Returns:
            True if this correction has been rejected
        """
        return (typo, word, boundary) in self.graveyard

    def is_rejected_for_platform_constraint(
        self,
        typo: str,
        word: str,
    ) -> bool:
        """Check if a typo+word combination was rejected for platform constraints.

        Platform constraint rejections (like substring conflicts) apply to ALL boundaries
        for that typo+word combination, so we should never retry with a different boundary.

        Args:
            typo: The typo string
            word: The correct word

        Returns:
            True if this typo+word was rejected for platform constraints with any boundary
        """
        for (g_typo, g_word, _), entry in self.graveyard.items():
            if (
                g_typo == typo
                and g_word == word
                and entry.reason == RejectionReason.PLATFORM_CONSTRAINT
            ):
                return True
        return False

    def add_to_graveyard(
        self,
        typo: str,
        word: str,
        boundary: BoundaryType,
        reason: RejectionReason,
        blocker: str | None = None,
        pass_name: str = "unknown",
    ) -> None:
        """Add a correction to the graveyard.

        Args:
            typo: The typo string
            word: The correct word
            boundary: The boundary type
            reason: Why this was rejected
            blocker: Optional identifier of what blocked this
            pass_name: Name of the pass adding this to graveyard
        """
        entry = GraveyardEntry(
            typo=typo,
            word=word,
            boundary=boundary,
            reason=reason,
            blocker=blocker,
            iteration=self.current_iteration,
        )
        self.graveyard[(typo, word, boundary)] = entry

        # Track comprehensive history if enabled
        if self.debug_graveyard:
            self.graveyard_history.append(
                GraveyardHistoryEntry(
                    iteration=self.current_iteration,
                    pass_name=pass_name,
                    typo=typo,
                    word=word,
                    boundary=boundary,
                    reason=reason,
                    blocker=blocker,
                    timestamp=time.time(),
                )
            )

        # Log if this is a debug target
        if is_debug_target(typo, word, boundary, self.debug_words, self.debug_typo_matcher):
            self.debug_trace.append(
                DebugTraceEntry(
                    iteration=self.current_iteration,
                    pass_name=pass_name,
                    action="rejected",
                    typo=typo,
                    word=word,
                    boundary=boundary,
                    reason=f"{reason.value}: {blocker}" if blocker else reason.value,
                )
            )

    def add_correction(
        self,
        typo: str,
        word: str,
        boundary: BoundaryType,
        pass_name: str,
    ) -> bool:
        """Add a correction to the active set.

        Args:
            typo: The typo string
            word: The correct word
            boundary: The boundary type
            pass_name: Name of the pass adding this

        Returns:
            True if the correction was added (wasn't already present)
        """
        correction = (typo, word, boundary)

        if correction in self.active_corrections:
            return False

        self.active_corrections.add(correction)
        self._coverage_map[typo].add(correction)
        self.is_dirty = True
        # Mark typo as covered (remove from uncovered set)
        self.caching.get_uncovered_typos().discard(typo)
        # Invalidate pattern coverage cache for this typo (coverage may have changed)
        self.caching.invalidate_pattern_coverage_for_typo(typo)

        # Track comprehensive history if enabled
        if self.debug_corrections:
            # pylint: disable=duplicate-code
            # Acceptable pattern: This is simple field assignment to a dataclass constructor.
            # The similar code for PatternHistoryEntry uses a different type with the same
            # field structure. Extracting this would require generic factories that add
            # complexity without benefit. The similarity is inherent to the data model design.
            self.correction_history.append(
                CorrectionHistoryEntry(
                    iteration=self.current_iteration,
                    pass_name=pass_name,
                    action="added",
                    typo=typo,
                    word=word,
                    boundary=boundary,
                    reason=None,
                    timestamp=time.time(),
                )
            )

        # Log if this is a debug target
        if is_debug_target(typo, word, boundary, self.debug_words, self.debug_typo_matcher):
            self.debug_trace.append(
                DebugTraceEntry(
                    iteration=self.current_iteration,
                    pass_name=pass_name,
                    action="added",
                    typo=typo,
                    word=word,
                    boundary=boundary,
                )
            )
            # Map pass name to stage number for logging
            stage_map = {
                "CandidateSelection": "Stage 3",
            }
            stage = stage_map.get(pass_name, "")
            if stage:
                log_if_debug_correction(
                    correction,
                    f"Added correction (boundary: {boundary.value})",
                    self.debug_words,
                    self.debug_typo_matcher,
                    stage,
                )

        return True

    def remove_correction(
        self,
        typo: str,
        word: str,
        boundary: BoundaryType,
        pass_name: str,
        reason: str | None = None,
    ) -> bool:
        """Remove a correction from the active set.

        Args:
            typo: The typo string
            word: The correct word
            boundary: The boundary type
            pass_name: Name of the pass removing this
            reason: Optional reason for removal

        Returns:
            True if the correction was removed (was present)
        """
        correction = (typo, word, boundary)

        if correction not in self.active_corrections:
            return False

        self.active_corrections.remove(correction)
        self._coverage_map[typo].discard(correction)
        self.is_dirty = True
        # If typo is no longer covered, mark it as uncovered
        if not self._coverage_map.get(typo) and not self.caching.is_typo_covered_by_pattern(
            typo, self.active_patterns
        ):
            self.caching.get_uncovered_typos().add(typo)
        # Invalidate pattern coverage cache for this typo (coverage may have changed)
        self.caching.invalidate_pattern_coverage_for_typo(typo)

        # Track comprehensive history if enabled
        if self.debug_corrections:
            # pylint: disable=duplicate-code
            # Acceptable pattern: This is simple field assignment to a dataclass constructor.
            # The similar code for PatternHistoryEntry uses a different type with the same
            # field structure. Extracting this would require generic factories that add
            # complexity without benefit. The similarity is inherent to the data model design.
            self.correction_history.append(
                CorrectionHistoryEntry(
                    iteration=self.current_iteration,
                    pass_name=pass_name,
                    action="removed",
                    typo=typo,
                    word=word,
                    boundary=boundary,
                    reason=reason,
                    timestamp=time.time(),
                )
            )

        # Log if this is a debug target
        if is_debug_target(typo, word, boundary, self.debug_words, self.debug_typo_matcher):
            self.debug_trace.append(
                DebugTraceEntry(
                    iteration=self.current_iteration,
                    pass_name=pass_name,
                    action="removed",
                    typo=typo,
                    word=word,
                    boundary=boundary,
                    reason=reason,
                )
            )

        return True

    def add_pattern(
        self,
        typo: str,
        word: str,
        boundary: BoundaryType,
        pass_name: str,
    ) -> bool:
        """Add a pattern to the active set.

        Args:
            typo: The pattern typo string
            word: The pattern word
            boundary: The boundary type
            pass_name: Name of the pass adding this

        Returns:
            True if the pattern was added (wasn't already present)
        """
        pattern = (typo, word, boundary)

        if pattern in self.active_patterns:
            return False

        self.active_patterns.add(pattern)
        self.is_dirty = True
        # Invalidate pattern coverage cache when patterns change
        self.caching.invalidate_pattern_coverage_cache()

        # Track comprehensive history if enabled
        if self.debug_patterns:
            # pylint: disable=duplicate-code
            # Acceptable pattern: This is simple field assignment to a dataclass constructor.
            # The similar code for CorrectionHistoryEntry uses a different type with the same
            # field structure. Extracting this would require generic factories that add
            # complexity without benefit. The similarity is inherent to the data model design.
            self.pattern_history.append(
                PatternHistoryEntry(
                    iteration=self.current_iteration,
                    pass_name=pass_name,
                    action="added",
                    typo=typo,
                    word=word,
                    boundary=boundary,
                    reason=None,
                    timestamp=time.time(),
                )
            )

        # Log if this is a debug target
        if is_debug_target(typo, word, boundary, self.debug_words, self.debug_typo_matcher):
            self.debug_trace.append(
                DebugTraceEntry(
                    iteration=self.current_iteration,
                    pass_name=pass_name,
                    action="added_pattern",
                    typo=typo,
                    word=word,
                    boundary=boundary,
                )
            )

        return True

    def remove_pattern(
        self,
        typo: str,
        word: str,
        boundary: BoundaryType,
        pass_name: str,
        reason: str | None = None,
    ) -> bool:
        """Remove a pattern from the active set.

        Args:
            typo: The pattern typo string
            word: The pattern word
            boundary: The boundary type
            pass_name: Name of the pass removing this
            reason: Optional reason for removal

        Returns:
            True if the pattern was removed (was present)
        """
        pattern = (typo, word, boundary)

        if pattern not in self.active_patterns:
            return False

        self.active_patterns.remove(pattern)
        self.is_dirty = True
        # Invalidate pattern coverage cache when patterns change
        self.caching.invalidate_pattern_coverage_cache()

        # Track comprehensive history if enabled
        if self.debug_patterns:
            # pylint: disable=duplicate-code
            # Acceptable pattern: This is simple field assignment to a dataclass constructor.
            # The similar code for CorrectionHistoryEntry uses a different type with the same
            # field structure. Extracting this would require generic factories that add
            # complexity without benefit. The similarity is inherent to the data model design.
            self.pattern_history.append(
                PatternHistoryEntry(
                    iteration=self.current_iteration,
                    pass_name=pass_name,
                    action="removed",
                    typo=typo,
                    word=word,
                    boundary=boundary,
                    reason=reason,
                    timestamp=time.time(),
                )
            )

        # Log if this is a debug target
        if is_debug_target(typo, word, boundary, self.debug_words, self.debug_typo_matcher):
            self.debug_trace.append(
                DebugTraceEntry(
                    iteration=self.current_iteration,
                    pass_name=pass_name,
                    action="removed_pattern",
                    typo=typo,
                    word=word,
                    boundary=boundary,
                    reason=reason,
                )
            )

        return True

    def is_typo_covered(self, typo: str) -> bool:
        """Check if a raw typo is covered by active corrections or patterns.

        Args:
            typo: The typo to check

        Returns:
            True if the typo is covered by any active correction or pattern
        """
        return self.caching.is_typo_covered(typo, self._coverage_map, self.active_patterns)

    def get_formatted_cache(self) -> dict[Correction, str]:
        """Get the formatted correction cache.

        Returns:
            Dictionary mapping corrections to their formatted typo strings
        """
        return self._formatted_cache

    def clear_dirty_flag(self) -> None:
        """Mark the state as clean (no changes in this iteration)."""
        self.is_dirty = False

    def start_iteration(self) -> None:
        """Mark the start of a new iteration."""
        self.current_iteration += 1
        self.clear_dirty_flag()
        # Clear false trigger cache and batch results at start of each iteration
        # (validation/source sets don't change, but corrections/patterns do)
        self.caching.clear_false_trigger_cache()
