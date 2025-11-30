"""Helper functions for report generation."""

from datetime import datetime

def format_time(seconds: float) -> str:
    """Format seconds into human-readable time."""
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, secs = divmod(seconds, 60)
    return f"{int(minutes)}m {secs:.1f}s"


def write_report_header(f, title: str):
    """Write a standard report header with title and timestamp.

    Args:
        f: File object to write to
        title: Title of the report
    """
    f.write("=" * 80 + "\n")
    f.write(f"{title}\n")
    f.write("=" * 80 + "\n")
    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
