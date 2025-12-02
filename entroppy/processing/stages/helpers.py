"""Helper functions for pipeline stages to reduce code duplication."""

from typing import TYPE_CHECKING

from entroppy.core import Config
from entroppy.resolution import resolve_collisions

if TYPE_CHECKING:
    from entroppy.processing.stages.data_models import DictionaryData
    from entroppy.utils.debug import DebugTypoMatcher


def call_resolve_collisions(
    typo_map: dict[str, list[str]],
    dict_data: "DictionaryData",
    config: Config,
    exclusion_set: set[str] | None = None,
    jobs: int | None = None,
    verbose: bool = False,
) -> tuple:
    """Call resolve_collisions with common parameters extracted from dict_data and config.

    This helper function eliminates duplication between collision_resolution.py
    and pattern_generalization.py by centralizing the parameter extraction.

    Args:
        typo_map: Map of typos to word lists
        dict_data: Dictionary data from loading stage
        config: Configuration object
        exclusion_set: Optional exclusion set (if None, uses dict_data.exclusions)
        jobs: Optional number of jobs (if None, uses config.jobs)
        verbose: Whether to show verbose output

    Returns:
        Tuple of (corrections, skipped_collisions, skipped_short, excluded_corrections)
    """
    return resolve_collisions(
        typo_map,
        dict_data.filtered_validation_set,
        dict_data.source_words_set,
        config.freq_ratio,
        config.min_typo_length,
        config.min_word_length,
        dict_data.user_words_set,
        dict_data.exclusion_matcher,
        config.debug_words,
        config.debug_typo_matcher,
        exclusion_set if exclusion_set is not None else dict_data.exclusions,
        jobs if jobs is not None else config.jobs,
        verbose,
    )
