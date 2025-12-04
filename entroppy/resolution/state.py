"""Dictionary state management for the iterative solver."""

from collections import defaultdict
from dataclasses import dataclass
from enum import Enum

from entroppy.core import BoundaryType, Correction
from entroppy.utils.debug import DebugTypoMatcher


class RejectionReason(Enum):
    """Reasons why a correction was rejected."""

    COLLISION_AMBIGUOUS = "ambiguous_collision"
    TOO_SHORT = "too_short"
    BLOCKED_BY_CONFLICT = "blocked_by_conflict"
    PLATFORM_CONSTRAINT = "platform_constraint"
    PATTERN_VALIDATION_FAILED = "pattern_validation_failed"
    EXCLUDED_BY_PATTERN = "excluded_by_pattern"
    FALSE_TRIGGER = "false_trigger"


@dataclass
class GraveyardEntry:
    """A rejected correction with context."""

    typo: str
    word: str
    boundary: BoundaryType
    reason: RejectionReason
    blocker: str | None = None  # What blocked this (e.g., conflicting typo/word)
    iteration: int = 0


@dataclass
class DebugTraceEntry:
    """A log entry for debug tracing."""

    iteration: int
    pass_name: str
    action: str  # "added", "removed", "promoted_to_pattern", etc.
    typo: str
    word: str
    boundary: BoundaryType
    reason: str | None = None


class DictionaryState:
    """Central state manager for the iterative solver.

    This is the "Source of Truth" for the dictionary optimization process.
    It manages:
    - Raw typo map from Stage 2
    - Active corrections (currently valid)
    - Active patterns (generalized corrections)
    - The Graveyard (rejected items with reasons)
    - Debug context and trace logging

    Attributes:
        raw_typo_map: Original typo map from Stage 2 (typo -> [words])
        active_corrections: Current set of valid corrections
        active_patterns: Current set of valid patterns
        graveyard: Registry of rejected corrections
        debug_words: Set of words to track for debugging
        debug_typo_matcher: Matcher for debug typos
        debug_trace: Log of all changes affecting debug targets
        is_dirty: Flag indicating if state changed in last iteration
    """

    def __init__(
        self,
        raw_typo_map: dict[str, list[str]],
        debug_words: set[str] | None = None,
        debug_typo_matcher: DebugTypoMatcher | None = None,
    ) -> None:
        """Initialize the dictionary state.

        Args:
            raw_typo_map: The typo map from Stage 2
            debug_words: Optional set of words to track
            debug_typo_matcher: Optional matcher for debug typos
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

        # Track what corrections cover which raw typos
        self._coverage_map: dict[str, set[Correction]] = defaultdict(set)

        # Track pattern replacements for reporting
        self.pattern_replacements: dict[Correction, list[Correction]] = {}

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
    ) -> None:
        """Add a correction to the graveyard.

        Args:
            typo: The typo string
            word: The correct word
            boundary: The boundary type
            reason: Why this was rejected
            blocker: Optional identifier of what blocked this
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

        # Log if this is a debug target
        if self._is_debug_target(typo, word, boundary):
            self.debug_trace.append(
                DebugTraceEntry(
                    iteration=self.current_iteration,
                    pass_name="graveyard",
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
        # Check if any active correction covers this typo
        if typo in self._coverage_map and self._coverage_map[typo]:
            return True

        # Check if any pattern covers this typo
        for pattern_typo, _, _ in self.active_patterns:
            if self._pattern_matches_typo(pattern_typo, typo):
                return True

        return False

    def clear_dirty_flag(self) -> None:
        """Mark the state as clean (no changes in this iteration)."""
        self.is_dirty = False

    def start_iteration(self) -> None:
        """Mark the start of a new iteration."""
        self.current_iteration += 1
        self.clear_dirty_flag()

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

    @staticmethod
    def _pattern_matches_typo(pattern: str, typo: str) -> bool:
        """Check if a pattern matches a typo.

        Args:
            pattern: The pattern string (may contain wildcards)
            typo: The typo string

        Returns:
            True if the pattern matches the typo
        """
        # For now, exact match (patterns will be enhanced in PatternGeneralizationPass)
        return pattern == typo
