"""Report generation for EntropPy."""

from .core import generate_reports
from .data import ReportData
from .helpers import format_time, write_report_header

# Maintain backward compatibility with old private function names
_format_time = format_time

__all__ = [
    "ReportData",
    "generate_reports",
    "write_report_header",
    "format_time",
    "_format_time",  # Backward compatibility
]
