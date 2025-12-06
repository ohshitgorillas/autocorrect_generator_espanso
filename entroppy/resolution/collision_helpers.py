"""Helper functions for collision resolution."""

from entroppy.core import BoundaryType, Correction
from entroppy.core.boundaries import BoundaryIndex
from entroppy.matching import ExclusionMatcher
from entroppy.resolution.boundaries.selection import log_boundary_selection_details
from entroppy.resolution.processing import process_collision_case, process_single_word_correction
from entroppy.utils.debug import DebugTypoMatcher


def _process_single_word_item(
    typo: str,
    unique_words: list[str],
    min_typo_length: int,
    min_word_length: int,
    user_words: set[str],
    exclusion_matcher: ExclusionMatcher,
    debug_words: set[str],
    debug_typo_matcher: DebugTypoMatcher | None,
    validation_index: BoundaryIndex,
    source_index: BoundaryIndex,
    final_corrections: list[Correction],
    skipped_short: list,
    excluded_corrections: list,
) -> None:
    """Process a single word item (no collision)."""
    correction, was_skipped_short, excluded_info = _process_single_word_case(
        typo,
        unique_words,
        min_typo_length,
        min_word_length,
        user_words,
        exclusion_matcher,
        debug_words,
        debug_typo_matcher,
        validation_index,
        source_index,
    )

    if was_skipped_short:
        skipped_short.append((typo, unique_words[0], len(typo)))
    elif excluded_info:
        excluded_corrections.append(excluded_info)
    elif correction:
        final_corrections.append(correction)


def _process_collision_item(
    typo: str,
    unique_words: list[str],
    freq_ratio: float,
    min_typo_length: int,
    min_word_length: int,
    user_words: set[str],
    exclusion_matcher: ExclusionMatcher,
    debug_words: set[str],
    debug_typo_matcher: DebugTypoMatcher | None,
    validation_index: BoundaryIndex,
    source_index: BoundaryIndex,
    final_corrections: list[Correction],
    excluded_corrections: list,
    skipped_collisions: list,
) -> None:
    """Process a collision item (multiple words)."""
    corrections_list, excluded_list, skipped_collisions_list, boundary_details_list = (
        _process_collision_case_wrapper(
            typo,
            unique_words,
            freq_ratio,
            min_typo_length,
            min_word_length,
            user_words,
            exclusion_matcher,
            debug_words,
            debug_typo_matcher,
            validation_index,
            source_index,
        )
    )

    # Accumulate all results
    final_corrections.extend(corrections_list)
    excluded_corrections.extend(excluded_list)
    skipped_collisions.extend(skipped_collisions_list)

    # Log boundary selection details for accepted corrections
    if boundary_details_list and debug_typo_matcher:
        _log_boundary_details(boundary_details_list, debug_typo_matcher)


def _process_single_word_case(
    typo: str,
    unique_words: list[str],
    min_typo_length: int,
    min_word_length: int,
    user_words: set[str],
    exclusion_matcher: ExclusionMatcher,
    debug_words: set[str],
    debug_typo_matcher: DebugTypoMatcher | None,
    validation_index: BoundaryIndex,
    source_index: BoundaryIndex,
) -> tuple[Correction | None, bool, tuple | None]:
    """Process single word case (no collision)."""
    word = unique_words[0]
    correction, was_skipped_short, excluded_info, _ = process_single_word_correction(
        typo,
        word,
        min_typo_length,
        min_word_length,
        user_words,
        exclusion_matcher,
        debug_words,
        debug_typo_matcher,
        validation_index,
        source_index,
    )
    return correction, was_skipped_short, excluded_info


def _process_collision_case_wrapper(
    typo: str,
    unique_words: list[str],
    freq_ratio: float,
    min_typo_length: int,
    min_word_length: int,
    user_words: set[str],
    exclusion_matcher: ExclusionMatcher,
    debug_words: set[str],
    debug_typo_matcher: DebugTypoMatcher | None,
    validation_index: BoundaryIndex,
    source_index: BoundaryIndex,
) -> tuple[list[Correction], list, list, list]:
    """Process collision case (multiple words)."""
    corrections_list, excluded_list, skipped_collisions_list, boundary_details_list = (
        process_collision_case(
            typo,
            unique_words,
            freq_ratio,
            min_typo_length,
            min_word_length,
            user_words,
            exclusion_matcher,
            debug_words,
            debug_typo_matcher,
            validation_index,
            source_index,
        )
    )
    return (
        corrections_list,
        excluded_list,
        skipped_collisions_list,
        boundary_details_list,
    )


def _log_boundary_details(
    boundary_details_list: list, debug_typo_matcher: DebugTypoMatcher
) -> None:
    """Log boundary selection details for accepted corrections."""
    for bd in boundary_details_list:
        log_boundary_selection_details(
            bd["typo"],
            bd["word"],
            BoundaryType(bd["boundary"]),
            bd["details"],
            debug_typo_matcher,
        )
