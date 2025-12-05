"""Helper functions for report generation."""

from datetime import datetime
from typing import TextIO


def format_time(seconds: float) -> str:
    """Format seconds into human-readable time."""
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, secs = divmod(seconds, 60)
    return f"{int(minutes)}m {secs:.1f}s"


def write_report_header(f: TextIO, title: str) -> None:
    """Write a standard report header with title and timestamp.

    Args:
        f: File object to write to
        title: Title of the report
    """
    f.write("=" * 80 + "\n")
    f.write(f"{title}\n")
    f.write("=" * 80 + "\n")
    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")


def write_section_header(f: TextIO, title: str) -> None:
    """Write a section header with separator line.

    Args:
        f: File object to write to
        title: Title of the section (empty string to write only separator)
    """
    if title:
        f.write(f"{title}\n")
    f.write("-" * 80 + "\n")
