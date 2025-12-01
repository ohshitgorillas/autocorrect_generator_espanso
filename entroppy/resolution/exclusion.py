"""Exclusion handling for collision resolution."""

from typing import TYPE_CHECKING

from entroppy.core import Correction
from entroppy.matching import ExclusionMatcher
from entroppy.utils.debug import log_if_debug_correction

if TYPE_CHECKING:
    from entroppy.utils.debug import DebugTypoMatcher


def handle_exclusion(
    correction: Correction,
    exclusion_matcher: ExclusionMatcher,
    debug_words: set[str],
    debug_typo_matcher: "DebugTypoMatcher | None",
) -> tuple[bool, str | None]:
    """Check if a correction should be excluded and log if needed.

    Args:
        correction: The correction to check
        exclusion_matcher: Matcher for exclusion rules
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos

    Returns:
        Tuple of (should_exclude, matching_rule). matching_rule is None if not excluded.
    """
    if exclusion_matcher.should_exclude(correction):
        matching_rule = exclusion_matcher.get_matching_rule(correction)
        log_if_debug_correction(
            correction,
            f"EXCLUDED by rule: {matching_rule}",
            debug_words,
            debug_typo_matcher,
            "Stage 3",
        )
        return True, matching_rule
    return False, None
