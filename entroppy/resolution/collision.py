"""Collision resolution for typo corrections."""

from multiprocessing import Pool
from typing import TYPE_CHECKING

from loguru import logger
from tqdm import tqdm

from entroppy.core import BoundaryType, Correction
from entroppy.core.boundaries import BoundaryIndex
from entroppy.matching import ExclusionMatcher

from .boundary_selection import log_boundary_selection_details
from .correction_processing import process_collision_case, process_single_word_correction
from .worker_context import (
    CollisionResolutionContext,
    get_collision_worker_context,
    get_worker_indexes,
    init_collision_worker,
)

if TYPE_CHECKING:
    from entroppy.utils.debug import DebugTypoMatcher


def _process_typo_worker(item: tuple[str, list[str]]) -> tuple[
    list[Correction],  # corrections (can be multiple per typo now)
    list[tuple[str, str, str | None]],  # excluded_list
    list[tuple[str, list[str], float, BoundaryType]],  # skipped_collisions (now includes boundary)
    list[tuple[str, str, int]],  # skipped_short_list
    list[dict],  # boundary_details_list
]:
    """Worker function to process a single typo collision.

    Args:
        item: Tuple of (typo, word_list)

    Returns:
        Tuple of (corrections, excluded_list, skipped_collisions, skipped_short_list, boundary_details_list)
        - corrections: List of resolved corrections (can be multiple per typo, one per boundary)
        - excluded_list: List of (typo, word, matching_rule) for excluded corrections
        - skipped_collisions: List of (typo, words_in_group, ratio, boundary) for ambiguous collisions
        - skipped_short_list: List of (typo, word, len(typo)) for skipped short typos
        - boundary_details_list: List of boundary details dicts for later logging
    """
    typo, word_list = item
    context = get_collision_worker_context()
    validation_index, source_index = get_worker_indexes()

    # Recreate ExclusionMatcher in worker (not serializable due to compiled regex)
    exclusion_matcher = ExclusionMatcher(set(context.exclusion_set))

    # Convert frozensets back to sets for compatibility
    validation_set = set(context.validation_set)
    source_words = set(context.source_words)
    user_words = set(context.user_words)
    debug_words = set(context.debug_words)

    unique_words = list(set(word_list))

    if len(unique_words) == 1:
        # Single word case: no collision
        word = unique_words[0]

        correction, was_skipped_short, excluded_info, boundary_details = (
            process_single_word_correction(
                typo,
                word,
                validation_set,
                source_words,
                context.min_typo_length,
                context.min_word_length,
                user_words,
                exclusion_matcher,
                debug_words,
                None,  # debug_typo_matcher not passed to workers (not easily serializable)
                validation_index,
                source_index,
            )
        )

        if was_skipped_short:
            return [], [], [], [(typo, word, len(typo))], [boundary_details] if boundary_details else []
        elif excluded_info:
            return [], [excluded_info], [], [], [boundary_details] if boundary_details else []
        elif correction:
            return [correction], [], [], [], [boundary_details] if boundary_details else []
        else:
            return [], [], [], [], [boundary_details] if boundary_details else []
    else:
        # Collision case: multiple words compete for same typo
        corrections, excluded_list, skipped_collisions, boundary_details_list = (
            process_collision_case(
                typo,
                unique_words,
                validation_set,
                source_words,
                context.freq_ratio,
                context.min_typo_length,
                context.min_word_length,
                user_words,
                exclusion_matcher,
                debug_words,
                None,  # debug_typo_matcher not passed to workers
                validation_index,
                source_index,
            )
        )

        return corrections, excluded_list, skipped_collisions, [], boundary_details_list


def resolve_collisions(
    typo_map: dict[str, list[str]],
    validation_set: set[str],
    source_words: set[str],
    freq_ratio: float,
    min_typo_length: int,
    min_word_length: int,
    user_words: set[str],
    exclusion_matcher: ExclusionMatcher,
    debug_words: set[str] | None = None,
    debug_typo_matcher: "DebugTypoMatcher | None" = None,
    exclusion_set: set[str] | None = None,
    jobs: int = 1,
    verbose: bool = False,
) -> tuple[list[Correction], list, list, list]:
    """Resolve collisions where multiple words map to same typo.

    Args:
        typo_map: Map of typos to word lists (boundaries determined during resolution)
        validation_set: Set of validation words
        source_words: Set of source words
        freq_ratio: Minimum frequency ratio for collision resolution
        min_typo_length: Minimum typo length
        min_word_length: Minimum word length
        user_words: Set of user-provided words
        exclusion_matcher: Matcher for exclusion rules
        debug_words: Set of words to debug (exact matches)
        debug_typo_matcher: Matcher for debug typos (with wildcards/boundaries)
        exclusion_set: Set of exclusion patterns (needed for parallel workers)
        jobs: Number of parallel workers to use (1 = sequential)
        verbose: Whether to show progress bar

    Returns:
        Tuple of (final_corrections, skipped_collisions, skipped_short, excluded_corrections)
    """
    if debug_words is None:
        debug_words = set()

    if exclusion_set is None:
        # Fallback: use empty set if not provided (workers will recreate matcher)
        # This should only happen in single-threaded mode
        exclusion_set = set()

    final_corrections = []
    skipped_collisions = []
    skipped_short = []
    excluded_corrections = []

    if jobs > 1 and len(typo_map) > 1:
        # Parallel processing mode
        if verbose:
            logger.info(f"  Using {jobs} parallel workers")
            logger.info("  Preparing worker context...")

        # Create context for workers
        context = CollisionResolutionContext(
            validation_set=frozenset(validation_set),
            source_words=frozenset(source_words),
            freq_ratio=freq_ratio,
            min_typo_length=min_typo_length,
            min_word_length=min_word_length,
            user_words=frozenset(user_words),
            exclusion_set=frozenset(exclusion_set),
            debug_words=frozenset(debug_words),
        )

        if verbose:
            logger.info("  Initializing workers and building boundary indexes...")

        with Pool(
            processes=jobs,
            initializer=init_collision_worker,
            initargs=(context,),
        ) as pool:
            items = list(typo_map.items())
            results = pool.imap_unordered(_process_typo_worker, items)

            # Wrap with progress bar if verbose
            if verbose:
                results = tqdm(
                    results,
                    total=len(items),
                    desc="Resolving collisions",
                    unit="typo",
                )

            all_boundary_details = []
            for (
                corrections_list,
                excluded_list,
                skipped_collisions_list,
                skipped_short_list,
                boundary_details_list,
            ) in results:
                # Accumulate all corrections
                final_corrections.extend(corrections_list)
                
                # Accumulate all excluded
                excluded_corrections.extend(excluded_list)
                
                # Accumulate all skipped collisions
                skipped_collisions.extend(skipped_collisions_list)
                
                # Accumulate all skipped short
                skipped_short.extend(skipped_short_list)

                # Accumulate all boundary details
                all_boundary_details.extend(boundary_details_list)

            # Log boundary selection details AFTER processing completes
            if all_boundary_details and debug_typo_matcher:
                for bd in all_boundary_details:
                    log_boundary_selection_details(
                        bd["typo"],
                        bd["word"],
                        BoundaryType(bd["boundary"]),
                        bd["details"],
                        debug_typo_matcher,
                    )
    else:
        # Single-threaded mode (original implementation)
        # Build boundary indexes for efficient lookups
        if verbose:
            logger.info("  Building boundary indexes...")
        validation_index = BoundaryIndex(validation_set)
        source_index = BoundaryIndex(source_words)

        # Wrap with progress bar if verbose
        items_iter = typo_map.items()
        if verbose:
            items_iter = tqdm(
                typo_map.items(),
                total=len(typo_map),
                desc="Resolving collisions",
                unit="typo",
            )

        for typo, word_list in items_iter:
            unique_words = list(set(word_list))

            if len(unique_words) == 1:
                # Single word case: no collision
                word = unique_words[0]

                correction, was_skipped_short, excluded_info, _ = process_single_word_correction(
                    typo,
                    word,
                    validation_set,
                    source_words,
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
                    skipped_short.append((typo, word, len(typo)))
                elif excluded_info:
                    excluded_corrections.append(excluded_info)
                elif correction:
                    final_corrections.append(correction)
            else:
                # Collision case: multiple words compete for same typo
                corrections_list, excluded_list, skipped_collisions_list, boundary_details_list = process_collision_case(
                    typo,
                    unique_words,
                    validation_set,
                    source_words,
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

                # Accumulate all results
                final_corrections.extend(corrections_list)
                excluded_corrections.extend(excluded_list)
                skipped_collisions.extend(skipped_collisions_list)

                # Log boundary selection details for accepted corrections
                if boundary_details_list and debug_typo_matcher:
                    for bd in boundary_details_list:
                        log_boundary_selection_details(
                            bd["typo"],
                            bd["word"],
                            BoundaryType(bd["boundary"]),
                            bd["details"],
                            debug_typo_matcher,
                        )

    return final_corrections, skipped_collisions, skipped_short, excluded_corrections
