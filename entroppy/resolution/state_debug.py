"""Debug helper functions for DictionaryState.

This module provides helper functions for debug-related functionality
to keep the main state.py file focused on core state management.
"""

from entroppy.core.boundaries import BoundaryType


def get_debug_summary(debug_trace: list) -> str:
    """Get a summary of debug trace for reporting.

    Args:
        debug_trace: List of DebugTraceEntry objects

    Returns:
        Formatted string with debug trace
    """
    if not debug_trace:
        return "No debug targets tracked."

    lines = ["Debug Trace:"]
    for entry in debug_trace:
        lines.append(
            f"  Iter {entry.iteration} [{entry.pass_name}] "
            f"{entry.action}: {entry.typo} -> {entry.word} ({entry.boundary.value})"
        )
        if entry.reason:
            lines.append(f"    Reason: {entry.reason}")

    return "\n".join(lines)


def is_debug_target(
    typo: str,
    word: str,
    boundary: BoundaryType,
    debug_words: set[str],
    debug_typo_matcher,
) -> bool:
    """Check if a correction should be tracked for debugging.

    Args:
        typo: The typo string
        word: The correct word
        boundary: The boundary type
        debug_words: Set of words to track
        debug_typo_matcher: Matcher for debug typos

    Returns:
        True if this should be tracked
    """
    if word in debug_words:
        return True

    if debug_typo_matcher and debug_typo_matcher.matches(typo, boundary):
        return True

    return False
