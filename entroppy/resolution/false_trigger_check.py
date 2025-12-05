"""False trigger checking logic for boundary selection."""

from entroppy.core import BoundaryType
from entroppy.core.boundaries import (
    BoundaryIndex,
    is_substring_of_any,
    would_trigger_at_end,
    would_trigger_at_start,
)

from .boundary_utils import _check_typo_in_target_word


def _collect_trigger_checks(
    typo: str,
    validation_index: BoundaryIndex,
    source_index: BoundaryIndex,
    target_word: str | None,
) -> tuple[bool, bool, bool, bool, bool, bool, bool, bool, bool]:
    """Collect all trigger checks for a typo.

    Args:
        typo: The typo string
        validation_index: Boundary index for validation set
        source_index: Boundary index for source words
        target_word: Optional target word to check against

    Returns:
        Tuple of (would_trigger_start_target, would_trigger_end_target, is_substring_target,
                 would_trigger_start_val, would_trigger_end_val, is_substring_val,
                 would_trigger_start_src, would_trigger_end_src, is_substring_src)
    """
    # FIRST: Check target word (highest priority - most critical check)
    would_trigger_start_target, would_trigger_end_target, is_substring_target = (
        _check_typo_in_target_word(typo, target_word)
    )

    # Check validation and source words
    would_trigger_start_val = would_trigger_at_start(typo, validation_index)
    would_trigger_end_val = would_trigger_at_end(typo, validation_index)
    is_substring_val = is_substring_of_any(typo, validation_index)

    would_trigger_start_src = would_trigger_at_start(typo, source_index)
    would_trigger_end_src = would_trigger_at_end(typo, source_index)
    is_substring_src = is_substring_of_any(typo, source_index)

    return (
        would_trigger_start_target,
        would_trigger_end_target,
        is_substring_target,
        would_trigger_start_val,
        would_trigger_end_val,
        is_substring_val,
        would_trigger_start_src,
        would_trigger_end_src,
        is_substring_src,
    )


def _determine_false_trigger_for_boundary(
    boundary: BoundaryType,
    would_trigger_start: bool,
    would_trigger_end: bool,
    is_substring: bool,
    would_trigger_start_target: bool,
    would_trigger_end_target: bool,
    is_substring_target: bool,
    would_trigger_start_val: bool,
    would_trigger_end_val: bool,
    is_substring_val: bool,
    would_trigger_start_src: bool,
    would_trigger_end_src: bool,
    is_substring_src: bool,
) -> tuple[bool, str | None]:
    """Determine if boundary would cause false triggers and the reason.

    Args:
        boundary: The boundary type to check
        would_trigger_start: Combined start trigger check
        would_trigger_end: Combined end trigger check
        is_substring: Combined substring check
        would_trigger_start_target: Target word start trigger
        would_trigger_end_target: Target word end trigger
        is_substring_target: Target word substring
        would_trigger_start_val: Validation start trigger
        would_trigger_end_val: Validation end trigger
        is_substring_val: Validation substring
        would_trigger_start_src: Source start trigger
        would_trigger_end_src: Source end trigger
        is_substring_src: Source substring

    Returns:
        Tuple of (would_cause, reason)
    """
    if boundary == BoundaryType.NONE:
        # NONE matches anywhere, so false trigger if typo appears anywhere
        would_cause = would_trigger_start or would_trigger_end or is_substring
        if would_cause:
            if would_trigger_start_target or would_trigger_end_target or is_substring_target:
                reason = "typo appears in target word"
            elif would_trigger_start_val or would_trigger_end_val or is_substring_val:
                reason = "typo appears as substring in validation words"
            elif would_trigger_start_src or would_trigger_end_src or is_substring_src:
                reason = "typo appears as substring in source words"
            else:
                reason = "typo appears as substring"
        else:
            reason = None
    elif boundary == BoundaryType.LEFT:
        # LEFT matches at word start, so false trigger if typo appears as prefix
        would_cause = would_trigger_start
        reason = "typo appears as prefix" if would_cause else None
    elif boundary == BoundaryType.RIGHT:
        # RIGHT matches at word end, so false trigger if typo appears as suffix
        would_cause = would_trigger_end
        reason = "typo appears as suffix" if would_cause else None
    elif boundary == BoundaryType.BOTH:
        # BOTH matches as standalone word only, so it would NOT cause false triggers
        would_cause = False
        reason = None
    else:
        # Unknown boundary type, be conservative
        would_cause = True
        reason = "unknown boundary type"

    return would_cause, reason


def _would_cause_false_trigger(
    typo: str,
    boundary: BoundaryType,
    validation_index: BoundaryIndex,
    source_index: BoundaryIndex,
    target_word: str | None = None,
    return_details: bool = False,
) -> bool | tuple[bool, dict[str, bool | str | None]]:
    """Check if a boundary would cause false triggers (garbage corrections).

    A false trigger occurs when the typo would match validation/source words incorrectly
    due to the boundary restrictions (or lack thereof).

    Args:
        typo: The typo string
        boundary: The boundary type to check
        validation_index: Boundary index for validation set
        source_index: Boundary index for source words
        target_word: Optional target word to check against (highest priority check)
        return_details: If True, return tuple of (bool, details_dict) instead of just bool

    Returns:
        If return_details is False: True if the boundary would cause false triggers, False otherwise
        If return_details is True: Tuple of (would_cause_false_trigger, details_dict) where
            details_dict contains breakdown of checks performed
    """
    # Collect all trigger checks
    (
        would_trigger_start_target,
        would_trigger_end_target,
        is_substring_target,
        would_trigger_start_val,
        would_trigger_end_val,
        is_substring_val,
        would_trigger_start_src,
        would_trigger_end_src,
        is_substring_src,
    ) = _collect_trigger_checks(typo, validation_index, source_index, target_word)

    # Combine checks: target word check takes precedence
    would_trigger_start = (
        would_trigger_start_target or would_trigger_start_val or would_trigger_start_src
    )
    would_trigger_end = would_trigger_end_target or would_trigger_end_val or would_trigger_end_src
    is_substring = is_substring_target or is_substring_val or is_substring_src

    # Determine if boundary would cause false triggers
    would_cause, reason = _determine_false_trigger_for_boundary(
        boundary,
        would_trigger_start,
        would_trigger_end,
        is_substring,
        would_trigger_start_target,
        would_trigger_end_target,
        is_substring_target,
        would_trigger_start_val,
        would_trigger_end_val,
        is_substring_val,
        would_trigger_start_src,
        would_trigger_end_src,
        is_substring_src,
    )

    if return_details:
        details = {
            "would_cause_false_trigger": would_cause,
            "reason": reason,
            "would_trigger_start": would_trigger_start,
            "would_trigger_end": would_trigger_end,
            "is_substring": is_substring,
            "would_trigger_start_target": would_trigger_start_target,
            "would_trigger_end_target": would_trigger_end_target,
            "is_substring_target": is_substring_target,
            "would_trigger_start_val": would_trigger_start_val,
            "would_trigger_end_val": would_trigger_end_val,
            "is_substring_val": is_substring_val,
            "would_trigger_start_src": would_trigger_start_src,
            "would_trigger_end_src": would_trigger_end_src,
            "is_substring_src": is_substring_src,
        }
        return would_cause, details

    return would_cause


def _check_false_trigger_with_details(
    typo: str,
    boundary: BoundaryType,
    validation_index: BoundaryIndex,
    source_index: BoundaryIndex,
    target_word: str | None = None,
) -> tuple[bool, dict[str, bool | str | None]]:
    """Check if boundary would cause false triggers and return details.

    This helper function eliminates duplication between boundary_selection.py
    and correction_processing.py by centralizing the call pattern.

    Args:
        typo: The typo string
        boundary: The boundary type to check
        validation_index: Boundary index for validation set
        source_index: Boundary index for source words
        target_word: Optional target word to check against

    Returns:
        Tuple of (would_cause_false_trigger, details_dict)
    """
    result = _would_cause_false_trigger(
        typo,
        boundary,
        validation_index,
        source_index,
        target_word=target_word,
        return_details=True,
    )
    # _would_cause_false_trigger with return_details=True always returns tuple
    assert isinstance(result, tuple)
    return result
