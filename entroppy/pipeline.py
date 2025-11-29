"""Main processing pipeline orchestration."""

import time

from loguru import logger

from .config import Config
from .reports import ReportData, generate_reports
from .stages import (
    load_dictionaries,
    generate_typos,
    resolve_typo_collisions,
    generalize_typo_patterns,
    remove_typo_conflicts,
)
from .platforms import get_platform_backend, PlatformBackend


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
        platform = get_platform_backend(config.platform)

    # Get platform constraints
    constraints = platform.get_constraints()

    if verbose:
        platform_name = platform.get_name()
        logger.info(f"# Using platform: {platform_name}")
        if constraints.max_corrections:
            logger.info(f"# Max corrections: {constraints.max_corrections}")

    # Initialize report data if reports are enabled
    report_data = None
    if config.reports:
        report_data = ReportData(start_time=start_time)

    # Stage 1: Load dictionaries and mappings
    dict_data = load_dictionaries(config, verbose)

    if report_data:
        report_data.stage_times["Loading dictionaries"] = dict_data.elapsed_time
        report_data.words_processed = len(dict_data.source_words)

    # Stage 2: Generate typos
    typo_result = generate_typos(dict_data, config, verbose)

    if report_data:
        report_data.stage_times["Generating typos"] = typo_result.elapsed_time

    # Stage 3: Resolve collisions
    collision_result = resolve_typo_collisions(typo_result, dict_data, config, verbose)

    if report_data:
        report_data.stage_times["Resolving collisions"] = collision_result.elapsed_time
        report_data.skipped_collisions = collision_result.skipped_collisions
        report_data.skipped_short = collision_result.skipped_short
        report_data.excluded_corrections = collision_result.excluded_corrections
        report_data.corrections_before_generalization = len(
            collision_result.corrections
        )

    # Stage 4: Generalize patterns
    pattern_result = generalize_typo_patterns(
        collision_result, dict_data, config, constraints.match_direction, verbose
    )

    if report_data:
        report_data.stage_times["Generalizing patterns"] = pattern_result.elapsed_time
        report_data.corrections_after_generalization = len(pattern_result.corrections)
        # Store pattern info with count of replacements
        for typo, word, boundary in pattern_result.patterns:
            pattern_key = (typo, word, boundary)
            count = len(pattern_result.pattern_replacements.get(pattern_key, []))
            report_data.generalized_patterns.append((typo, word, boundary, count))
        report_data.pattern_replacements = pattern_result.pattern_replacements
        report_data.rejected_patterns = pattern_result.rejected_patterns

    # Stage 5: Remove conflicts
    conflict_removal_result = remove_typo_conflicts(
        pattern_result, verbose, collect_details=config.reports is not None
    )

    if report_data:
        report_data.stage_times["Removing conflicts"] = (
            conflict_removal_result.elapsed_time
        )
        report_data.corrections_after_conflicts = len(
            conflict_removal_result.corrections
        )
        report_data.removed_conflicts = conflict_removal_result.removed_corrections

    # Stage 5.5: Platform-specific filtering and ranking
    start_filter = time.time()

    if verbose:
        logger.info("# Applying platform-specific filtering and ranking...")

    # Filter corrections
    filtered_corrections, filter_metadata = platform.filter_corrections(
        conflict_removal_result.corrections, config
    )

    if verbose and filter_metadata.get("filtered_count", 0) > 0:
        logger.info(
            f"# Platform filtered: {filter_metadata['filtered_count']} corrections"
        )

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
    if (
        constraints.max_corrections
        and len(ranked_corrections) > constraints.max_corrections
    ):
        if verbose:
            logger.info(
                f"# Limiting to {constraints.max_corrections} corrections "
                "(platform constraint)"
            )
        final_corrections = ranked_corrections[: constraints.max_corrections]
    else:
        final_corrections = ranked_corrections

    filter_elapsed = time.time() - start_filter

    if report_data:
        report_data.stage_times["Platform filtering/ranking"] = filter_elapsed
        report_data.total_corrections = len(final_corrections)
        # Store platform-specific data for reports
        report_data.final_corrections = final_corrections
        report_data.ranked_corrections_before_limit = ranked_corrections
        report_data.filtered_corrections = filtered_corrections
        report_data.filter_metadata = filter_metadata

    # Stage 6: Generate output
    start_output = time.time()

    if verbose:
        logger.info(
            f"# Generating output for {len(final_corrections)} corrections"
        )

    platform.generate_output(final_corrections, config.output, config)

    output_elapsed = time.time() - start_output

    if report_data:
        report_data.stage_times["Generating output"] = output_elapsed

    # Generate reports if enabled
    if config.reports:
        if verbose:
            logger.info(f"# Generating reports in {config.reports}")

        # Generate standard reports
        platform_name = platform.get_name()
        report_dir = generate_reports(
            report_data, config.reports, platform_name, verbose
        )

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
            logger.info(f"✓ Platform report written to {report_dir}/")

    # Print total time
    elapsed_time = time.time() - start_time
    if verbose:
        minutes, seconds = divmod(elapsed_time, 60)
        if minutes > 0:
            logger.info(
                f"\n✓ Total processing time: {int(minutes)}m {seconds:.1f}s"
            )
        else:
            logger.info(f"\n✓ Total processing time: {seconds:.1f}s")
