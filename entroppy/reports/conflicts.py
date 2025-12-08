"""Substring conflicts report generation."""

from pathlib import Path
from typing import TextIO

from entroppy.core import BoundaryType, format_boundary_display
from entroppy.reports.data import ReportData
from entroppy.reports.helpers import write_report_header, write_section_header
from entroppy.utils.helpers import write_file_safely


def generate_conflicts_report(data: ReportData, report_dir: Path) -> None:
    """Generate substring conflicts reports (one per boundary type)."""
    if not data.removed_conflicts:
        return

    # Group by boundary type
    by_boundary: dict[BoundaryType, list[tuple[str, str, str, str]]] = {}
    for (
        long_typo,
        long_word,
        short_typo,
        short_word,
        boundary,
    ) in data.removed_conflicts:
        if boundary not in by_boundary:
            by_boundary[boundary] = []
        by_boundary[boundary].append((long_typo, long_word, short_typo, short_word))

    # Create a separate file for each boundary type
    boundary_file_map = {
        BoundaryType.NONE: "conflicts_none.txt",
        BoundaryType.LEFT: "conflicts_left.txt",
        BoundaryType.RIGHT: "conflicts_right.txt",
        BoundaryType.BOTH: "conflicts_both.txt",
    }

    for boundary, conflicts in by_boundary.items():
        filename = boundary_file_map.get(boundary, f"conflicts_{boundary.value}.txt")
        filepath = report_dir / filename

        def write_content(f: TextIO, boundary=boundary, conflicts=conflicts) -> None:
            write_report_header(
                f, f"SUBSTRING CONFLICTS - {format_boundary_display(boundary).upper()}"
            )
            f.write("These corrections were removed because a shorter typo would trigger\n")
            f.write("first, making them unreachable in Espanso.\n\n")
            f.write(f"Total removed: {len(conflicts)}\n")
            write_section_header(f, "", width=70)

            # Group by correction word for compact display
            by_word: dict[str, list[tuple[str, str, str]]] = {}
            for long_typo, long_word, short_typo, short_word in conflicts:
                if long_word not in by_word:
                    by_word[long_word] = []
                by_word[long_word].append((long_typo, short_typo, short_word))

            # Write grouped conflicts
            for word in sorted(by_word.keys()):
                entries = by_word[word]
                f.write(f"{word} ({len(entries)} blocked typo{'s' if len(entries) != 1 else ''})\n")

                # Show up to 20 typos, then summarize
                for long_typo, short_typo, short_word in entries[:20]:
                    f.write(f"  {long_typo} ← {short_typo} → {short_word}\n")

                f.write("\n")

        write_file_safely(filepath, write_content, f"writing conflicts report ({boundary.value})")
