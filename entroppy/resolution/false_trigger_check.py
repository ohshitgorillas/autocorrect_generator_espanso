"""False trigger checking logic for boundary selection."""

from entroppy.core import BoundaryType
from entroppy.core.boundaries import (
    BoundaryIndex,
    is_substring_of_any,
    would_trigger_at_end,
    would_trigger_at_start,
)

from .boundaries.utils import _check_typo_in_target_word


def _determine_none_boundary_reason(
    would_trigger_start_target: bool,
    would_trigger_end_target: bool,
    is_substring_target: bool,
    would_trigger_start_val: bool,
    would_trigger_end_val: bool,
    is_substring_val: bool,
    would_trigger_start_src: bool,
    would_trigger_end_src: bool,
    is_substring_src: bool,
) -> str | None:
    """Determine reason for NONE boundary false trigger."""
    if would_trigger_start_target or would_trigger_end_target or is_substring_target:
        return "typo appears in target word"
    if would_trigger_start_val or would_trigger_end_val or is_substring_val:
        return "typo appears as substring in validation words"
    if would_trigger_start_src or would_trigger_end_src or is_substring_src:
        return "typo appears as substring in source words"
    return "typo appears as substring"


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
        reason = (
            _determine_none_boundary_reason(
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
            if would_cause
            else None
        )
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


def _check_false_trigger_with_details(
    typo: str,
    boundary: BoundaryType,
    validation_index: BoundaryIndex,
    source_index: BoundaryIndex,
    target_word: str | None = None,
    batch_results: dict[str, dict[str, bool]] | None = None,
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
        batch_results: Optional pre-computed batch results dict with keys:
            'start_val', 'end_val', 'substring_val', 'start_src', 'end_src', 'substring_src'

    Returns:
        Tuple of (would_cause_false_trigger, details_dict)
    """
    # Use batch results if available, otherwise compute individually
    if batch_results and typo in batch_results:
        batch = batch_results[typo]
        would_trigger_start_val = batch.get("start_val", False)
        would_trigger_end_val = batch.get("end_val", False)
        is_substring_val = batch.get("substring_val", False)
        would_trigger_start_src = batch.get("start_src", False)
        would_trigger_end_src = batch.get("end_src", False)
        is_substring_src = batch.get("substring_src", False)
    else:
        # Fallback to individual checks
        would_trigger_start_val = would_trigger_at_start(typo, validation_index)
        would_trigger_end_val = would_trigger_at_end(typo, validation_index)
        is_substring_val = is_substring_of_any(typo, validation_index)
        would_trigger_start_src = would_trigger_at_start(typo, source_index)
        would_trigger_end_src = would_trigger_at_end(typo, source_index)
        is_substring_src = is_substring_of_any(typo, source_index)

    # Check target word (always done individually as it's per-typo)
    would_trigger_start_target, would_trigger_end_target, is_substring_target = (
        _check_typo_in_target_word(typo, target_word)
    )

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


def batch_check_false_triggers(
    typos: list[str],
    validation_index: BoundaryIndex,
    source_index: BoundaryIndex,
) -> dict[str, dict[str, bool]]:
    """Batch check false trigger conditions for multiple typos.

    Pre-computes validation and source index checks for all typos at once,
    which is much faster than checking individually.

    Args:
        typos: List of typo strings to check
        validation_index: Boundary index for validation set
        source_index: Boundary index for source words

    Returns:
        Dict mapping typo -> dict with keys: 'start_val', 'end_val', 'substring_val',
        'start_src', 'end_src', 'substring_src'
    """
    # Batch check all typos at once
    start_val_results = validation_index.batch_check_start(typos)
    end_val_results = validation_index.batch_check_end(typos)
    substring_val_results = validation_index.batch_check_substring(typos)
    start_src_results = source_index.batch_check_start(typos)
    end_src_results = source_index.batch_check_end(typos)
    substring_src_results = source_index.batch_check_substring(typos)

    # Combine results
    batch_results: dict[str, dict[str, bool]] = {}
    for typo in typos:
        batch_results[typo] = {
            "start_val": start_val_results[typo],
            "end_val": end_val_results[typo],
            "substring_val": substring_val_results[typo],
            "start_src": start_src_results[typo],
            "end_src": end_src_results[typo],
            "substring_src": substring_src_results[typo],
        }

    return batch_results
