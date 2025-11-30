"""Exclusions report generation."""

from pathlib import Path

from entroppy.reports.data import ReportData
from entroppy.reports.helpers import write_report_header


def generate_exclusions_report(data: ReportData, report_dir: Path) -> None:
    """Generate exclusions report."""
    if not data.excluded_corrections:
        return

    filepath = report_dir / "exclusions.txt"
    with open(filepath, "w", encoding="utf-8") as f:
        write_report_header(f, "EXCLUSIONS REPORT")
        f.write("These corrections were blocked by exclusion rules.\n\n")
        f.write(f"Total excluded: {len(data.excluded_corrections)}\n")
        f.write("=" * 70 + "\n\n")

        for typo, word, rule in data.excluded_corrections[:100]:
            f.write(f"{typo} → {word}\n")
            f.write(f"  Blocked by rule: {rule}\n\n")

        remaining = len(data.excluded_corrections) - 100
        if remaining > 0:
            f.write(f"... and {remaining} more (showing first 100)\n")
