"""Boundary selection logic for collision resolution."""

from entroppy.core import BoundaryType
from entroppy.core.boundaries import BoundaryIndex
from entroppy.utils.debug import DebugTypoMatcher, is_debug_typo, log_debug_typo

from .boundary_logging import (
    _determine_boundary_order,
    _log_boundary_order_selection,
    _log_boundary_rejection,
    _log_fallback_boundary,
    _should_debug_boundary_selection,
)
from .false_trigger_check import _check_false_trigger_with_details


def choose_boundary_for_typo(
    typo: str,
    validation_index: BoundaryIndex,
    source_index: BoundaryIndex,
    debug_words: set[str] | None = None,
    debug_typo_matcher: DebugTypoMatcher | None = None,
    word: str | None = None,
) -> BoundaryType:
    """Choose the least restrictive boundary that doesn't produce garbage corrections.

    Tries boundaries from least restrictive to most restrictive, but adjusts the order
    based on the typo's relationship to the target word:
    - If typo is a suffix of target word → skip LEFT (incompatible)
    - If typo is a prefix of target word → skip RIGHT (incompatible)
    - If typo is a middle substring → skip LEFT and RIGHT (both incompatible)
    - Otherwise → try all boundaries in default order

    Args:
        typo: The typo string
        validation_index: Boundary index for validation set
        source_index: Boundary index for source words
        debug_words: Set of words to debug (exact matches)
        debug_typo_matcher: Matcher for debug typos (with wildcards/boundaries)
        word: Optional word associated with this typo (for debug logging)

    Returns:
        The chosen boundary type (least restrictive that doesn't cause false triggers)
    """
    # Check if we should debug this boundary selection
    is_debug = _should_debug_boundary_selection(typo, word, debug_words, debug_typo_matcher)

    # Determine boundary order based on target word relationship
    boundary_order, relationship = _determine_boundary_order(typo, word)

    # Log boundary order selection if debugging
    if is_debug:
        _log_boundary_order_selection(typo, word, relationship, debug_typo_matcher)

    # Check each boundary from least to most restrictive
    for boundary in boundary_order:
        # pylint: disable=duplicate-code
        # Intentional duplication: Same false trigger check pattern used in multiple places
        # (worker functions, sequential functions in candidate_selection.py) to ensure
        # consistent validation logic across all code paths where corrections are added.
        would_cause, details = _check_false_trigger_with_details(
            typo,
            boundary,
            validation_index,
            source_index,
            target_word=word,
        )
        if not would_cause:
            # Boundary selected - logging will be done by log_boundary_selection_details
            # which is called from collision.py after processing
            return boundary

        # Log why this boundary was rejected with concrete examples
        if is_debug:
            _log_boundary_rejection(
                typo,
                word,
                boundary,
                details,
                validation_index,
                source_index,
                debug_typo_matcher,
            )

    # If all boundaries would cause false triggers, return BOTH as safest fallback
    # (most restrictive, least likely to cause issues)
    if is_debug:
        _log_fallback_boundary(typo, word, debug_typo_matcher)
    return BoundaryType.BOTH


def log_boundary_selection_details(
    typo: str,
    word: str | None,
    boundary: BoundaryType,
    details: dict,
    debug_typo_matcher: DebugTypoMatcher | None,
) -> None:
    """Log boundary selection details for debug typos."""
    if not debug_typo_matcher or not is_debug_typo(typo, boundary, debug_typo_matcher):
        return

    word_info = f" (word: {word})" if word else ""
    safety_details = []

    if (
        not details["would_trigger_start"]
        and not details["would_trigger_end"]
        and not details["is_substring"]
    ):
        safety_details.append("typo doesn't appear in validation or source words")
    else:
        if boundary == BoundaryType.NONE:
            safety_details.append(
                "NONE boundary would match anywhere, but typo doesn't appear as substring"
            )
        elif boundary == BoundaryType.LEFT:
            safety_details.append(
                "LEFT boundary requires word start, typo doesn't appear as prefix"
            )
        elif boundary == BoundaryType.RIGHT:
            safety_details.append("RIGHT boundary requires word end, typo doesn't appear as suffix")
        elif boundary == BoundaryType.BOTH:
            safety_details.append(
                "BOTH boundary requires standalone word, prevents all substring matches"
            )

    check_parts = []
    if not details["would_trigger_start"]:
        check_parts.append("not a prefix")
    if not details["would_trigger_end"]:
        check_parts.append("not a suffix")
    if not details["is_substring"]:
        check_parts.append("not a substring")
    if check_parts:
        safety_details.append(f"checks passed: {', '.join(check_parts)}")

    log_debug_typo(
        typo,
        f"Selected boundary '{boundary.value}'{word_info} - {'; '.join(safety_details)}",
        debug_typo_matcher.get_matching_patterns(typo, boundary),
        "Stage 3",
    )
