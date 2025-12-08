"""Collision resolution for typo corrections."""

from multiprocessing import Pool
from typing import Any

from loguru import logger
from tqdm import tqdm

from entroppy.core.boundaries import BoundaryIndex, BoundaryType
from entroppy.core.types import Correction
from entroppy.matching import ExclusionMatcher
from entroppy.utils.debug import DebugTypoMatcher

from .boundaries.selection import log_boundary_selection_details
from .collision_helpers import _process_collision_item, _process_single_word_item
from .processing import process_collision_case, process_single_word_correction
from .worker_context import (
    CollisionResolutionContext,
    get_collision_worker_context,
    get_worker_indexes,
    init_collision_worker,
)


def _process_typo_worker(
    item: tuple[str, list[str]],
) -> tuple[
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
        Tuple of (corrections, excluded_list, skipped_collisions,
            skipped_short_list, boundary_details_list)
        - corrections: List of resolved corrections (can be multiple per typo, one per boundary)
        - excluded_list: List of (typo, word, matching_rule) for excluded corrections
        - skipped_collisions: List of (typo, words_in_group, ratio, boundary)
            for ambiguous collisions
        - skipped_short_list: List of (typo, word, len(typo)) for skipped short typos
        - boundary_details_list: List of boundary details dicts for later logging
    """
    typo, word_list = item
    context = get_collision_worker_context()
    validation_index, source_index = get_worker_indexes()

    # Recreate ExclusionMatcher in worker (not serializable due to compiled regex)
    exclusion_matcher = ExclusionMatcher(set(context.exclusion_set))

    # Recreate DebugTypoMatcher in worker from patterns (not serializable due to compiled regex)
    debug_typo_matcher = (
        DebugTypoMatcher.from_patterns(set(context.debug_typo_patterns))
        if context.debug_typo_patterns
        else None
    )

    # Convert frozensets back to sets for compatibility
    user_words = set(context.user_words)
    debug_words = set(context.debug_words)

    unique_words = list(set(word_list))

    if len(unique_words) == 1:
        # Single word case: no collision
        word = unique_words[0]

        # pylint: disable=duplicate-code
        # False positive: Similar parameter lists are expected when calling the same function
        # from different contexts (single-threaded vs parallel worker). This is not duplicate
        # code that should be refactored - it's the same function call with the same parameters.
        correction, was_skipped_short, excluded_info, boundary_details = (
            process_single_word_correction(
                typo,
                word,
                context.min_typo_length,
                context.min_word_length,
                user_words,
                exclusion_matcher,
                debug_words,
                debug_typo_matcher,
                validation_index,
                source_index,
            )
        )

        if was_skipped_short:
            return (
                [],
                [],
                [],
                [(typo, word, len(typo))],
                [boundary_details] if boundary_details else [],
            )
        if excluded_info:
            return (
                [],
                [excluded_info],
                [],
                [],
                [boundary_details] if boundary_details else [],
            )
        if correction:
            return (
                [correction],
                [],
                [],
                [],
                [boundary_details] if boundary_details else [],
            )
        return [], [], [], [], [boundary_details] if boundary_details else []

    # Collision case: multiple words compete for same typo
    # pylint: disable=duplicate-code
    # False positive: This is a call to process_collision_case with standard parameters.
    # The similar code in correction_processor.py is the same function call with the same
    # parameters, which is expected and not actual duplicate code.
    corrections, excluded_list, skipped_collisions, boundary_details_list = process_collision_case(
        typo,
        unique_words,
        context.freq_ratio,
        context.min_typo_length,
        context.min_word_length,
        user_words,
        exclusion_matcher,
        debug_words,
        debug_typo_matcher,
        validation_index,
        source_index,
    )

    return corrections, excluded_list, skipped_collisions, [], boundary_details_list


def _process_parallel_collisions(
    typo_map: dict[str, list[str]],
    context: CollisionResolutionContext,
    jobs: int,
    verbose: bool,
    debug_typo_matcher: DebugTypoMatcher | None,
) -> tuple[list[Correction], list, list, list]:
    """Process collisions in parallel mode.

    Args:
        typo_map: Map of typos to word lists
        context: Worker context
        jobs: Number of parallel workers
        verbose: Whether to show progress bar
        debug_typo_matcher: Matcher for debug typos

    Returns:
        Tuple of (final_corrections, skipped_collisions, skipped_short, excluded_corrections)
    """
    if verbose:
        logger.info(f"  Using {jobs} parallel workers")
        logger.info("  Preparing worker context...")
        logger.info("  Initializing workers and building boundary indexes...")

    final_corrections = []
    skipped_collisions = []
    skipped_short = []
    excluded_corrections = []
    all_boundary_details = []

    with Pool(processes=jobs, initializer=init_collision_worker, initargs=(context,)) as pool:
        items = list(typo_map.items())
        results = pool.imap_unordered(_process_typo_worker, items)

        # Wrap with progress bar if verbose
        if verbose:
            results_wrapped_iter: Any = tqdm(
                results, total=len(items), desc="Resolving collisions", unit="typo"
            )
        else:
            results_wrapped_iter = results

        for (
            corrections_list,
            excluded_list,
            skipped_collisions_list,
            skipped_short_list,
            boundary_details_list,
        ) in results_wrapped_iter:
            # Accumulate all results
            final_corrections.extend(corrections_list)
            excluded_corrections.extend(excluded_list)
            skipped_collisions.extend(skipped_collisions_list)
            skipped_short.extend(skipped_short_list)
            all_boundary_details.extend(boundary_details_list)

        # Log boundary selection details AFTER processing completes
        if all_boundary_details and debug_typo_matcher:
            # pylint: disable=duplicate-code
            # Acceptable pattern: This is a function call to log_boundary_selection_details.
            # The similar code in collision_helpers.py calls the same function with the
            # same parameters. This is expected when both places need to log boundary
            # details in the same way.
            for bd in all_boundary_details:
                log_boundary_selection_details(
                    bd["typo"],
                    bd["word"],
                    BoundaryType(bd["boundary"]),
                    bd["details"],
                    debug_typo_matcher,
                    None,  # debug_messages - not available in this context
                )

    return final_corrections, skipped_collisions, skipped_short, excluded_corrections


def _process_single_threaded_collisions(
    typo_map: dict[str, list[str]],
    validation_set: set[str],
    source_words: set[str],
    freq_ratio: float,
    min_typo_length: int,
    min_word_length: int,
    user_words: set[str],
    exclusion_matcher: ExclusionMatcher | None,
    debug_words: set[str],
    debug_typo_matcher: DebugTypoMatcher | None,
    verbose: bool,
) -> tuple[list[Correction], list, list, list]:
    """Process collisions in single-threaded mode.

    Args:
        typo_map: Map of typos to word lists
        validation_set: Set of validation words
        source_words: Set of source words
        freq_ratio: Minimum frequency ratio for collision resolution
        min_typo_length: Minimum typo length
        min_word_length: Minimum word length
        user_words: Set of user-provided words
        exclusion_matcher: Matcher for exclusion rules
        debug_words: Set of words to debug
        debug_typo_matcher: Matcher for debug typos
        verbose: Whether to show progress bar

    Returns:
        Tuple of (final_corrections, skipped_collisions, skipped_short, excluded_corrections)
    """
    if verbose:
        logger.info("  Building boundary indexes...")
    validation_index = BoundaryIndex(validation_set)
    source_index = BoundaryIndex(source_words)

    # Wrap with progress bar if verbose
    if verbose:
        items_iter: list[tuple[str, list[str]]] = list(
            tqdm(
                typo_map.items(),
                total=len(typo_map),
                desc="Resolving collisions",
                unit="typo",
            )
        )
    else:
        items_iter = list(typo_map.items())

    final_corrections: list[Correction] = []
    skipped_collisions: list[tuple[str, list[str], float, BoundaryType]] = []
    skipped_short: list[tuple[str, str, int]] = []
    excluded_corrections: list[tuple[str, str, str | None]] = []

    if exclusion_matcher is None:
        exclusion_matcher = ExclusionMatcher(set())

    for typo, word_list in items_iter:
        unique_words = list(set(word_list))

        if len(unique_words) == 1:
            # pylint: disable=duplicate-code
            # Acceptable pattern: This is a function call to a wrapper function with
            # standard parameters. The similar code in collision_helpers.py calls a
            # different wrapper function (_process_single_word_case). The similar
            # parameter lists are expected when calling related wrapper functions.
            _process_single_word_item(
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
                final_corrections,
                skipped_short,
                excluded_corrections,
            )
        else:
            # pylint: disable=duplicate-code
            # Acceptable pattern: This is a function call to a wrapper function with
            # standard parameters. The similar code in collision_helpers.py calls a
            # different wrapper function (_process_collision_case_wrapper). The similar
            # parameter lists are expected when calling related wrapper functions.
            _process_collision_item(
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
                final_corrections,
                excluded_corrections,
                skipped_collisions,
            )

    return final_corrections, skipped_collisions, skipped_short, excluded_corrections


def resolve_collisions(
    typo_map: dict[str, list[str]],
    validation_set: set[str],
    source_words: set[str],
    freq_ratio: float,
    min_typo_length: int,
    min_word_length: int,
    user_words: set[str],
    exclusion_matcher: ExclusionMatcher | None,
    debug_words: set[str] | None = None,
    debug_typo_matcher: DebugTypoMatcher | None = None,
    exclusion_set: set[str] | None = None,
    jobs: int = 1,
    verbose: bool = False,
    debug_typo_patterns: set[str] | None = None,
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
        debug_typo_patterns: Set of debug typo patterns (raw strings, for workers)

    Returns:
        Tuple of (final_corrections, skipped_collisions, skipped_short, excluded_corrections)
    """
    if debug_words is None:
        debug_words = set()

    if debug_typo_patterns is None:
        debug_typo_patterns = set()

    if exclusion_set is None:
        # Fallback: use empty set if not provided (workers will recreate matcher)
        # This should only happen in single-threaded mode
        exclusion_set = set()

    if debug_words is None:
        debug_words = set()

    if debug_typo_patterns is None:
        debug_typo_patterns = set()

    if exclusion_set is None:
        exclusion_set = set()

    if jobs > 1 and len(typo_map) > 1:
        # Parallel processing mode
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
            debug_typo_patterns=frozenset(debug_typo_patterns),
        )
        return _process_parallel_collisions(typo_map, context, jobs, verbose, debug_typo_matcher)

    # Single-threaded mode
    # pylint: disable=duplicate-code
    # Acceptable pattern: This is a function call to _process_single_threaded_collisions
    # with standard parameters. The similar code in collision_helpers.py calls
    # process_single_word_correction and process_collision_case with similar parameter
    # lists. The similarity is expected when calling related functions with the same
    # context.
    return _process_single_threaded_collisions(
        typo_map,
        validation_set,
        source_words,
        freq_ratio,
        min_typo_length,
        min_word_length,
        user_words,
        exclusion_matcher,
        debug_words,
        debug_typo_matcher,
        verbose,
    )
