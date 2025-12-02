"""Boundary selection logic for collision resolution."""

from typing import TYPE_CHECKING

from entroppy.core import BoundaryType
from entroppy.core.boundaries import (
    BoundaryIndex,
    is_substring_of_any,
    would_trigger_at_end,
    would_trigger_at_start,
)

from entroppy.utils.debug import (
    DebugTypoMatcher,
    is_debug_typo,
    is_debug_word,
    log_debug_typo,
)

if TYPE_CHECKING:
    from entroppy.core.types import Correction


def _check_typo_in_target_word(
    typo: str,
    target_word: str | None,
) -> tuple[bool, bool, bool]:
    """Check if typo appears as prefix, suffix, or substring in target word.

    Args:
        typo: The typo string to check
        target_word: The target word to check against (None if not available)

    Returns:
        Tuple of (is_prefix, is_suffix, is_substring)
    """
    if target_word is None:
        return False, False, False

    # Check if typo is a prefix (excluding exact match)
    is_prefix = target_word.startswith(typo) and typo != target_word

    # Check if typo is a suffix (excluding exact match)
    is_suffix = target_word.endswith(typo) and typo != target_word

    # Check if typo is a substring (excluding exact match and prefix/suffix cases)
    is_substring = typo in target_word and typo != target_word and not is_prefix and not is_suffix

    return is_prefix, is_suffix, is_substring


def _would_cause_false_trigger(
    typo: str,
    boundary: BoundaryType,
    validation_set: set[str],
    source_words: set[str],
    validation_index: BoundaryIndex,
    source_index: BoundaryIndex,
    target_word: str | None = None,
    return_details: bool = False,
) -> bool | tuple[bool, dict[str, bool]]:
    """Check if a boundary would cause false triggers (garbage corrections).

    A false trigger occurs when the typo would match validation/source words incorrectly
    due to the boundary restrictions (or lack thereof).

    Args:
        typo: The typo string
        boundary: The boundary type to check
        validation_set: Set of validation words to check against
        source_words: Set of source words to check against
        validation_index: Boundary index for validation set
        source_index: Boundary index for source words
        target_word: Optional target word to check against (highest priority check)
        return_details: If True, return tuple of (bool, details_dict) instead of just bool

    Returns:
        If return_details is False: True if the boundary would cause false triggers, False otherwise
        If return_details is True: Tuple of (would_cause_false_trigger, details_dict) where
            details_dict contains breakdown of checks performed
    """
    # FIRST: Check target word (highest priority - most critical check)
    # This prevents predictive corrections where typo is prefix/suffix/substring of target
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

    # Combine checks: target word check takes precedence
    would_trigger_start = (
        would_trigger_start_target or would_trigger_start_val or would_trigger_start_src
    )
    would_trigger_end = would_trigger_end_target or would_trigger_end_val or would_trigger_end_src
    is_substring = is_substring_target or is_substring_val or is_substring_src

    # Determine if boundary would cause false triggers
    # Logic: A boundary causes false triggers if it would allow the typo to match
    # validation/source words in positions where it appears.
    #
    # The inverse of determine_boundaries() logic:
    # - If typo appears as prefix only → need RIGHT (not NONE/LEFT)
    # - If typo appears as suffix only → need LEFT (not NONE/RIGHT)
    # - If typo appears in middle only → need BOTH (not NONE/LEFT/RIGHT)
    # - If typo appears as both prefix and suffix → need BOTH
    #
    # So a boundary causes false triggers if it would match where the typo appears:
    if boundary == BoundaryType.NONE:
        # NONE matches anywhere, so false trigger if typo appears anywhere
        would_cause = is_substring
        reason = "typo appears as substring" if is_substring else None
    elif boundary == BoundaryType.LEFT:
        # LEFT matches at word start, so false trigger if typo appears as prefix
        # (LEFT would match words starting with typo, which is incorrect)
        would_cause = would_trigger_start
        reason = "typo appears as prefix" if would_trigger_start else None
    elif boundary == BoundaryType.RIGHT:
        # RIGHT matches at word end, so false trigger if typo appears as suffix
        # (RIGHT would match words ending with typo, which is incorrect)
        would_cause = would_trigger_end
        reason = "typo appears as suffix" if would_trigger_end else None
    elif boundary == BoundaryType.BOTH:
        # BOTH matches as standalone word only, so it would NOT cause false triggers
        # for substrings (because BOTH only matches exact words, not words containing the typo)
        # BOTH is always safe for substring checks (it prevents all substring matches)
        would_cause = False
        reason = None
    else:
        # Unknown boundary type, be conservative
        would_cause = True
        reason = "unknown boundary type"

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


def choose_boundary_for_typo(
    typo: str,
    validation_set: set[str],
    source_words: set[str],
    validation_index: BoundaryIndex,
    source_index: BoundaryIndex,
    debug_words: set[str] | None = None,
    debug_typo_matcher: DebugTypoMatcher | None = None,
    word: str | None = None,
) -> BoundaryType:
    """Choose the least restrictive boundary that doesn't produce garbage corrections.

    Tries boundaries from least restrictive to most restrictive:
    1. NONE (matches anywhere)
    2. LEFT (matches at word start only)
    3. RIGHT (matches at word end only)
    4. BOTH (matches as standalone word only)

    Returns the first boundary that doesn't cause false triggers.

    Args:
        typo: The typo string
        validation_set: Set of validation words to check for false triggers
        source_words: Set of source words to check for false triggers
        validation_index: Boundary index for validation set
        source_index: Boundary index for source words
        debug_words: Set of words to debug (exact matches)
        debug_typo_matcher: Matcher for debug typos (with wildcards/boundaries)
        word: Optional word associated with this typo (for debug logging)

    Returns:
        The chosen boundary type (least restrictive that doesn't cause false triggers)
    """
    # Check if we should debug this boundary selection
    is_debug = False
    if word:
        is_debug = is_debug_word(word, debug_words or set())
    if not is_debug and debug_typo_matcher:
        # Check if typo matches any debug pattern (try with NONE boundary as placeholder)
        is_debug = is_debug_typo(typo, BoundaryType.NONE, debug_typo_matcher)

    # Try boundaries from least restrictive to most restrictive
    # Order: NONE, LEFT, RIGHT, BOTH
    boundary_order = [
        BoundaryType.NONE,
        BoundaryType.LEFT,
        BoundaryType.RIGHT,
        BoundaryType.BOTH,
    ]

    if is_debug:
        word_info = f" (word: {word})" if word else ""
        log_debug_typo(
            typo,
            f"Boundary selection starting{word_info}",
            (
                debug_typo_matcher.get_matching_patterns(typo, BoundaryType.NONE)
                if debug_typo_matcher
                else None
            ),
            "Stage 3",
        )

    # Check each boundary from least to most restrictive
    for boundary in boundary_order:
        would_cause, details = _would_cause_false_trigger(
            typo,
            boundary,
            validation_set,
            source_words,
            validation_index,
            source_index,
            target_word=word,
            return_details=True,
        )
        if not would_cause:
            if is_debug:
                word_info = f" (word: {word})" if word else ""
                log_debug_typo(
                    typo,
                    f"Selected boundary '{boundary.value}'{word_info} - no false triggers detected",
                    (
                        debug_typo_matcher.get_matching_patterns(typo, boundary)
                        if debug_typo_matcher
                        else None
                    ),
                    "Stage 3",
                )
            return boundary
        elif is_debug:
            # Log why this boundary was rejected
            reason_parts = []
            if details["would_trigger_start"]:
                reason_parts.append("appears as prefix")
            if details["would_trigger_end"]:
                reason_parts.append("appears as suffix")
            if details["is_substring"] and not (
                details["would_trigger_start"] or details["would_trigger_end"]
            ):
                reason_parts.append("appears as substring")

            reason_str = ", ".join(reason_parts) if reason_parts else "unknown reason"
            word_info = f" (word: {word})" if word else ""
            log_debug_typo(
                typo,
                f"Rejected boundary '{boundary.value}'{word_info} - would cause false triggers: {reason_str}",
                (
                    debug_typo_matcher.get_matching_patterns(typo, boundary)
                    if debug_typo_matcher
                    else None
                ),
                "Stage 3",
            )

    # If all boundaries would cause false triggers, return BOTH as safest fallback
    # (most restrictive, least likely to cause issues)
    if is_debug:
        word_info = f" (word: {word})" if word else ""
        log_debug_typo(
            typo,
            f"All boundaries would cause false triggers, using fallback '{BoundaryType.BOTH.value}'{word_info}",
            (
                debug_typo_matcher.get_matching_patterns(typo, BoundaryType.BOTH)
                if debug_typo_matcher
                else None
            ),
            "Stage 3",
        )
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
