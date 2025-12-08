"""Debug logging functions for platform substring conflict detection."""

from typing import TYPE_CHECKING

from entroppy.core import Correction
from entroppy.core.patterns.data_models import PlatformConflict
from entroppy.utils.debug import is_debug_correction, log_debug_correction

if TYPE_CHECKING:
    from entroppy.resolution.state import DictionaryState
    from entroppy.utils.debug import DebugTypoMatcher


def log_platform_substring_conflict(
    removed_correction: Correction,
    conflicting_correction: Correction,
    formatted_removed: str,
    formatted_conflicting: str,
    reason: str,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
    state: "DictionaryState | None" = None,
) -> None:
    """Log that a correction was removed due to a platform substring conflict.

    Args:
        removed_correction: The correction that was removed
        conflicting_correction: The correction that conflicts with it
        formatted_removed: The formatted typo string for the removed correction
        formatted_conflicting: The formatted typo string for the conflicting correction
        reason: The reason for removal
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos
        state: Optional dictionary state for storing structured debug data
    """
    # Unpack for use in log message and structured data
    conflicting_typo, conflicting_word, conflicting_boundary = conflicting_correction

    if is_debug_correction(removed_correction, debug_words, debug_typo_matcher):
        log_debug_correction(
            removed_correction,
            f"REMOVED - platform substring conflict: '{formatted_removed}' conflicts with "
            f"'{formatted_conflicting}' ({conflicting_typo} → {conflicting_word}, "
            f"{conflicting_boundary.value} boundary). {reason}",
            debug_words,
            debug_typo_matcher,
            "PlatformSubstringConflicts",
        )

    # Store structured data if state is provided
    if state is not None:
        removed_typo, removed_word, removed_boundary = removed_correction
        conflict = PlatformConflict(
            typo=removed_typo,
            word=removed_word,
            boundary=removed_boundary.value,
            conflict_type="substring_conflict",
            details=f"'{formatted_removed}' conflicts with '{formatted_conflicting}' "
            f"({conflicting_typo} → {conflicting_word}, {conflicting_boundary.value} boundary)",
            result="REMOVED",
            iteration=state.current_iteration,
        )
        state.platform_conflicts.append(conflict)
