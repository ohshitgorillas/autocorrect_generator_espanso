"""Patterns debug report generation."""

from datetime import datetime
from pathlib import Path
from typing import TextIO

from entroppy.core import format_boundary_display
from entroppy.reports.helpers import write_report_header
from entroppy.resolution.state import DictionaryState
from entroppy.utils.helpers import write_file_safely


def generate_patterns_debug_report(state: DictionaryState, report_dir: Path) -> None:
    """Generate comprehensive patterns debug report.

    Args:
        state: Dictionary state with pattern history
        report_dir: Directory to write report to
    """
    filepath = report_dir / "debug_patterns.txt"

    def write_content(f: TextIO) -> None:
        write_report_header(f, "PATTERNS DEBUG REPORT")

        total_events = len(state.pattern_history)
        f.write(f"Total pattern events: {total_events:,}\n\n")

        if not state.pattern_history:
            f.write("No pattern events tracked.\n")
            return

        # Group by iteration
        by_iteration: dict[int, list] = {}
        for entry in state.pattern_history:
            if entry.iteration not in by_iteration:
                by_iteration[entry.iteration] = []
            by_iteration[entry.iteration].append(entry)

        # Track which corrections were replaced by patterns
        pattern_replacements = state.pattern_replacements

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
                    action_str = entry.action.upper()
                    boundary_str = format_boundary_display(entry.boundary)
                    f.write(
                        f'    {action_str}: "{entry.typo}" → "{entry.word}" '
                        f"(boundary: {boundary_str})\n"
                    )
                    f.write(f"      {action_str.capitalize()} at: {timestamp_str}\n")

                    if entry.action == "added":
                        # Show which corrections were replaced
                        pattern_key = (entry.typo, entry.word, entry.boundary)
                        if pattern_key in pattern_replacements:
                            replacements = pattern_replacements[pattern_key]
                            f.write(f"      Replaces {len(replacements)} corrections:\n")
                            for typo, word, _ in replacements[:15]:  # Show first 15
                                f.write(f'        - "{typo}" → "{word}"\n')
                            if len(replacements) > 15:
                                f.write(f"        ... and {len(replacements) - 15} more\n")
                    elif entry.reason:
                        f.write(f"      Reason: {entry.reason}\n")

                    f.write("\n")

            f.write("\n")

    write_file_safely(filepath, write_content, "writing patterns debug report")
