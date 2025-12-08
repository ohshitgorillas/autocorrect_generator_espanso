"""Main processing pipeline orchestration."""

from pathlib import Path
import time

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


def _log_platform_info(platform: PlatformBackend, verbose: bool) -> None:
    """Log platform information if verbose."""
    if verbose:
        platform_name = platform.get_name()
        logger.info(f"Platform: {platform_name}")
        constraints = platform.get_constraints()
        if constraints.max_corrections:
            logger.info(f"Max corrections limit: {constraints.max_corrections}")
        logger.info("")


def _generate_reports(
    config: Config,
    platform: PlatformBackend,
    final_corrections: list,
    ranked_corrections: list,
    all_corrections: list,
    solver_result,
    pattern_replacements: dict,
    dict_data,
    report_dir: Path | None,
    report_data,
    verbose: bool,
    state=None,
) -> None:
    """Generate reports if enabled."""
    if config.reports and report_data is not None and report_dir is not None:
        # pylint: disable=duplicate-code
        # Acceptable pattern: This is a function call with standard report parameters.
        # The similar code in pipeline_stages.py calls generate_platform_reports with
        # similar parameters. The similarity is expected when both functions need to
        # pass the same report data.
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
            state=state,
        )


def _print_debug_summary(config: Config, solver_result, verbose: bool) -> None:
    """Print debug summary if debugging is enabled."""
    if config.debug_words or config.debug_typo_matcher:
        if verbose:
            logger.info("")
            logger.info("Debug Summary:")
        logger.info(solver_result.debug_trace)


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

    # Log platform information
    _log_platform_info(platform, verbose)

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
    constraints = platform.get_constraints()
    final_corrections, ranked_corrections, pattern_replacements = run_stage_7_ranking(
        solver_result,
        state,
        dict_data,
        platform,
        config,
        constraints,
        verbose,
        report_data,
    )

    # Stage 8: Generate output
    run_stage_8_output(platform, final_corrections, config, verbose, report_data)

    # Combine corrections and patterns for reporting
    all_corrections = list(dict.fromkeys(solver_result.corrections + solver_result.patterns))

    # Generate reports if enabled
    _generate_reports(
        config,
        platform,
        final_corrections,
        ranked_corrections,
        all_corrections,
        solver_result,
        pattern_replacements,
        dict_data,
        report_dir,
        report_data,
        verbose,
        state=state,
    )

    # Print total time
    elapsed_time = time.time() - start_time
    if verbose:
        logger.info(f"Total processing time: {format_time(elapsed_time)}")

    # Print debug summary if debugging is enabled
    _print_debug_summary(config, solver_result, verbose)
