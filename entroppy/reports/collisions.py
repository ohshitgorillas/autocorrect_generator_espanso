"""Ambiguous collisions report generation."""

from pathlib import Path

from entroppy.reports.data import ReportData
from entroppy.reports.helpers import write_report_header


def generate_collisions_report(data: ReportData, report_dir: Path) -> None:
    """Generate ambiguous collisions report."""
    if not data.skipped_collisions:
        return

    filepath = report_dir / "collisions.txt"
    with open(filepath, "w", encoding="utf-8") as f:
        write_report_header(f, "AMBIGUOUS COLLISIONS REPORT")
        f.write("These typos map to multiple words with similar frequencies and were\n")
        f.write("skipped. To force a correction, add unwanted mappings to your\n")
        f.write("exclusion file.\n\n")
        f.write(f"Total skipped: {len(data.skipped_collisions)}\n")
        f.write("=" * 70 + "\n\n")

        # Sort by ratio (closest ambiguities first)
        sorted_collisions = sorted(data.skipped_collisions, key=lambda x: x[2])

        for typo, words, ratio in sorted_collisions:
            f.write(f"{typo} → {words}\n")
            f.write(f"  Ratio: {ratio:.2f}\n")
            f.write("\n")
