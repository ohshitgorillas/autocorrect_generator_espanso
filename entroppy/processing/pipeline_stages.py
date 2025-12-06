"""Pipeline stage execution functions."""

from pathlib import Path
import time
import traceback
from typing import TYPE_CHECKING

from loguru import logger

from entroppy.core import Config, Correction
from entroppy.platforms import PlatformBackend, PlatformConstraints
from entroppy.processing.stages import generate_typos, load_dictionaries
from entroppy.reports import ReportData, generate_reports
from entroppy.resolution.passes import (
    CandidateSelectionPass,
    ConflictRemovalPass,
    PatternGeneralizationPass,
    PlatformConstraintsPass,
    PlatformSubstringConflictPass,
)
from entroppy.resolution.solver import IterativeSolver, PassContext
from entroppy.resolution.state import DictionaryState

from .pipeline_reporting import extract_graveyard_data_for_reporting

if TYPE_CHECKING:
    from entroppy.processing.stages import DictionaryData, TypoGenerationResult
    from entroppy.resolution.solver import SolverResult


def run_iterative_solver(
    typo_result: "TypoGenerationResult",
    dict_data: "DictionaryData",
    platform: PlatformBackend,
    config: Config,
    verbose: bool,
) -> tuple["SolverResult", DictionaryState]:
    """Run the iterative solver for stages 3-6.

    Args:
        typo_result: Result from typo generation
        dict_data: Dictionary data
        platform: Platform backend
        config: Configuration object
        verbose: Whether to show verbose output

    Returns:
        Tuple of (solver_result, state)
    """
    # Create dictionary state
    state = DictionaryState(
        raw_typo_map=typo_result.typo_map,
        debug_words=config.debug_words,
        debug_typo_matcher=config.debug_typo_matcher,
        debug_graveyard=config.debug_graveyard,
        debug_patterns=config.debug_patterns,
        debug_corrections=config.debug_corrections,
    )

    # Create pass context
    pass_context = PassContext.from_dictionary_data(
        dictionary_data=dict_data,
        platform=platform,
        min_typo_length=config.min_typo_length,
        collision_threshold=config.freq_ratio,
        jobs=config.jobs,
        verbose=verbose,
    )

    # Create passes
    passes = [
        CandidateSelectionPass(pass_context),
        PatternGeneralizationPass(pass_context),
        ConflictRemovalPass(pass_context),
        PlatformSubstringConflictPass(pass_context),
        PlatformConstraintsPass(pass_context),
    ]

    # Run solver
    solver = IterativeSolver(passes, max_iterations=config.max_iterations)
    solver_result = solver.solve(state)

    return solver_result, state


def apply_platform_ranking(
    solver_result: "SolverResult",
    state: DictionaryState,
    dict_data: "DictionaryData",
    platform: PlatformBackend,
    config: Config,
) -> list[Correction]:
    """Apply platform-specific ranking and filtering.

    Args:
        solver_result: Result from iterative solver
        state: Dictionary state
        dict_data: Dictionary data
        platform: Platform backend
        config: Configuration object

    Returns:
        List of ranked corrections
    """
    # Combine corrections and patterns for ranking
    # Deduplicate: same (typo, word, boundary) can appear in both corrections and patterns
    all_corrections = list(dict.fromkeys(solver_result.corrections + solver_result.patterns))

    # Rank corrections
    # Use pattern_replacements from state
    pattern_replacements = state.pattern_replacements.copy()
    # Ensure all patterns have entries (even if empty)
    for pattern in solver_result.patterns:
        if pattern not in pattern_replacements:
            pattern_replacements[pattern] = []

    return platform.rank_corrections(
        all_corrections,
        solver_result.patterns,
        pattern_replacements,
        dict_data.user_words_set,
        config,
    )


def generate_platform_reports(
    platform: PlatformBackend,
    final_corrections: list[Correction],
    _ranked_corrections: list[Correction],
    all_corrections: list[Correction],
    solver_result: "SolverResult",
    pattern_replacements: dict,
    dict_data: "DictionaryData",
    report_dir: Path,
    config: Config,
) -> None:
    """Generate platform-specific reports if supported.

    Args:
        platform: Platform backend
        final_corrections: Final list of corrections
        ranked_corrections: Ranked corrections before limit
        all_corrections: All corrections
        solver_result: Solver result
        pattern_replacements: Pattern replacements mapping
        dict_data: Dictionary data
        report_dir: Report directory
        config: Configuration object
    """
    if hasattr(platform, "generate_platform_report"):
        try:
            platform.generate_platform_report(
                final_corrections,
                all_corrections,
                solver_result.patterns,
                pattern_replacements,
                dict_data.user_words_set,
                report_dir,
                config,
            )
        except (ValueError, KeyError, AttributeError, OSError) as e:
            logger.warning(f"Failed to generate platform-specific report: {e}")
            if config.debug:
                logger.debug(traceback.format_exc())


def run_stage_1_load_dictionaries(
    config: Config, verbose: bool, report_data: ReportData | None
) -> "DictionaryData":
    """Run Stage 1: Load dictionaries and mappings.

    Args:
        config: Configuration object
        verbose: Whether to show verbose output
        report_data: Optional report data to populate

    Returns:
        Dictionary data
    """
    if verbose:
        logger.info("Stage 1: Loading dictionaries and mappings...")
    dict_data = load_dictionaries(config, verbose)

    if report_data:
        report_data.stage_times["Loading dictionaries"] = dict_data.elapsed_time
        report_data.words_processed = len(dict_data.source_words)

    if verbose:
        logger.info(f"✓ Loaded {len(dict_data.source_words)} source words")
        logger.info("")

    return dict_data


def run_stage_2_generate_typos(
    dict_data: "DictionaryData",
    config: Config,
    verbose: bool,
    report_data: ReportData | None,
) -> "TypoGenerationResult":
    """Run Stage 2: Generate typos.

    Args:
        dict_data: Dictionary data
        config: Configuration object
        verbose: Whether to show verbose output
        report_data: Optional report data to populate

    Returns:
        Typo generation result
    """
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

    return typo_result


def run_stage_3_6_solver(
    typo_result: "TypoGenerationResult",
    dict_data: "DictionaryData",
    platform: PlatformBackend,
    config: Config,
    verbose: bool,
    report_data: ReportData | None,
) -> tuple["SolverResult", DictionaryState]:
    """Run Stages 3-6: Iterative solver.

    Args:
        typo_result: Typo generation result
        dict_data: Dictionary data
        platform: Platform backend
        config: Configuration object
        verbose: Whether to show verbose output
        report_data: Optional report data to populate

    Returns:
        Tuple of (solver_result, state)
    """
    if verbose:
        logger.info("Stage 3-6: Running iterative solver...")

    solver_start = time.time()
    solver_result, state = run_iterative_solver(typo_result, dict_data, platform, config, verbose)
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

        # Create pass context for accessing configuration
        pass_context = PassContext.from_dictionary_data(
            dictionary_data=dict_data,
            platform=platform,
            min_typo_length=config.min_typo_length,
            collision_threshold=config.freq_ratio,
            jobs=config.jobs,
            verbose=verbose,
        )

        # Extract data from graveyard for reporting
        extract_graveyard_data_for_reporting(state, report_data, pass_context)

    return solver_result, state


def run_stage_7_ranking(
    solver_result: "SolverResult",
    state: DictionaryState,
    dict_data: "DictionaryData",
    platform: PlatformBackend,
    config: Config,
    constraints: PlatformConstraints,
    verbose: bool,
    report_data: ReportData | None,
) -> tuple[list[Correction], list[Correction], dict]:
    """Run Stage 7: Platform-specific ranking and filtering.

    Args:
        solver_result: Solver result
        state: Dictionary state
        dict_data: Dictionary data
        platform: Platform backend
        config: Configuration object
        constraints: Platform constraints
        verbose: Whether to show verbose output
        report_data: Optional report data to populate

    Returns:
        Tuple of (final_corrections, ranked_corrections, pattern_replacements)
    """
    if verbose:
        logger.info("Stage 7: Applying platform-specific ranking...")

    ranked_corrections = apply_platform_ranking(solver_result, state, dict_data, platform, config)

    # Combine corrections and patterns for reporting
    pattern_replacements = state.pattern_replacements.copy()
    for pattern in solver_result.patterns:
        if pattern not in pattern_replacements:
            pattern_replacements[pattern] = []

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

    if report_data:
        report_data.final_corrections = final_corrections

    return final_corrections, ranked_corrections, pattern_replacements


def run_stage_8_output(
    platform: PlatformBackend,
    final_corrections: list[Correction],
    config: Config,
    verbose: bool,
    report_data: ReportData | None,
) -> None:
    """Run Stage 8: Generate output.

    Args:
        platform: Platform backend
        final_corrections: Final list of corrections
        config: Configuration object
        verbose: Whether to show verbose output
        report_data: Optional report data to populate
    """
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


def run_stage_9_reports(
    platform: PlatformBackend,
    final_corrections: list[Correction],
    ranked_corrections: list[Correction],
    all_corrections: list[Correction],
    solver_result: "SolverResult",
    pattern_replacements: dict,
    dict_data: "DictionaryData",
    report_dir: Path,
    report_data: ReportData,
    config: Config,
    verbose: bool,
    state: DictionaryState | None = None,
    typo_result: "TypoGenerationResult | None" = None,
) -> None:
    """Run Stage 9: Generate reports.

    Args:
        platform: Platform backend
        final_corrections: Final list of corrections
        ranked_corrections: Ranked corrections before limit
        all_corrections: All corrections
        solver_result: Solver result
        pattern_replacements: Pattern replacements mapping
        dict_data: Dictionary data
        report_dir: Report directory
        report_data: Report data
        config: Configuration object
        verbose: Whether to show verbose output
        state: Optional dictionary state for debug reports
        typo_result: Optional typo generation result for debug messages
    """
    if verbose:
        logger.info("Stage 9: Generating reports...")

    # Generate standard reports (report_dir already created earlier)
    # config.reports is guaranteed to be non-None since we're in this function
    platform_name = platform.get_name()
    reports_path = config.reports if config.reports else ""

    # Extract debug data
    debug_messages = typo_result.debug_messages if typo_result else None
    debug_trace = state.debug_trace if state else None

    generate_reports(
        report_data,
        reports_path,
        platform_name,
        verbose,
        report_dir=report_dir,
        state=state,
        debug_messages=debug_messages,
        debug_trace=debug_trace,
        config=config,
    )

    # Generate platform-specific reports
    generate_platform_reports(
        platform,
        final_corrections,
        ranked_corrections,
        all_corrections,
        solver_result,
        pattern_replacements,
        dict_data,
        report_dir,
        config,
    )

    if verbose:
        logger.info(f"✓ Reports written to: {report_dir}/")
        logger.info("")
