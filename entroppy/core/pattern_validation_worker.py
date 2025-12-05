"""Worker functions for parallel pattern validation."""

from dataclasses import dataclass
import threading

from entroppy.core.boundaries import BoundaryIndex, BoundaryType
from entroppy.core.pattern_conflicts import check_pattern_would_incorrectly_match_other_corrections
from entroppy.core.pattern_indexes import CorrectionIndex, SourceWordIndex
from entroppy.core.pattern_validation import (
    check_pattern_conflicts,
    validate_pattern_for_all_occurrences,
)
from entroppy.core.types import Correction, MatchDirection

# Thread-local storage for pattern validation worker context
_pattern_worker_context = threading.local()
_pattern_worker_indexes = threading.local()


@dataclass(frozen=True)
class PatternValidationContext:
    """Immutable context for pattern validation workers.

    Attributes:
        validation_set: Set of validation words
        source_words: Set of source words
        match_direction: Platform match direction
        min_typo_length: Minimum typo length
        debug_words: Set of words to debug
        corrections: All corrections for conflict checking
    """

    validation_set: frozenset[str]
    source_words: frozenset[str]
    match_direction: str  # MatchDirection enum value as string
    min_typo_length: int
    debug_words: frozenset[str]
    corrections: tuple[Correction, ...]  # Tuple for immutability


def init_pattern_validation_worker(context: PatternValidationContext) -> None:
    """Initialize worker process with context and build indexes eagerly.

    Args:
        context: PatternValidationContext to store in thread-local storage
    """
    _pattern_worker_context.value = context

    # Build indexes eagerly during initialization
    _pattern_worker_indexes.validation_index = BoundaryIndex(context.validation_set)
    _pattern_worker_indexes.source_word_index = SourceWordIndex(
        context.source_words, MatchDirection(context.match_direction)
    )
    _pattern_worker_indexes.correction_index = CorrectionIndex(list(context.corrections))


def _validate_single_pattern_worker(
    pattern_data: tuple[
        tuple[str, str, BoundaryType], list[Correction]
    ],  # (pattern_key, occurrences)
) -> tuple[
    bool,  # is_accepted
    Correction | None,  # pattern if accepted, None if rejected
    list[Correction],  # corrections_to_remove
    tuple[str, str, BoundaryType, str] | None,  # rejected_pattern tuple if rejected
]:
    """Worker function to validate a single pattern.

    Args:
        pattern_data: Tuple of (pattern_key, occurrences) where pattern_key is
            (typo_pattern, word_pattern, boundary)

    Returns:
        Tuple of (is_accepted, pattern, corrections_to_remove, rejected_pattern)
    """
    (typo_pattern, word_pattern, boundary), occurrences = pattern_data
    context = _pattern_worker_context.value
    validation_index = _pattern_worker_indexes.validation_index
    source_word_index = _pattern_worker_indexes.source_word_index
    correction_index = _pattern_worker_indexes.correction_index

    # Skip patterns with only one occurrence
    if len(occurrences) < 2:
        return False, None, [], None

    # Reject patterns that are too short
    if len(typo_pattern) < context.min_typo_length:
        reason = f"Too short (< {context.min_typo_length})"
        return False, None, [], (typo_pattern, word_pattern, boundary, reason)

    # Validate that pattern works correctly for all occurrences
    is_valid, validation_error = validate_pattern_for_all_occurrences(
        typo_pattern, word_pattern, occurrences, boundary
    )
    if not is_valid:
        return (
            False,
            None,
            [],
            (typo_pattern, word_pattern, boundary, validation_error or "Validation failed"),
        )

    # Extract target words from occurrences
    target_words = {word for _, word, _ in occurrences}

    # Check for conflicts with validation words or source/target words
    match_direction = MatchDirection(context.match_direction)
    is_safe, conflict_error = check_pattern_conflicts(
        typo_pattern,
        set(context.validation_set),
        set(context.source_words),
        match_direction,
        validation_index,
        boundary,
        source_word_index,
        target_words=target_words,
    )
    if not is_safe:
        return (
            False,
            None,
            [],
            (typo_pattern, word_pattern, boundary, conflict_error or "Conflict detected"),
        )

    # Check if pattern would incorrectly match other corrections
    is_safe, incorrect_match_error = check_pattern_would_incorrectly_match_other_corrections(
        typo_pattern,
        word_pattern,
        list(context.corrections),
        occurrences,
        correction_index=correction_index,
    )
    if not is_safe:
        return (
            False,
            None,
            [],
            (typo_pattern, word_pattern, boundary, incorrect_match_error or "Incorrect match"),
        )

    # Pattern passed all checks - accept it
    pattern = (typo_pattern, word_pattern, boundary)
    corrections_to_remove = list(occurrences)
    return True, pattern, corrections_to_remove, None
