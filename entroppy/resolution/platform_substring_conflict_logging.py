"""Debug logging functions for platform substring conflict detection."""

from typing import TYPE_CHECKING

from entroppy.core import Correction
from entroppy.utils.debug import is_debug_correction, log_debug_correction

if TYPE_CHECKING:
    from entroppy.utils.debug import DebugTypoMatcher


def log_platform_substring_conflict(
    removed_correction: Correction,
    conflicting_correction: Correction,
    formatted_removed: str,
    formatted_conflicting: str,
    reason: str,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
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
    """
    if is_debug_correction(removed_correction, debug_words, debug_typo_matcher):
        # Unpack for use in log message
        conflicting_typo, conflicting_word, conflicting_boundary = conflicting_correction

        log_debug_correction(
            removed_correction,
            f"REMOVED - platform substring conflict: '{formatted_removed}' conflicts with "
            f"'{formatted_conflicting}' ({conflicting_typo} → {conflicting_word}, "
            f"{conflicting_boundary.value} boundary). {reason}",
            debug_words,
            debug_typo_matcher,
            "PlatformSubstringConflicts",
        )
