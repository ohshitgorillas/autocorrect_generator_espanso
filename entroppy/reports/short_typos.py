"""Short typos report generation."""

from pathlib import Path

from entroppy.reports.data import ReportData
from entroppy.reports.helpers import write_report_header


def generate_short_typos_report(data: ReportData, report_dir: Path) -> None:
    """Generate short typos report."""
    if not data.skipped_short:
        return

    filepath = report_dir / "short_typos.txt"
    with open(filepath, "w", encoding="utf-8") as f:
        write_report_header(f, "SHORT TYPOS REPORT")
        f.write("These typos were skipped for being too short.\n")
        f.write("Consider adjusting --min-typo-length if needed.\n\n")
        f.write(f"Total skipped: {len(data.skipped_short)}\n")
        f.write("=" * 70 + "\n\n")

        # Group by length
        by_length = {}
        for typo, word, length in data.skipped_short:
            if length not in by_length:
                by_length[length] = []
            by_length[length].append((typo, word))

        for length in sorted(by_length.keys()):
            items = by_length[length]
            f.write(f"\nLENGTH {length} ({len(items)} typos)\n")
            f.write("-" * 70 + "\n")
            for typo, word in items[:30]:
                f.write(f"{typo} → {word}\n")
            remaining = len(items) - 30
            if remaining > 0:
                f.write(f"... and {remaining} more\n")
