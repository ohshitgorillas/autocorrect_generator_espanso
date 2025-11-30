"""Espanso platform-specific report generation."""

from pathlib import Path

from ...core import Correction
from ...reports import write_report_header


def generate_espanso_output_report(
    final_corrections: list[Correction],
    corrections_by_letter: dict[str, list[dict]],
    ram_estimate: dict[str, float],
    max_entries_per_file: int,
    report_dir: Path,
) -> dict:
    """Generate Espanso output summary report."""
    report_path = report_dir / "espanso_output.txt"

    with open(report_path, "w", encoding="utf-8") as f:
        write_report_header(f, "ESPANSO OUTPUT SUMMARY")
        _write_overview(f, final_corrections, ram_estimate)
        _write_file_breakdown(f, corrections_by_letter, max_entries_per_file)
        _write_largest_files(f, corrections_by_letter)

    return {
        "file_path": str(report_path),
        "total_corrections": len(final_corrections),
        "estimated_mb": ram_estimate.get("total_mb", 0),
    }


def _write_overview(f, final_corrections: list[Correction], ram_estimate: dict):
    """Write overview section."""
    f.write("OVERVIEW\n")
    f.write("-" * 80 + "\n")
    f.write(f"Total corrections:              {len(final_corrections):,}\n")
    f.write(
        f"Estimated RAM usage:            {ram_estimate.get('total_mb', 0):.2f} MB\n"
    )
    f.write(
        f"Average bytes per entry:        {ram_estimate.get('per_entry_bytes', 0):.1f}\n\n"
    )


def _write_file_breakdown(
    f, corrections_by_letter: dict[str, list[dict]], max_entries_per_file: int
):
    """Write file breakdown section."""
    f.write("FILE BREAKDOWN\n")
    f.write("-" * 80 + "\n")

    total_files = 0
    for letter in sorted(corrections_by_letter.keys()):
        matches = corrections_by_letter[letter]
        num_corrections = len(matches)
        num_files = (num_corrections + max_entries_per_file - 1) // max_entries_per_file
        total_files += num_files

        f.write(f"Letter '{letter}':  {num_corrections:,} corrections")
        if num_files > 1:
            f.write(f" → {num_files} files\n")
        else:
            f.write(f" → {num_files} file\n")

    f.write("-" * 80 + "\n")
    f.write(f"Total YAML files:               {total_files}\n")
    f.write(f"Max entries per file:           {max_entries_per_file}\n\n")


def _write_largest_files(f, corrections_by_letter: dict[str, list[dict]]):
    """Write largest files section."""
    f.write("LARGEST FILES (Top 5 by correction count)\n")
    f.write("-" * 80 + "\n")

    # Sort by correction count
    sorted_letters = sorted(
        corrections_by_letter.items(), key=lambda x: len(x[1]), reverse=True
    )

    for i, (letter, matches) in enumerate(sorted_letters[:5], 1):
        f.write(f"{i}. Letter '{letter}': {len(matches):,} corrections\n")

    f.write("\n")
