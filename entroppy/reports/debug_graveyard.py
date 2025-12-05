"""Graveyard debug report generation."""

from datetime import datetime
from pathlib import Path
from typing import TextIO

from entroppy.core import format_boundary_display
from entroppy.reports.helpers import write_report_header
from entroppy.resolution.state import DictionaryState
from entroppy.utils.helpers import write_file_safely


def generate_graveyard_debug_report(state: DictionaryState, report_dir: Path) -> None:
    """Generate comprehensive graveyard debug report.

    Args:
        state: Dictionary state with graveyard history
        report_dir: Directory to write report to
    """
    filepath = report_dir / "debug_graveyard.txt"

    def write_content(f: TextIO) -> None:
        write_report_header(f, "GRAVEYARD DEBUG REPORT")

        total_entries = len(state.graveyard_history)
        f.write(f"Total graveyard entries: {total_entries:,}\n\n")

        if not state.graveyard_history:
            f.write("No graveyard entries tracked.\n")
            return

        # Group by iteration
        by_iteration: dict[int, list] = {}
        for entry in state.graveyard_history:
            if entry.iteration not in by_iteration:
                by_iteration[entry.iteration] = []
            by_iteration[entry.iteration].append(entry)

        # Sort iterations
        for iteration in sorted(by_iteration.keys()):
            f.write(f"--- Iteration {iteration} ---\n")
            entries = by_iteration[iteration]

            # Group by pass within iteration
            by_pass: dict[str, list] = {}
            for entry in entries:
                if entry.pass_name not in by_pass:
                    by_pass[entry.pass_name] = []
                by_pass[entry.pass_name].append(entry)

            # Sort passes by timestamp (chronological order)
            for pass_name in sorted(
                by_pass.keys(), key=lambda p: min(e.timestamp for e in by_pass[p])
            ):
                f.write(f"  [{pass_name}]\n")
                pass_entries = sorted(by_pass[pass_name], key=lambda e: e.timestamp)

                for entry in pass_entries:
                    timestamp_str = datetime.fromtimestamp(entry.timestamp).strftime(
                        "%Y-%m-%d %H:%M:%S.%f"
                    )[:-3]
                    boundary_str = format_boundary_display(entry.boundary)
                    f.write(
                        f'    typo: "{entry.typo}" → word: "{entry.word}" '
                        f"(boundary: {boundary_str})\n"
                    )
                    f.write(f"      Reason: {entry.reason.value}\n")
                    if entry.blocker:
                        f.write(f"      Blocker: {entry.blocker}\n")
                    f.write(f"      Added at: {timestamp_str}\n")
                    f.write("\n")

            f.write("\n")

    write_file_safely(filepath, write_content, "writing graveyard debug report")
