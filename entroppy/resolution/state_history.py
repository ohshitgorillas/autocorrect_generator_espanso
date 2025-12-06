"""History tracking helpers for DictionaryState.

This module provides helper functions for tracking correction and pattern history
to keep the main state.py file focused on core state management.
"""

import time

from entroppy.core.boundaries import BoundaryType
from entroppy.resolution.history import CorrectionHistoryEntry, PatternHistoryEntry
from entroppy.resolution.state_types import DebugTraceEntry


def create_correction_history_entry(
    iteration: int,
    pass_name: str,
    action: str,
    typo: str,
    word: str,
    boundary: BoundaryType,
    reason: str | None = None,
) -> CorrectionHistoryEntry:
    """Create a correction history entry.

    Args:
        iteration: Current iteration number
        pass_name: Name of the pass
        action: Action taken ("added" or "removed")
        typo: The typo string
        word: The correct word
        boundary: The boundary type
        reason: Optional reason for the action

    Returns:
        CorrectionHistoryEntry
    """
    return CorrectionHistoryEntry(
        iteration=iteration,
        pass_name=pass_name,
        action=action,
        typo=typo,
        word=word,
        boundary=boundary,
        reason=reason,
        timestamp=time.time(),
    )


def create_pattern_history_entry(
    iteration: int,
    pass_name: str,
    action: str,
    typo: str,
    word: str,
    boundary: BoundaryType,
    reason: str | None = None,
) -> PatternHistoryEntry:
    """Create a pattern history entry.

    Args:
        iteration: Current iteration number
        pass_name: Name of the pass
        action: Action taken ("added" or "removed")
        typo: The pattern typo string
        word: The pattern word
        boundary: The boundary type
        reason: Optional reason for the action

    Returns:
        PatternHistoryEntry
    """
    return PatternHistoryEntry(
        iteration=iteration,
        pass_name=pass_name,
        action=action,
        typo=typo,
        word=word,
        boundary=boundary,
        reason=reason,
        timestamp=time.time(),
    )


def create_debug_trace_entry(
    iteration: int,
    pass_name: str,
    action: str,
    typo: str,
    word: str,
    boundary: BoundaryType,
    reason: str | None = None,
) -> DebugTraceEntry:
    """Create a debug trace entry.

    Args:
        iteration: Current iteration number
        pass_name: Name of the pass
        action: Action taken
        typo: The typo string
        word: The correct word
        boundary: The boundary type
        reason: Optional reason

    Returns:
        DebugTraceEntry
    """
    return DebugTraceEntry(
        iteration=iteration,
        pass_name=pass_name,
        action=action,
        typo=typo,
        word=word,
        boundary=boundary,
        reason=reason,
    )
