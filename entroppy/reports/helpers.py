"""Helper functions for report generation."""

from datetime import datetime
from typing import Any, Callable, TextIO

from entroppy.core import format_boundary_display


def write_report_header(f: TextIO, title: str) -> None:
    """Write a standard report header.

    Args:
        f: File object to write to
        title: Report title
    """
    f.write("=" * 80 + "\n")
    f.write(f"{title}\n")
    f.write("=" * 80 + "\n")
    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write("\n")


def format_time(seconds: float) -> str:
    """Format time in seconds to human-readable string.

    Args:
        seconds: Time in seconds

    Returns:
        Formatted time string
    """
    if seconds < 1:
        return f"{seconds * 1000:.1f}ms"
    if seconds < 60:
        return f"{seconds:.2f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes}m {secs:.2f}s"


def format_entry_header(entry) -> tuple[str, str, str]:
    """Format entry header for report output.

    Args:
        entry: History entry with timestamp, action, boundary

    Returns:
        Tuple of (timestamp_str, action_str, boundary_str)
    """
    timestamp_str = datetime.fromtimestamp(entry.timestamp).strftime("%Y-%m-%d %H:%M:%S")
    action_str = entry.action.replace("_", " ").title()
    boundary_str = format_boundary_display(entry.boundary)
    return timestamp_str, action_str, boundary_str


def iterate_by_iteration_and_pass(
    events: list[Any],
    f: TextIO,
    write_entry: Callable[[TextIO, Any], None],
) -> None:
    """Iterate through events organized by iteration and pass, writing entries.

    Args:
        events: List of history entries
        f: File to write to
        write_entry: Function to write a single entry
    """
    organized: dict[int, dict[str, list]] = {}
    for entry in events:
        iteration = entry.iteration
        pass_name = entry.pass_name if hasattr(entry, "pass_name") else "Unknown"
        if iteration not in organized:
            organized[iteration] = {}
        if pass_name not in organized[iteration]:
            organized[iteration][pass_name] = []
        organized[iteration][pass_name].append(entry)

    for iteration in sorted(organized.keys()):
        f.write("\n")
        write_subsection_header(f, f"ITERATION {iteration}")
        for pass_name in sorted(organized[iteration].keys()):
            f.write("\n")
            write_subsection_header(f, f"[{pass_name}]")
            for entry in organized[iteration][pass_name]:
                write_entry(f, entry)


def write_section_header(f: TextIO, title: str, width: int = 80) -> None:
    """Write a section header.

    Args:
        f: File object to write to
        title: Section title
        width: Width of separator line (default: 80)
    """
    f.write("\n")
    f.write("=" * width + "\n")
    f.write(f"{title}\n")
    f.write("=" * width + "\n")


def write_subsection_header(f: TextIO, title: str, width: int = 80) -> None:
    """Write a subsection header.

    Args:
        f: File object to write to
        title: Subsection title
        width: Width of separator line (default: 80)
    """
    f.write(f"{title}\n")
    f.write("-" * width + "\n")
