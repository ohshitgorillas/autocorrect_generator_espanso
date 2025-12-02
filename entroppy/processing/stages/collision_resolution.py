"""Stage 3: Collision resolution."""

import time

from loguru import logger

from entroppy.core import Config
from entroppy.resolution import resolve_collisions
from entroppy.processing.stages.data_models import (
    DictionaryData,
    TypoGenerationResult,
    CollisionResolutionResult,
)


def resolve_typo_collisions(
    typo_result: TypoGenerationResult,
    dict_data: DictionaryData,
    config: Config,
    verbose: bool = False,
) -> CollisionResolutionResult:
    """Resolve collisions in the typo map.

    Args:
        typo_result: Result from typo generation stage
        dict_data: Dictionary data from loading stage
        config: Configuration object
        verbose: Whether to print verbose output

    Returns:
        CollisionResolutionResult containing corrections and statistics
    """
    start_time = time.time()

    corrections, skipped_collisions, skipped_short, excluded_corrections = resolve_collisions(
        typo_result.typo_map,
        dict_data.filtered_validation_set,
        dict_data.source_words_set,
        config.freq_ratio,
        config.min_typo_length,
        config.min_word_length,
        dict_data.user_words_set,
        dict_data.exclusion_matcher,
        config.debug_words,
        config.debug_typo_matcher,
        dict_data.exclusions,
        config.jobs,
        verbose,
    )

    if verbose:
        logger.info(f"  Generated {len(corrections)} corrections (before pattern generalization)")
        if skipped_short:
            logger.info(
                f"  Skipped {len(skipped_short)} typos shorter "
                f"than {config.min_typo_length} characters"
            )
        if skipped_collisions:
            logger.info(f"  Skipped {len(skipped_collisions)} ambiguous collisions:")
            for typo, words, ratio, boundary in skipped_collisions[:5]:
                logger.info(f"    {typo}: {words} (ratio: {ratio:.2f}, boundary: {boundary.value})")
            if len(skipped_collisions) > 5:
                logger.info(f"    ... and {len(skipped_collisions) - 5} more")

    elapsed_time = time.time() - start_time

    return CollisionResolutionResult(
        corrections=corrections,
        skipped_collisions=skipped_collisions,
        skipped_short=skipped_short,
        excluded_corrections=excluded_corrections,
        elapsed_time=elapsed_time,
    )
