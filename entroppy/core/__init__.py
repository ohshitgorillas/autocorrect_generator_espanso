"""Core domain logic for EntropPy."""

from .boundaries import (
    determine_boundaries,
    format_boundary_display,
    format_boundary_name,
    would_trigger_at_end,
    parse_boundary_markers,
)
from .config import BoundaryType, Config, Correction, load_config
from .patterns import generalize_patterns
from .typos import generate_all_typos

__all__ = [
    "BoundaryType",
    "Config",
    "Correction",
    "load_config",
    "determine_boundaries",
    "format_boundary_display",
    "format_boundary_name",
    "would_trigger_at_end",
    "parse_boundary_markers",
    "generalize_patterns",
    "generate_all_typos",
]

