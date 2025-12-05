"""Main processing pipeline orchestration."""

import time
from typing import TYPE_CHECKING

from loguru import logger

from entroppy.core import Config
from entroppy.platforms import PlatformBackend
from entroppy.processing.pipeline_helpers import initialize_platform, setup_reporting
from entroppy.processing.pipeline_stages import (
    run_stage_1_load_dictionaries,
    run_stage_2_generate_typos,
    run_stage_3_6_solver,
    run_stage_7_ranking,
    run_stage_8_output,
    run_stage_9_reports,
)
from entroppy.reports import format_time

if TYPE_CHECKING:
    pass


def run_pipeline(config: Config, platform: PlatformBackend | None = None) -> None:
    """Main processing pipeline using iterative solver architecture.

    This pipeline uses an iterative solver for stages 3-6, which can backtrack
    and self-heal when conflicts arise.

    Args:
        config: Configuration object containing all settings
        platform: Platform backend (if None, will be created from config.platform)
    """
    start_time = time.time()
    verbose = config.verbose

    # Get platform backend
    if platform is None:
        platform = initialize_platform(config)

    # Get platform constraints
    constraints = platform.get_constraints()

    if verbose:
        platform_name = platform.get_name()
        logger.info(f"Platform: {platform_name}")
        if constraints.max_corrections:
            logger.info(f"Max corrections limit: {constraints.max_corrections}")
        logger.info("")

    # Initialize report data and create report directory if reports are enabled
    report_data, report_dir = setup_reporting(config, platform, start_time)

    # Stage 1: Load dictionaries and mappings
    dict_data = run_stage_1_load_dictionaries(config, verbose, report_data)

    # Stage 2: Generate typos
    typo_result = run_stage_2_generate_typos(dict_data, config, verbose, report_data)

    # Stage 3-6: Iterative Solver
    solver_result, state = run_stage_3_6_solver(
        typo_result, dict_data, platform, config, verbose, report_data
    )

    # Stage 7: Platform-specific ranking and filtering
    final_corrections, ranked_corrections, pattern_replacements = run_stage_7_ranking(
        solver_result, state, dict_data, platform, config, constraints, verbose, report_data
    )

    # Stage 8: Generate output
    run_stage_8_output(platform, final_corrections, config, verbose, report_data)

    # Combine corrections and patterns for reporting
    all_corrections = list(dict.fromkeys(solver_result.corrections + solver_result.patterns))

    # Generate reports if enabled
    if config.reports and report_data is not None and report_dir is not None:
        run_stage_9_reports(
            platform,
            final_corrections,
            ranked_corrections,
            all_corrections,
            solver_result,
            pattern_replacements,
            dict_data,
            report_dir,
            report_data,
            config,
            verbose,
        )

    # Print total time
    elapsed_time = time.time() - start_time
    if verbose:
        logger.info(f"Total processing time: {format_time(elapsed_time)}")

    # Print debug summary if debugging is enabled
    if config.debug_words or config.debug_typo_matcher:
        if verbose:
            logger.info("")
            logger.info("Debug Summary:")
        logger.info(solver_result.debug_trace)
