"""Worker functions for candidate selection parallel processing."""

from collections import defaultdict
from typing import TYPE_CHECKING

from entroppy.core import BoundaryType
from entroppy.core.boundaries import determine_boundaries
from entroppy.core.types import Correction
from entroppy.matching import ExclusionMatcher
from entroppy.resolution.false_trigger_check import _check_false_trigger_with_details
from entroppy.resolution.state import RejectionReason
from entroppy.resolution.worker_context import (
    CandidateSelectionContext,
    get_candidate_selection_worker_context,
    get_candidate_worker_indexes,
)
from entroppy.utils.helpers import cached_word_frequency

if TYPE_CHECKING:
    pass


def _get_boundary_order(natural_boundary: BoundaryType) -> list[BoundaryType]:
    """Get the order of boundaries to try, starting with the natural one.

    This implements self-healing: if a less strict boundary fails,
    we automatically try stricter ones in subsequent iterations.

    Args:
        natural_boundary: The naturally determined boundary

    Returns:
        List of boundaries to try in order
    """
    # Order: try natural first, then stricter alternatives
    if natural_boundary == BoundaryType.NONE:
        # NONE is least strict - try all others if it fails
        return [
            BoundaryType.NONE,
            BoundaryType.LEFT,
            BoundaryType.RIGHT,
            BoundaryType.BOTH,
        ]
    if natural_boundary == BoundaryType.LEFT:
        return [BoundaryType.LEFT, BoundaryType.BOTH]
    if natural_boundary == BoundaryType.RIGHT:
        return [BoundaryType.RIGHT, BoundaryType.BOTH]
    # BOTH is most strict - only try it
    return [BoundaryType.BOTH]


def _check_length_constraints_worker(typo: str, word: str, min_typo_length: int) -> bool:
    """Check if typo/word meet length constraints in worker.

    Args:
        typo: The typo string
        word: The correct word
        min_typo_length: Minimum typo length

    Returns:
        True if constraints are met
    """
    # If word is shorter than min_typo_length, typo must be at least min_typo_length
    if len(word) <= min_typo_length:
        return len(typo) >= min_typo_length
    return True


def _process_single_word_worker(
    typo: str,
    word: str,
    context: CandidateSelectionContext,
    validation_index,
    source_index,
    exclusion_matcher: ExclusionMatcher | None,
    corrections: list[tuple[str, str, BoundaryType]],
    graveyard_entries: list[tuple[str, str, BoundaryType, RejectionReason, str | None]],
) -> None:
    """Process a typo with a single word (no collision) in worker.

    Args:
        typo: The typo string
        word: The correct word
        context: Worker context
        validation_index: Boundary index for validation set
        source_index: Boundary index for source words
        exclusion_matcher: Exclusion matcher (or None)
        corrections: List to append corrections to
        graveyard_entries: List to append graveyard entries to
    """
    # Determine the natural boundary for this typo
    natural_boundary = determine_boundaries(typo, validation_index, source_index)

    # Try boundaries in order: NONE -> LEFT/RIGHT -> BOTH
    boundaries_to_try = _get_boundary_order(natural_boundary)

    for boundary in boundaries_to_try:
        # Check if this is in the graveyard
        if (typo, word, boundary) in context.graveyard:
            continue

        # Check length constraints
        if not _check_length_constraints_worker(typo, word, context.min_typo_length):
            graveyard_entries.append((typo, word, boundary, RejectionReason.TOO_SHORT, None))
            continue

        # Check exclusions
        if exclusion_matcher and exclusion_matcher.should_exclude((typo, word, boundary)):
            graveyard_entries.append(
                (typo, word, boundary, RejectionReason.EXCLUDED_BY_PATTERN, None)
            )
            continue

        # Check for false triggers
        # pylint: disable=duplicate-code
        # Intentional duplication: Same false trigger check pattern used in multiple places
        # (worker functions, sequential functions, and boundary_selection.py) to ensure
        # consistent validation logic across all code paths where corrections are added.
        would_cause, details = _check_false_trigger_with_details(
            typo,
            boundary,
            validation_index,
            source_index,
            target_word=word,
        )
        if would_cause:
            # This boundary would cause false triggers - add to graveyard and try next boundary
            reason_value = details.get("reason", "false trigger")
            reason_str = reason_value if isinstance(reason_value, str) else "false trigger"
            graveyard_entries.append(
                (typo, word, boundary, RejectionReason.FALSE_TRIGGER, reason_str)
            )
            continue

        # Add the correction
        corrections.append((typo, word, boundary))
        return  # Successfully added, no need to try other boundaries


def _process_single_word_with_boundary_worker(
    typo: str,
    word: str,
    boundary: BoundaryType,
    context: CandidateSelectionContext,
    validation_index,
    source_index,
    exclusion_matcher: ExclusionMatcher | None,
    corrections: list[tuple[str, str, BoundaryType]],
    graveyard_entries: list[tuple[str, str, BoundaryType, RejectionReason, str | None]],
) -> None:
    """Process a single word with a specific boundary in worker.

    Args:
        typo: The typo string
        word: The correct word
        boundary: The boundary type
        context: Worker context
        validation_index: Boundary index for validation set
        source_index: Boundary index for source words
        exclusion_matcher: Exclusion matcher (or None)
        corrections: List to append corrections to
        graveyard_entries: List to append graveyard entries to
    """
    # Try boundaries in order starting from the given boundary
    boundaries_to_try = _get_boundary_order(boundary)

    for bound in boundaries_to_try:
        # Check if this is in the graveyard
        if (typo, word, bound) in context.graveyard:
            continue

        # Check length constraints
        if not _check_length_constraints_worker(typo, word, context.min_typo_length):
            graveyard_entries.append((typo, word, bound, RejectionReason.TOO_SHORT, None))
            continue

        # Check exclusions
        if exclusion_matcher and exclusion_matcher.should_exclude((typo, word, bound)):
            graveyard_entries.append((typo, word, bound, RejectionReason.EXCLUDED_BY_PATTERN, None))
            continue

        # Check for false triggers
        # pylint: disable=duplicate-code
        # Intentional duplication: Same false trigger check pattern used in multiple places
        # (worker functions, sequential functions, and boundary_selection.py) to ensure
        # consistent validation logic across all code paths where corrections are added.
        would_cause, _ = _check_false_trigger_with_details(
            typo,
            bound,
            validation_index,
            source_index,
            target_word=word,
        )
        if would_cause:
            # This boundary would cause false triggers - try next boundary
            continue

        # Add the correction
        corrections.append((typo, word, bound))
        return  # Successfully added


def _resolve_collision_by_frequency_worker(
    typo: str,
    words: list[str],
    boundary: BoundaryType,
    context: CandidateSelectionContext,
    validation_index,
    source_index,
    exclusion_matcher: ExclusionMatcher | None,
    corrections: list[tuple[str, str, BoundaryType]],
    graveyard_entries: list[tuple[str, str, BoundaryType, RejectionReason, str | None]],
) -> None:
    """Resolve a collision using frequency analysis in worker.

    Args:
        typo: The typo string
        words: List of competing words
        boundary: The boundary type for this group
        context: Worker context
        validation_index: Boundary index for validation set
        source_index: Boundary index for source words
        exclusion_matcher: Exclusion matcher (or None)
        corrections: List to append corrections to
        graveyard_entries: List to append graveyard entries to
    """
    # Get frequencies for all words
    word_freqs = [(w, cached_word_frequency(w, "en")) for w in words]
    word_freqs.sort(key=lambda x: x[1], reverse=True)

    most_common = word_freqs[0]
    second_most = word_freqs[1] if len(word_freqs) > 1 else (None, 0)
    ratio = most_common[1] / second_most[1] if second_most[1] > 0 else float("inf")

    if ratio <= context.collision_threshold:
        # Ambiguous collision - add all words to graveyard
        for word in words:
            graveyard_entries.append(
                (typo, word, boundary, RejectionReason.COLLISION_AMBIGUOUS, f"ratio={ratio:.2f}")
            )
        return

    # Can resolve collision - use most common word
    word = most_common[0]

    # Try boundaries in order
    boundaries_to_try = _get_boundary_order(boundary)

    for bound in boundaries_to_try:
        # Check if this is in the graveyard
        if (typo, word, bound) in context.graveyard:
            continue

        # Check length constraints
        if not _check_length_constraints_worker(typo, word, context.min_typo_length):
            graveyard_entries.append((typo, word, bound, RejectionReason.TOO_SHORT, None))
            continue

        # Check exclusions
        if exclusion_matcher and exclusion_matcher.should_exclude((typo, word, bound)):
            graveyard_entries.append((typo, word, bound, RejectionReason.EXCLUDED_BY_PATTERN, None))
            continue

        # Check for false triggers
        # pylint: disable=duplicate-code
        # Intentional duplication: Same false trigger check pattern used in multiple places
        # (worker functions, sequential functions, and boundary_selection.py) to ensure
        # consistent validation logic across all code paths where corrections are added.
        would_cause, _ = _check_false_trigger_with_details(
            typo,
            bound,
            validation_index,
            source_index,
            target_word=word,
        )
        if would_cause:
            # This boundary would cause false triggers - try next boundary
            continue

        # Add the correction
        corrections.append((typo, word, bound))
        return  # Successfully added


def _process_collision_worker(
    typo: str,
    unique_words: list[str],
    context: CandidateSelectionContext,
    validation_index,
    source_index,
    exclusion_matcher: ExclusionMatcher | None,
    corrections: list[tuple[str, str, BoundaryType]],
    graveyard_entries: list[tuple[str, str, BoundaryType, RejectionReason, str | None]],
) -> None:
    """Process a typo with multiple competing words (collision) in worker.

    Args:
        typo: The typo string
        unique_words: List of competing words
        context: Worker context
        validation_index: Boundary index for validation set
        source_index: Boundary index for source words
        exclusion_matcher: Exclusion matcher (or None)
        corrections: List to append corrections to
        graveyard_entries: List to append graveyard entries to
    """
    # Determine boundaries for each word
    word_boundary_map = {}
    for word in unique_words:
        boundary = determine_boundaries(typo, validation_index, source_index)
        word_boundary_map[word] = boundary

    # Group words by boundary type
    by_boundary = defaultdict(list)
    for word, boundary in word_boundary_map.items():
        by_boundary[boundary].append(word)

    # Process each boundary group separately
    for boundary, words_in_group in by_boundary.items():
        if len(words_in_group) == 1:
            # No collision within this boundary
            word = words_in_group[0]
            _process_single_word_with_boundary_worker(
                typo,
                word,
                boundary,
                context,
                validation_index,
                source_index,
                exclusion_matcher,
                corrections,
                graveyard_entries,
            )
        else:
            # Collision within this boundary - resolve by frequency
            _resolve_collision_by_frequency_worker(
                typo,
                words_in_group,
                boundary,
                context,
                validation_index,
                source_index,
                exclusion_matcher,
                corrections,
                graveyard_entries,
            )


def _process_typo_batch_worker(
    batch: list[tuple[str, list[str]]],
) -> tuple[
    list[tuple[str, str, BoundaryType]],  # corrections
    list[tuple[str, str, BoundaryType, RejectionReason, str | None]],  # graveyard entries
]:
    """Worker function to process a batch of typos.

    Args:
        batch: List of (typo, word_list) tuples to process

    Returns:
        Tuple of (corrections, graveyard_entries)
        - corrections: List of (typo, word, boundary) tuples to add
        - graveyard_entries: List of (typo, word, boundary, reason, blocker) tuples
    """
    context = get_candidate_selection_worker_context()
    indexes = get_candidate_worker_indexes()
    if not isinstance(indexes, tuple) or len(indexes) != 2:
        len_str = str(len(indexes)) if isinstance(indexes, tuple) else "unknown"
        raise ValueError(
            f"get_candidate_worker_indexes() returned {type(indexes)} with "
            f"{len_str} values, expected tuple of 2: {indexes}"
        )
    validation_index, source_index = indexes

    # Recreate ExclusionMatcher in worker (not serializable due to compiled regex)
    exclusion_matcher = (
        ExclusionMatcher(set(context.exclusion_set)) if context.exclusion_set else None
    )

    corrections: list[Correction] = []
    graveyard_entries: list[tuple[str, str, BoundaryType, RejectionReason, str | None]] = []

    for typo, word_list in batch:
        # Skip if already covered
        if typo in context.covered_typos:
            continue

        # Get unique words for this typo
        unique_words = list(set(word_list))

        # Process based on number of words
        if len(unique_words) == 1:
            _process_single_word_worker(
                typo,
                unique_words[0],
                context,
                validation_index,
                source_index,
                exclusion_matcher,
                corrections,
                graveyard_entries,
            )
        else:
            _process_collision_worker(
                typo,
                unique_words,
                context,
                validation_index,
                source_index,
                exclusion_matcher,
                corrections,
                graveyard_entries,
            )

    # Explicitly return a tuple of exactly 2 items
    return (corrections, graveyard_entries)
