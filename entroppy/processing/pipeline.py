"""Main processing pipeline orchestration."""

import time

from loguru import logger

from entroppy.core import Config
from entroppy.platforms import PlatformBackend, get_platform_backend
from entroppy.reports import ReportData, format_time, generate_reports
from entroppy.processing.stages.conflict_removal import update_patterns_from_conflicts
from entroppy.processing.stages import (
    generalize_typo_patterns,
    load_dictionaries,
    remove_typo_conflicts,
    resolve_typo_collisions,
    generate_typos,
)
from entroppy.processing.stages.platform_filtering_logging import (
    log_max_corrections_limit_application,
)
from entroppy.resolution.state import DictionaryState
from entroppy.resolution.solver import IterativeSolver, PassContext
from entroppy.resolution.passes import (
    CandidateSelectionPass,
    ConflictRemovalPass,
    PatternGeneralizationPass,
    PlatformConstraintsPass,
)


def run_iterative_solver_pipeline(
    config: Config, platform: PlatformBackend | None = None
) -> None:
    """Run pipeline using the new iterative solver architecture.

    This is the new architecture that replaces stages 3-6 with an iterative
    solver that can backtrack and retry alternatives.

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

    # Initialize report data if reports are enabled
    report_data = None
    if config.reports:
        report_data = ReportData(start_time=start_time)

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
        total_typos = sum(len(words) for words in typo_result.typo_map.values())
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
    solver = IterativeSolver(passes)
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
    filtered_corrections, filter_metadata = platform.filter_corrections(all_corrections, config)

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

        # Generate standard reports
        platform_name = platform.get_name()
        report_dir = generate_reports(report_data, config.reports, platform_name, verbose)

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


def run_pipeline(config: Config, platform: PlatformBackend | None = None) -> None:
    """Main processing pipeline orchestrating all stages.

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

    # Initialize report data if reports are enabled
    report_data = None
    if config.reports:
        report_data = ReportData(start_time=start_time)

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
        # pylint: disable=no-member
        total_typos = sum(len(words) for words in typo_result.typo_map.values())
        logger.info(
            f"✓ Generated {total_typos} typo mappings from {len(typo_result.typo_map)} unique typos"
        )
        logger.info("")

    # Stage 3: Resolve collisions
    if verbose:
        logger.info("Stage 3: Resolving collisions...")
    collision_result = resolve_typo_collisions(typo_result, dict_data, config, verbose)

    if report_data:
        report_data.stage_times["Resolving collisions"] = collision_result.elapsed_time
        report_data.skipped_collisions = collision_result.skipped_collisions
        report_data.skipped_short = collision_result.skipped_short
        report_data.excluded_corrections = collision_result.excluded_corrections
        report_data.corrections_before_generalization = len(collision_result.corrections)

    if verbose:
        logger.info(
            f"✓ Resolved collisions: {len(collision_result.corrections)} corrections remaining"
        )
        if collision_result.skipped_collisions:
            logger.info(
                f"  Skipped {len(collision_result.skipped_collisions)} ambiguous collisions"
            )
        if collision_result.skipped_short:
            logger.info(
                f"  Skipped {len(collision_result.skipped_short)} typos below minimum length"
            )
        logger.info("")

    # Stage 4: Generalize patterns
    if verbose:
        logger.info("Stage 4: Generalizing patterns...")
    pattern_result = generalize_typo_patterns(
        collision_result, dict_data, config, constraints.match_direction, verbose
    )

    if report_data:
        report_data.stage_times["Generalizing patterns"] = pattern_result.elapsed_time
        report_data.corrections_after_generalization = len(pattern_result.corrections)
        # Store pattern info with count of replacements
        for typo, word, boundary in pattern_result.patterns:
            pattern_key = (typo, word, boundary)
            # pylint: disable=no-member
            count = len(pattern_result.pattern_replacements.get(pattern_key, []))
            report_data.generalized_patterns.append((typo, word, boundary, count))
        report_data.pattern_replacements = pattern_result.pattern_replacements
        report_data.rejected_patterns = pattern_result.rejected_patterns

    if verbose:
        logger.info(f"✓ Generalized {len(pattern_result.patterns)} patterns")
        logger.info(f"  Total corrections after generalization: {len(pattern_result.corrections)}")
        logger.info("")

    # Stage 5: Remove conflicts
    if verbose:
        logger.info("Stage 5: Removing conflicts...")
    conflict_removal_result = remove_typo_conflicts(
        pattern_result,
        verbose,
        collect_details=config.reports is not None,
        debug_words=config.debug_words,
        debug_typo_matcher=config.debug_typo_matcher,
    )

    if report_data:
        report_data.stage_times["Removing conflicts"] = conflict_removal_result.elapsed_time
        report_data.corrections_after_conflicts = len(conflict_removal_result.corrections)
        report_data.removed_conflicts = conflict_removal_result.removed_corrections

    if verbose:
        logger.info(
            f"✓ Removed {conflict_removal_result.conflicts_removed} conflicting corrections"
        )
        logger.info(f"  Remaining corrections: {len(conflict_removal_result.corrections)}")
        logger.info("")

    # Stage 5.5: Platform-specific filtering and ranking
    start_filter = time.time()

    if verbose:
        logger.info("Stage 6: Applying platform-specific filtering and ranking...")

    # Filter corrections
    filtered_corrections, filter_metadata = platform.filter_corrections(
        conflict_removal_result.corrections, config
    )

    if verbose and filter_metadata.get("filtered_count", 0) > 0:
        logger.info(f"  Platform filtered: {filter_metadata['filtered_count']} corrections")

    # Update patterns based on conflicts detected during platform filtering
    # When a shorter correction blocks a longer one, the shorter one is a pattern
    # This is universal - any correction that blocks others is a pattern
    # (except BOTH boundary corrections, which can't block anything)
    all_conflicts = []
    # QMK format: (long_typo, long_word, short_typo, short_word, boundary)
    if "suffix_conflicts" in filter_metadata:
        all_conflicts.extend(filter_metadata["suffix_conflicts"])
    if "substring_conflicts" in filter_metadata:
        all_conflicts.extend(filter_metadata["substring_conflicts"])

    if all_conflicts:
        updated_patterns, updated_replacements = update_patterns_from_conflicts(
            pattern_result.patterns,
            pattern_result.pattern_replacements,
            filtered_corrections,
            all_conflicts,
        )
        pattern_result.patterns = updated_patterns
        pattern_result.pattern_replacements = updated_replacements

    # Rank corrections
    ranked_corrections = platform.rank_corrections(
        filtered_corrections,
        pattern_result.patterns,
        pattern_result.pattern_replacements,
        dict_data.user_words_set,
        config,
    )

    # Apply platform constraints (e.g., max corrections limit)
    constraints = platform.get_constraints()
    if constraints.max_corrections and len(ranked_corrections) > constraints.max_corrections:
        if verbose:
            logger.info(
                f"  Limiting to {constraints.max_corrections} corrections (platform constraint)"
            )
        final_corrections = ranked_corrections[: constraints.max_corrections]

        # Debug logging for max_corrections limit
        if config.debug_words or config.debug_typo_matcher:
            for i, correction in enumerate(ranked_corrections, 1):
                within_limit = i <= constraints.max_corrections
                log_max_corrections_limit_application(
                    correction,
                    i,
                    constraints.max_corrections,
                    len(ranked_corrections),
                    within_limit,
                    config.debug_words or set(),
                    config.debug_typo_matcher,
                )
    else:
        final_corrections = ranked_corrections

    filter_elapsed = time.time() - start_filter

    if verbose:
        logger.info(f"✓ Filtered and ranked: {len(final_corrections)} final corrections")
        logger.info("")

    if report_data:
        report_data.stage_times["Platform filtering/ranking"] = filter_elapsed
        report_data.total_corrections = len(final_corrections)
        # Store platform-specific data for reports
        report_data.final_corrections = final_corrections
        report_data.ranked_corrections_before_limit = ranked_corrections
        report_data.filtered_corrections = filtered_corrections
        report_data.filter_metadata = filter_metadata

    # Stage 7: Generate output
    start_output = time.time()

    if verbose:
        logger.info(f"Stage 7: Generating output for {len(final_corrections)} corrections...")

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
            logger.info("Stage 8: Generating reports...")

        # Generate standard reports
        platform_name = platform.get_name()
        report_dir = generate_reports(report_data, config.reports, platform_name, verbose)

        # Generate platform-specific report
        platform.generate_platform_report(
            final_corrections,
            ranked_corrections,
            filtered_corrections,
            pattern_result.patterns,
            pattern_result.pattern_replacements,
            dict_data.user_words_set,
            filter_metadata,
            report_dir,
            config,
        )

        if verbose:
            logger.info(f"✓ Reports written to: {report_dir}/")
            logger.info("")

    # Print total time
    elapsed_time = time.time() - start_time
    if verbose:
        logger.info(f"Total processing time: {format_time(elapsed_time)}")
