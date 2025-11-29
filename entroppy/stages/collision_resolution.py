"""Stage 3: Collision resolution."""

import time

from loguru import logger

from ..config import Config
from ..processing import resolve_collisions
from .data_models import (
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

    corrections, skipped_collisions, skipped_short, excluded_corrections = (
        resolve_collisions(
            typo_result.typo_map,
            config.freq_ratio,
            config.min_typo_length,
            config.min_word_length,
            dict_data.user_words_set,
            dict_data.exclusion_matcher,
        )
    )

    if verbose:
        logger.info(
            f"# Generated {len(corrections)} corrections (before pattern generalization)"
        )
        if skipped_short:
            logger.info(
                f"# Skipped {len(skipped_short)} typos shorter "
                f"than {config.min_typo_length} characters"
            )
        if skipped_collisions:
            logger.info(
                f"# Skipped {len(skipped_collisions)} ambiguous collisions:"
            )
            for typo, words, ratio in skipped_collisions[:5]:
                logger.info(f"#   {typo}: {words} (ratio: {ratio:.2f})")

    elapsed_time = time.time() - start_time

    return CollisionResolutionResult(
        corrections=corrections,
        skipped_collisions=skipped_collisions,
        skipped_short=skipped_short,
        excluded_corrections=excluded_corrections,
        elapsed_time=elapsed_time,
    )
