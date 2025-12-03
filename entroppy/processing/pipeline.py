"""Main processing pipeline orchestration."""

import time

from loguru import logger

from entroppy.core import Config
from entroppy.platforms import PlatformBackend, get_platform_backend
from entroppy.reports import ReportData, format_time, generate_reports, create_report_directory
from entroppy.utils.logging import add_log_file_handler
from entroppy.processing.stages import (
    load_dictionaries,
    generate_typos,
)
from entroppy.resolution.state import DictionaryState
from entroppy.resolution.solver import IterativeSolver, PassContext
from entroppy.resolution.passes import (
    CandidateSelectionPass,
    ConflictRemovalPass,
    PatternGeneralizationPass,
    PlatformConstraintsPass,
)


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
        try:
            platform = get_platform_backend(config.platform)
        except ValueError as e:
            logger.error(f"✗ Invalid platform '{config.platform}': {e}")
            logger.error("  Supported platforms: espanso, qmk")
            raise
        except Exception as e:
            logger.error(f"✗ Unexpected error getting platform backend: {e}")
            raise

    # Get platform constraints
    constraints = platform.get_constraints()

    if verbose:
        platform_name = platform.get_name()
        logger.info(f"Platform: {platform_name}")
        if constraints.max_corrections:
            logger.info(f"Max corrections limit: {constraints.max_corrections}")
        logger.info("")

    # Initialize report data and create report directory if reports are enabled
    report_data = None
    report_dir = None
    if config.reports:
        report_data = ReportData(start_time=start_time)
        # Create report directory early so we can save logs to it
        platform_name = platform.get_name()
        report_dir = create_report_directory(config.reports, platform_name)

        # Set up log file in report directory
        # Extract timestamp from directory name (format: YYYY-MM-DD_HH-MM-SS_platform)
        # Timestamp is always the first 19 characters: YYYY-MM-DD_HH-MM-SS
        timestamp = report_dir.name[:19]
        log_file = report_dir / f"entroppy-{timestamp}.log"
        add_log_file_handler(log_file, verbose=config.verbose, debug=config.debug)

        if verbose:
            logger.info(f"Logs will be saved to: {log_file}")
            logger.info("")

    # Stage 1: Load dictionaries and mappings
    if verbose:
        logger.info("Stage 1: Loading dictionaries and mappings...")
    dict_data = load_dictionaries(config, verbose)

    if report_data:
        report_data.stage_times["Loading dictionaries"] = dict_data.elapsed_time
        report_data.words_processed = len(dict_data.source_words)

    if verbose:
        logger.info(f"✓ Loaded {len(dict_data.source_words)} source words")
        logger.info("")

    # Stage 2: Generate typos
    if verbose:
        logger.info("Stage 2: Generating typos...")
    typo_result = generate_typos(dict_data, config, verbose)

    if report_data:
        report_data.stage_times["Generating typos"] = typo_result.elapsed_time

    if verbose:
        typo_map_dict = dict(typo_result.typo_map)  # Convert to dict for pylint
        total_typos = sum(len(words) for words in typo_map_dict.values())
        logger.info(
            f"✓ Generated {total_typos} typo mappings from {len(typo_result.typo_map)} unique typos"
        )
        logger.info("")

    # Stage 3-6: Iterative Solver
    if verbose:
        logger.info("Stage 3-6: Running iterative solver...")

    solver_start = time.time()

    # Create dictionary state
    state = DictionaryState(
        raw_typo_map=typo_result.typo_map,
        debug_words=config.debug_words,
        debug_typo_matcher=config.debug_typo_matcher,
    )

    # Create pass context
    pass_context = PassContext.from_dictionary_data(
        dictionary_data=dict_data,
        platform=platform,
        min_typo_length=config.min_typo_length,
        collision_threshold=config.freq_ratio,
    )

    # Create passes
    passes = [
        CandidateSelectionPass(pass_context),
        PatternGeneralizationPass(pass_context),
        ConflictRemovalPass(pass_context),
        PlatformConstraintsPass(pass_context),
    ]

    # Run solver
    solver = IterativeSolver(passes, max_iterations=config.max_iterations)
    solver_result = solver.solve(state)

    solver_elapsed = time.time() - solver_start

    if verbose:
        logger.info(f"✓ Solver converged in {solver_result.iterations} iterations")
        logger.info(f"  Final corrections: {len(solver_result.corrections)}")
        logger.info(f"  Final patterns: {len(solver_result.patterns)}")
        logger.info(f"  Graveyard size: {solver_result.graveyard_size}")
        if not solver_result.converged:
            logger.warning("  Warning: Solver did not fully converge")
        logger.info("")

    if report_data:
        report_data.stage_times["Iterative solver"] = solver_elapsed
        report_data.total_corrections = len(solver_result.corrections)

    # Stage 7: Platform-specific ranking and filtering
    if verbose:
        logger.info("Stage 7: Applying platform-specific ranking...")

    # Combine corrections and patterns for ranking
    all_corrections = solver_result.corrections + solver_result.patterns

    # Filter corrections (if platform provides additional filtering)
    filtered_corrections, _ = platform.filter_corrections(all_corrections, config)

    # Rank corrections
    # Create dummy pattern_replacements for compatibility
    pattern_replacements = {}
    for pattern in solver_result.patterns:
        pattern_replacements[pattern] = []

    ranked_corrections = platform.rank_corrections(
        filtered_corrections,
        solver_result.patterns,
        pattern_replacements,
        dict_data.user_words_set,
        config,
    )

    # Apply platform constraints (e.g., max corrections limit)
    if constraints.max_corrections and len(ranked_corrections) > constraints.max_corrections:
        if verbose:
            logger.info(
                f"  Limiting to {constraints.max_corrections} corrections (platform constraint)"
            )
        final_corrections = ranked_corrections[: constraints.max_corrections]
    else:
        final_corrections = ranked_corrections

    if verbose:
        logger.info(f"✓ Final: {len(final_corrections)} corrections")
        logger.info("")

    # Stage 8: Generate output
    start_output = time.time()

    if verbose:
        logger.info(f"Stage 8: Generating output for {len(final_corrections)} corrections...")

    platform.generate_output(final_corrections, config.output, config)

    output_elapsed = time.time() - start_output

    if verbose:
        logger.info("✓ Output generated successfully")
        logger.info("")

    if report_data:
        report_data.stage_times["Generating output"] = output_elapsed

    # Generate reports if enabled
    if config.reports:
        if verbose:
            logger.info("Stage 9: Generating reports...")

        # Generate standard reports (report_dir already created earlier)
        platform_name = platform.get_name()
        generate_reports(report_data, config.reports, platform_name, verbose, report_dir=report_dir)

        if verbose:
            logger.info(f"✓ Reports written to: {report_dir}/")
            logger.info("")

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
