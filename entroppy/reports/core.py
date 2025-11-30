"""Report generation for autocorrect pipeline."""

from datetime import datetime
from pathlib import Path

from loguru import logger

from entroppy.reports.collisions import generate_collisions_report
from entroppy.reports.conflicts import generate_conflicts_report
from entroppy.reports.data import ReportData
from entroppy.reports.exclusions import generate_exclusions_report
from entroppy.reports.patterns import generate_patterns_report
from entroppy.reports.short_typos import generate_short_typos_report
from entroppy.reports.statistics import generate_statistics_csv
from entroppy.reports.summary import generate_summary_report


def generate_reports(
    data: ReportData,
    reports_path: str,
    platform_name: str,
    verbose: bool = False,
) -> Path:
    """Generate all reports in a timestamped directory.

    Args:
        data: Report data collected during pipeline execution
        reports_path: Base path for reports directory
        platform_name: Platform name to include in folder name
        verbose: Whether to print progress messages

    Returns:
        Path to the created report directory
    """
    # Create timestamped directory with platform name
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    folder_name = f"{timestamp}_{platform_name}"
    report_dir = Path(reports_path) / folder_name
    report_dir.mkdir(parents=True, exist_ok=True)

    if verbose:
        logger.info(f"\nGenerating reports in {report_dir}/")

    # Generate all report files
    generate_summary_report(data, report_dir)
    generate_collisions_report(data, report_dir)
    generate_patterns_report(data, report_dir)
    generate_conflicts_report(data, report_dir)
    generate_short_typos_report(data, report_dir)
    generate_exclusions_report(data, report_dir)
    generate_statistics_csv(data, report_dir)

    if verbose:
        logger.info("✓ Reports generated successfully")

    return report_dir
