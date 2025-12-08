"""Helper functions for formatting corrections in platform substring conflict pass."""

from collections import defaultdict
from multiprocessing import Pool
from typing import Any, Callable

from tqdm import tqdm

from entroppy.core.boundaries import BoundaryType
from entroppy.resolution.platform_conflicts.formatting import (
    FormattingContext,
    _format_correction_worker,
    init_formatting_worker,
)


def format_corrections_parallel(
    all_corrections: list[tuple[str, str, BoundaryType]],
    is_qmk: bool,
    jobs: int,
    verbose: bool,
    pass_name: str,
    format_typo_fn: Callable[[str, BoundaryType], str],
) -> tuple[
    dict[str, list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]]],
    dict[tuple[str, str, BoundaryType], str],
]:
    """Format corrections in parallel and build lookup structures.

    Args:
        all_corrections: List of all corrections to format
        is_qmk: Whether platform is QMK
        jobs: Number of parallel jobs
        verbose: Whether to show progress
        pass_name: Name of the pass
        format_typo_fn: Function to format typo for platform

    Returns:
        Tuple of:
        - formatted_to_corrections: Dict mapping formatted_typo ->
          list of (correction, typo, boundary)
        - correction_to_formatted: Dict mapping correction -> formatted_typo
    """
    use_parallel = jobs > 1 and len(all_corrections) >= 100

    if use_parallel:
        # pylint: disable=duplicate-code
        # Acceptable pattern: Parallel processing setup using Pool with initializer pattern.
        # This pattern is shared with formatting.py because both need to set up
        # parallel formatting workers in the same way. The Pool initialization pattern
        # is standard and should not be refactored.
        formatting_context = FormattingContext(is_qmk=is_qmk)

        with Pool(
            processes=jobs,
            initializer=init_formatting_worker,
            initargs=(formatting_context,),
        ) as pool:
            if verbose:
                results_iter = pool.imap(_format_correction_worker, all_corrections)
                results: Any = tqdm(
                    results_iter,
                    desc=f"    {pass_name}",
                    total=len(all_corrections),
                    unit="correction",
                    leave=False,
                )
            else:
                results = pool.imap(_format_correction_worker, all_corrections)
            formatted_results = list(results)
    else:
        if verbose:
            corrections_iter: Any = tqdm(
                all_corrections,
                desc=f"    {pass_name}",
                unit="correction",
                leave=False,
            )
        else:
            corrections_iter = all_corrections

        formatted_results = [(c, format_typo_fn(c[0], c[2])) for c in corrections_iter]

    # Build lookup structures
    # pylint: disable=duplicate-code
    # Acceptable pattern: Building lookup structures from formatted results is a common
    # pattern shared with formatting.py. Both need to build the same lookup structures
    # (formatted_to_corrections and correction_to_formatted) in the same way.
    # This is expected when both places need to process formatted corrections identically.
    formatted_to_corrections: dict[
        str, list[tuple[tuple[str, str, BoundaryType], str, BoundaryType]]
    ] = defaultdict(list)
    correction_to_formatted: dict[tuple[str, str, BoundaryType], str] = {}

    for correction, formatted_typo in formatted_results:
        typo, _word, boundary = correction
        formatted_to_corrections[formatted_typo].append((correction, typo, boundary))
        correction_to_formatted[correction] = formatted_typo

    return formatted_to_corrections, correction_to_formatted
