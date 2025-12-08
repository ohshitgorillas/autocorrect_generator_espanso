"""Exclusions report generation."""

from pathlib import Path
from typing import TextIO

from entroppy.reports.data import ReportData
from entroppy.reports.helpers import write_report_header, write_section_header
from entroppy.utils.helpers import write_file_safely


def generate_exclusions_report(data: ReportData, report_dir: Path) -> None:
    """Generate exclusions report."""
    if not data.excluded_corrections:
        return

    filepath = report_dir / "exclusions.txt"

    def write_content(f: TextIO) -> None:
        write_report_header(f, "EXCLUSIONS REPORT")
        f.write("These corrections were blocked by exclusion rules.\n\n")
        f.write(f"Total excluded: {len(data.excluded_corrections)}\n")
        write_section_header(f, "", width=70)

        for typo, word, rule in data.excluded_corrections[:100]:
            f.write(f"{typo} → {word}\n")
            f.write(f"  Blocked by rule: {rule}\n\n")

        remaining = len(data.excluded_corrections) - 100
        if remaining > 0:
            f.write(f"... and {remaining} more (showing first 100)\n")

    write_file_safely(filepath, write_content, "writing exclusions report")
