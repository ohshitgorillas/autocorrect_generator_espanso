"""Main processing pipeline orchestration."""

import sys
import time

from .config import Config
from .reports import ReportData, generate_reports
from .stages import (
    load_dictionaries,
    generate_typos,
    resolve_typo_collisions,
    generalize_typo_patterns,
    remove_typo_conflicts,
    generate_output,
)


def run_pipeline(config: Config) -> None:
    """Main processing pipeline orchestrating all stages.

    Args:
        config: Configuration object containing all settings
    """
    start_time = time.time()
    verbose = config.verbose

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
        collision_result, dict_data, config, verbose
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

    # Stage 6: Generate output
    output_result = generate_output(
        conflict_removal_result,
        config.output,
        config.max_entries_per_file,
        config.jobs,
        verbose,
    )

    if report_data:
        report_data.stage_times["Writing YAML files"] = output_result.elapsed_time
        report_data.total_corrections = len(conflict_removal_result.corrections)

    # Generate reports if enabled
    if config.reports:
        if verbose:
            print(f"# Generating reports in {config.reports}", file=sys.stderr)
        generate_reports(report_data, config.reports, verbose)

    # Print total time
    elapsed_time = time.time() - start_time
    if verbose:
        minutes, seconds = divmod(elapsed_time, 60)
        if minutes > 0:
            print(
                f"\n✓ Total processing time: {int(minutes)}m {seconds:.1f}s",
                file=sys.stderr,
            )
        else:
            print(f"\n✓ Total processing time: {seconds:.1f}s", file=sys.stderr)
