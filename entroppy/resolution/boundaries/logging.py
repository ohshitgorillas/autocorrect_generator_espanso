"""Debug logging functions for boundary selection."""

from entroppy.core import BoundaryType
from entroppy.core.boundaries import BoundaryIndex
from entroppy.utils.debug import DebugTypoMatcher, is_debug_typo, is_debug_word, log_debug_typo

from .utils import (
    _check_typo_in_target_word,
    _format_incorrect_transformation,
    _get_example_words_with_prefix,
    _get_example_words_with_substring,
    _get_example_words_with_suffix,
)


def _should_debug_boundary_selection(
    typo: str,
    word: str | None,
    debug_words: set[str] | None,
    debug_typo_matcher: DebugTypoMatcher | None,
) -> bool:
    """Check if boundary selection should be debugged.

    Args:
        typo: The typo string
        word: Optional word associated with this typo
        debug_words: Set of words to debug (exact matches)
        debug_typo_matcher: Matcher for debug typos (with wildcards/boundaries)

    Returns:
        True if debugging should be enabled, False otherwise
    """
    if word:
        if is_debug_word(word, debug_words or set()):
            return True
    if debug_typo_matcher:
        # Check if typo matches any debug pattern (try with NONE boundary as placeholder)
        return is_debug_typo(typo, BoundaryType.NONE, debug_typo_matcher)
    return False


def _determine_boundary_order(
    typo: str, word: str | None
) -> tuple[list[BoundaryType], tuple[bool, bool, bool]]:
    """Determine the boundary order based on typo's relationship to target word.

    Args:
        typo: The typo string
        word: Optional target word to check relationship against

    Returns:
        Tuple of (boundary_order, relationship) where relationship is
        (is_prefix, is_suffix, is_middle)
    """
    # Check target word relationship first to determine appropriate boundary order
    target_is_prefix, target_is_suffix, target_is_middle = (
        _check_typo_in_target_word(typo, word) if word else (False, False, False)
    )

    # Build boundary order based on target word relationship
    if target_is_suffix:
        # Typo is suffix of target - skip LEFT (doesn't match relationship)
        # LEFT boundary means "match at word start", but typo appears at word end
        # Try: NONE, RIGHT, BOTH
        boundary_order = [BoundaryType.NONE, BoundaryType.RIGHT, BoundaryType.BOTH]
    elif target_is_prefix:
        # Typo is prefix of target - skip RIGHT (doesn't match relationship)
        # RIGHT boundary means "match at word end", but typo appears at word start
        # Try: NONE, LEFT, BOTH
        boundary_order = [BoundaryType.NONE, BoundaryType.LEFT, BoundaryType.BOTH]
    elif target_is_middle:
        # Typo is middle substring - skip LEFT and RIGHT (both incompatible)
        # Neither LEFT nor RIGHT make sense for middle substrings
        # Try: NONE, BOTH
        boundary_order = [BoundaryType.NONE, BoundaryType.BOTH]
    else:
        # Default order: no target word relationship detected
        # Try all boundaries: NONE, LEFT, RIGHT, BOTH
        boundary_order = [
            BoundaryType.NONE,
            BoundaryType.LEFT,
            BoundaryType.RIGHT,
            BoundaryType.BOTH,
        ]

    return boundary_order, (target_is_prefix, target_is_suffix, target_is_middle)


def _log_boundary_order_selection(
    typo: str,
    word: str | None,
    relationship: tuple[bool, bool, bool],
    debug_typo_matcher: DebugTypoMatcher | None,
    debug_messages: list[str] | None = None,
) -> None:
    """Log the boundary order selection for debugging.

    Args:
        typo: The typo string
        word: Optional word associated with this typo
        relationship: Tuple of (is_prefix, is_suffix, is_middle)
        debug_typo_matcher: Matcher for debug typos (with wildcards/boundaries)
        debug_messages: Optional list to collect messages into (for reports)
    """
    target_is_prefix, target_is_suffix, target_is_middle = relationship
    word_info = f" (word: {word})" if word else ""

    if target_is_suffix:
        message = (
            f"Boundary selection starting{word_info} - typo is SUFFIX of target, "
            f"skipping LEFT boundary"
        )
    elif target_is_prefix:
        message = (
            f"Boundary selection starting{word_info} - typo is PREFIX of target, "
            f"skipping RIGHT boundary"
        )
    elif target_is_middle:
        message = (
            f"Boundary selection starting{word_info} - typo is MIDDLE substring of target, "
            f"skipping LEFT and RIGHT boundaries"
        )
    else:
        message = f"Boundary selection starting{word_info}"

    log_debug_typo(
        typo,
        message,
        (
            debug_typo_matcher.get_matching_patterns(typo, BoundaryType.NONE)
            if debug_typo_matcher
            else None
        ),
        "Stage 3",
        debug_messages,
    )


def _log_none_boundary_rejection(
    typo: str,
    word: str | None,
    details: dict[str, bool | str | None],
    validation_index: BoundaryIndex,
    source_index: BoundaryIndex,
) -> list[str]:
    """Log NONE boundary rejection with examples.

    Args:
        typo: The typo string
        word: Optional word associated with this typo
        details: Details dictionary from false trigger check
        validation_index: Boundary index for validation set
        source_index: Boundary index for source words

    Returns:
        List of example lines
    """
    example_lines = []
    if details["is_substring"]:
        examples = _get_example_words_with_substring(typo, validation_index, source_index)
        if not examples:
            # Fallback: check if it's a prefix or suffix
            if details["would_trigger_start"]:
                examples = _get_example_words_with_prefix(typo, validation_index, source_index)
            elif details["would_trigger_end"]:
                examples = _get_example_words_with_suffix(typo, validation_index, source_index)

        if examples:
            example_word = examples[0]
            example_lines.append(
                f'"{typo}" -> "{word}" with NONE boundary would conflict '
                f'with source word "{example_word}"'
            )
            example_lines.append(_format_incorrect_transformation(example_word, typo, word or ""))
            example_lines.append("NONE BOUNDARY REJECTED")
    return example_lines


def _log_left_boundary_rejection(
    typo: str,
    word: str | None,
    details: dict[str, bool | str | None],
    validation_index: BoundaryIndex,
    source_index: BoundaryIndex,
) -> list[str]:
    """Log LEFT boundary rejection with examples.

    Args:
        typo: The typo string
        word: Optional word associated with this typo
        details: Details dictionary from false trigger check
        validation_index: Boundary index for validation set
        source_index: Boundary index for source words

    Returns:
        List of example lines
    """
    example_lines = []
    if details["would_trigger_start"]:
        examples = _get_example_words_with_prefix(typo, validation_index, source_index)
        if examples:
            example_word = examples[0]
            example_lines.append(
                f'"{typo}" -> "{word}" with LEFT boundary would conflict '
                f'with source word "{example_word}"'
            )
            example_lines.append(_format_incorrect_transformation(example_word, typo, word or ""))
            example_lines.append("LEFT BOUNDARY REJECTED")
    return example_lines


def _log_right_boundary_rejection(
    typo: str,
    word: str | None,
    details: dict[str, bool | str | None],
    validation_index: BoundaryIndex,
    source_index: BoundaryIndex,
) -> list[str]:
    """Log RIGHT boundary rejection with examples.

    Args:
        typo: The typo string
        word: Optional word associated with this typo
        details: Details dictionary from false trigger check
        validation_index: Boundary index for validation set
        source_index: Boundary index for source words

    Returns:
        List of example lines
    """
    example_lines = []
    if details["would_trigger_end"]:
        examples = _get_example_words_with_suffix(typo, validation_index, source_index)
        if examples:
            example_word = examples[0]
            example_lines.append(
                f'"{typo}" -> "{word}" with RIGHT boundary would conflict '
                f'with source word "{example_word}"'
            )
            example_lines.append(_format_incorrect_transformation(example_word, typo, word or ""))
            example_lines.append("RIGHT BOUNDARY REJECTED")
    return example_lines


def _build_fallback_rejection_message(
    boundary: BoundaryType,
    word_info: str,
    details: dict[str, bool | str | None],
) -> str:
    """Build fallback rejection message when no examples found.

    Args:
        boundary: The boundary that was rejected
        word_info: Word info string
        details: Details dictionary from false trigger check

    Returns:
        Fallback message string
    """
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
    return (
        f"Rejected boundary '{boundary.value}'{word_info} - "
        f"would cause false triggers: {reason_str}"
    )


def _log_boundary_rejection(
    typo: str,
    word: str | None,
    boundary: BoundaryType,
    details: dict[str, bool | str | None],
    validation_index: BoundaryIndex,
    source_index: BoundaryIndex,
    debug_typo_matcher: DebugTypoMatcher | None,
    debug_messages: list[str] | None = None,
) -> None:
    """Log why a boundary was rejected with concrete examples.

    Args:
        typo: The typo string
        word: Optional word associated with this typo
        boundary: The boundary that was rejected
        details: Details dictionary from false trigger check
        validation_index: Boundary index for validation set
        source_index: Boundary index for source words
        debug_typo_matcher: Matcher for debug typos (with wildcards/boundaries)
        debug_messages: Optional list to collect messages into (for reports)
    """
    word_info = f" (word: {word})" if word else ""
    example_lines = []

    # Get example words for each type of conflict
    if boundary == BoundaryType.NONE:
        example_lines = _log_none_boundary_rejection(
            typo, word, details, validation_index, source_index
        )
    elif boundary == BoundaryType.LEFT:
        example_lines = _log_left_boundary_rejection(
            typo, word, details, validation_index, source_index
        )
    elif boundary == BoundaryType.RIGHT:
        example_lines = _log_right_boundary_rejection(
            typo, word, details, validation_index, source_index
        )
    elif boundary == BoundaryType.BOTH:
        # BOTH boundary is always safe (prevents all substring matches)
        example_lines.append(
            "BOTH boundary requires standalone word, prevents all substring matches"
        )

    # Format the message
    if example_lines:
        message = "\n".join(example_lines)
    else:
        message = _build_fallback_rejection_message(boundary, word_info, details)

    log_debug_typo(
        typo,
        message,
        (debug_typo_matcher.get_matching_patterns(typo, boundary) if debug_typo_matcher else None),
        "Stage 3",
        debug_messages,
    )


def _log_fallback_boundary(
    typo: str,
    word: str | None,
    debug_typo_matcher: DebugTypoMatcher | None,
    debug_messages: list[str] | None = None,
) -> None:
    """Log when falling back to BOTH boundary.

    Args:
        typo: The typo string
        word: Optional word associated with this typo
        debug_typo_matcher: Matcher for debug typos (with wildcards/boundaries)
        debug_messages: Optional list to collect messages into (for reports)
    """
    word_info = f" (word: {word})" if word else ""
    log_debug_typo(
        typo,
        f"All boundaries would cause false triggers, using fallback "
        f"'{BoundaryType.BOTH.value}'{word_info}",
        (
            debug_typo_matcher.get_matching_patterns(typo, BoundaryType.BOTH)
            if debug_typo_matcher
            else None
        ),
        "Stage 3",
        debug_messages,
    )
