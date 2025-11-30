"""Pattern generalization report generation."""

from pathlib import Path

from entroppy.reports.data import ReportData
from entroppy.core import format_boundary_display
from entroppy.reports.helpers import write_report_header


def generate_patterns_report(data: ReportData, report_dir: Path) -> None:
    """Generate pattern generalization report."""
    filepath = report_dir / "patterns.txt"
    with open(filepath, "w", encoding="utf-8") as f:
        write_report_header(f, "PATTERN GENERALIZATION REPORT")

        patterns_count = len(data.generalized_patterns)
        replaced_count = sum(len(v) for v in data.pattern_replacements.values())
        f.write(f"Generalized {patterns_count} patterns, ")
        f.write(f"replacing {replaced_count} specific corrections.\n")
        f.write("=" * 70 + "\n\n")

        if data.generalized_patterns:
            f.write("GENERALIZED PATTERNS\n")
            f.write("-" * 70 + "\n\n")
            for typo_suffix, word_suffix, boundary, count in data.generalized_patterns:
                f.write(f"✓ {typo_suffix} → {word_suffix} ({format_boundary_display(boundary)})\n")
                f.write(f"  Replaced {count} specific corrections\n")

                # Show what was replaced
                pattern_key = (typo_suffix, word_suffix, boundary)
                if pattern_key in data.pattern_replacements:
                    replacements = data.pattern_replacements[pattern_key][:10]
                    for typo, word, _ in replacements:
                        f.write(f"    - {typo} → {word}\n")
                f.write("\n")

        if data.rejected_patterns:
            f.write("\nREJECTED PATTERNS\n")
            f.write("-" * 70 + "\n\n")
            for pattern_typo, pattern_word, reason in data.rejected_patterns:
                f.write(f"✗ {pattern_typo} → {pattern_word}\n")
                f.write(f"  Reason: {reason}\n\n")
