"""Report generation for autocorrect pipeline."""

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from entroppy.reports.collisions import generate_collisions_report
from entroppy.reports.conflicts import generate_conflicts_report
from entroppy.reports.data import ReportData
from entroppy.reports.debug_corrections import generate_corrections_debug_report
from entroppy.reports.debug_graveyard import generate_graveyard_debug_report
from entroppy.reports.debug_patterns import generate_patterns_debug_report
from entroppy.reports.debug_typos import generate_debug_typos_report
from entroppy.reports.debug_words import generate_debug_words_report
from entroppy.reports.exclusions import generate_exclusions_report
from entroppy.reports.patterns import generate_patterns_report
from entroppy.reports.short_typos import generate_short_typos_report
from entroppy.reports.statistics import generate_statistics_csv
from entroppy.reports.summary import generate_summary_report

if TYPE_CHECKING:
    from entroppy.core import Config
    from entroppy.resolution.state import DebugTraceEntry, DictionaryState


def _generate_state_debug_reports(
    config: "Config", state: "DictionaryState", report_dir: Path
) -> int:
    """Generate state-based debug reports.

    Args:
        config: Configuration object
        state: Dictionary state
        report_dir: Report directory

    Returns:
        Number of reports generated
    """
    count = 0
    if config.debug_graveyard:
        generate_graveyard_debug_report(state, report_dir)
        count += 1
    if config.debug_patterns:
        generate_patterns_debug_report(state, report_dir)
        count += 1
    if config.debug_corrections:
        generate_corrections_debug_report(state, report_dir)
        count += 1
    return count


def _generate_word_typo_debug_reports(
    config: "Config",
    debug_trace: list["DebugTraceEntry"],
    report_dir: Path,
    state: "DictionaryState | None" = None,
) -> int:
    """Generate word/typo debug reports.

    Args:
        config: Configuration object
        debug_trace: Debug trace entries
        report_dir: Report directory
        state: Optional dictionary state with structured debug data

    Returns:
        Number of reports generated
    """
    count = 0
    if config.debug_words:
        generate_debug_words_report(debug_trace, report_dir, config.debug_words, state)
        count += 1
    if config.debug_typos:
        generate_debug_typos_report(debug_trace, report_dir, config.debug_typo_matcher, state)
        count += 1
    return count


def _generate_all_debug_reports(
    config: "Config | None",
    state: "DictionaryState | None",
    debug_trace: list["DebugTraceEntry"] | None,
    report_dir: Path,
) -> int:
    """Generate all debug reports if enabled.

    Args:
        config: Configuration object
        state: Dictionary state
        debug_trace: Debug trace entries
        report_dir: Report directory

    Returns:
        Number of reports generated
    """
    if not config:
        return 0

    count = 0
    if state:
        count += _generate_state_debug_reports(config, state, report_dir)
    if config.debug_words or config.debug_typos:
        debug_trace_list = debug_trace or []
        count += _generate_word_typo_debug_reports(config, debug_trace_list, report_dir, state)
    return count


def _generate_standard_reports(data: ReportData, report_dir: Path) -> None:
    """Generate all standard reports.

    Args:
        data: Report data
        report_dir: Report directory
    """
    generate_summary_report(data, report_dir)
    generate_collisions_report(data, report_dir)
    generate_patterns_report(data, report_dir)
    generate_conflicts_report(data, report_dir)
    generate_short_typos_report(data, report_dir)
    generate_exclusions_report(data, report_dir)
    generate_statistics_csv(data, report_dir)


def create_report_directory(reports_path: str, platform_name: str) -> Path:
    """Create a timestamped report directory.

    Args:
        reports_path: Base path for reports directory
        platform_name: Platform name to include in folder name

    Returns:
        Path to the created report directory
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    folder_name = f"{timestamp}_{platform_name}"
    report_dir = Path(reports_path) / folder_name
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir


def generate_reports(
    data: ReportData,
    reports_path: str | Path,
    platform_name: str,
    verbose: bool = False,
    report_dir: Path | None = None,
    state: "DictionaryState | None" = None,
    debug_trace: list["DebugTraceEntry"] | None = None,
    config: "Config | None" = None,
) -> Path:
    """Generate all reports in a timestamped directory.

    Args:
        data: Report data collected during pipeline execution
        reports_path: Base path for reports directory (used if report_dir is None)
        platform_name: Platform name to include in folder name (used if report_dir is None)
        verbose: Whether to print progress messages
        report_dir: Optional pre-created report directory. If None, creates a new one.
        state: Optional dictionary state for debug reports
        debug_trace: Optional debug trace entries
        config: Optional config for checking debug flags

    Returns:
        Path to the created report directory
    """
    # Use provided directory or create a new one
    if report_dir is None:
        report_dir = create_report_directory(str(reports_path), platform_name)

    if verbose:
        logger.info(f"  Generating reports in: {report_dir}/")

    # Generate all standard report files
    _generate_standard_reports(data, report_dir)
    report_count = 7

    # Generate debug reports if enabled
    report_count += _generate_all_debug_reports(config, state, debug_trace, report_dir)

    if verbose:
        logger.info(f"  Generated {report_count} report files")

    return report_dir
