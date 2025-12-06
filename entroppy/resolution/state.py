"""Dictionary state management for the iterative solver."""

from collections import defaultdict
import time

from entroppy.core import BoundaryType, Correction
from entroppy.resolution.history import (
    CorrectionHistoryEntry,
    GraveyardHistoryEntry,
    PatternHistoryEntry,
    RejectionReason,
)
from entroppy.resolution.state_types import DebugTraceEntry, GraveyardEntry

# Re-export for backward compatibility
__all__ = ["DictionaryState", "DebugTraceEntry", "GraveyardEntry", "RejectionReason"]
from entroppy.utils.debug import DebugTypoMatcher


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
        self.is_dirty = True  # Start dirty to trigger first iteration
        self.current_iteration = 0

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
        from entroppy.resolution.state_caching import StateCaching  # noqa: PLC0415

        self._caching = StateCaching()

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
        if self._is_debug_target(typo, word, boundary):
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
        self._caching._uncovered_typos.discard(typo)
        # Invalidate pattern coverage cache for this typo (coverage may have changed)
        self._caching.invalidate_pattern_coverage_for_typo(typo)

        # Track comprehensive history if enabled
        if self.debug_corrections:
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
        if self._is_debug_target(typo, word, boundary):
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
        if not self._coverage_map.get(typo) and not self._caching.is_typo_covered_by_pattern(
            typo, self.active_patterns
        ):
            self._caching._uncovered_typos.add(typo)
        # Invalidate pattern coverage cache for this typo (coverage may have changed)
        self._caching.invalidate_pattern_coverage_for_typo(typo)

        # Track comprehensive history if enabled
        if self.debug_corrections:
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
        if self._is_debug_target(typo, word, boundary):
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
        self._caching.invalidate_pattern_coverage_cache()

        # Track comprehensive history if enabled
        if self.debug_patterns:
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
        if self._is_debug_target(typo, word, boundary):
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
        self._caching.invalidate_pattern_coverage_cache()

        # Track comprehensive history if enabled
        if self.debug_patterns:
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
        if self._is_debug_target(typo, word, boundary):
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
        # Check cache first
        if typo in self._caching._pattern_coverage_cache:
            return self._caching._pattern_coverage_cache[typo]

        # Check if any active correction covers this typo (fast: O(1))
        if typo in self._coverage_map and self._coverage_map[typo]:
            self._caching._pattern_coverage_cache[typo] = True
            return True

        # Check if any pattern covers this typo (slow: O(P) where P=2000-2300)
        # For now, exact match (patterns will be enhanced in PatternGeneralizationPass)
        for pattern_typo, _, _ in self.active_patterns:
            if pattern_typo == typo:
                self._caching._pattern_coverage_cache[typo] = True
                return True

        # Not covered
        self._caching._pattern_coverage_cache[typo] = False
        return False

    def clear_dirty_flag(self) -> None:
        """Mark the state as clean (no changes in this iteration)."""
        self.is_dirty = False

    def start_iteration(self) -> None:
        """Mark the start of a new iteration."""
        self.current_iteration += 1
        self.clear_dirty_flag()
        # Clear false trigger cache at start of each iteration
        # (validation/source sets don't change, but corrections/patterns do)
        self._caching.clear_false_trigger_cache()

    def get_debug_summary(self) -> str:
        """Get a summary of debug trace for reporting.

        Returns:
            Formatted string with debug trace
        """
        if not self.debug_trace:
            return "No debug targets tracked."

        lines = ["Debug Trace:"]
        for entry in self.debug_trace:
            lines.append(
                f"  Iter {entry.iteration} [{entry.pass_name}] "
                f"{entry.action}: {entry.typo} -> {entry.word} ({entry.boundary.value})"
            )
            if entry.reason:
                lines.append(f"    Reason: {entry.reason}")

        return "\n".join(lines)

    def get_formatted_cache(self) -> dict[Correction, str]:
        """Get the formatted cache for corrections.

        Returns:
            Dictionary mapping corrections to their formatted typo strings
        """
        return self._formatted_cache

    def _is_debug_target(self, typo: str, word: str, boundary: BoundaryType) -> bool:
        """Check if a correction should be tracked for debugging.

        Args:
            typo: The typo string
            word: The correct word
            boundary: The boundary type

        Returns:
            True if this should be tracked
        """
        if word in self.debug_words:
            return True

        if self.debug_typo_matcher and self.debug_typo_matcher.matches(typo, boundary):
            return True

        return False
