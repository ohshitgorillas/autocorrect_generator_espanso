"""Core domain logic for EntropPy."""

from entroppy.core.boundaries import (
    BoundaryType,
    determine_boundaries,
    format_boundary_display,
    format_boundary_name,
    would_trigger_at_end,
    parse_boundary_markers,
)
from .config import Config, load_config
from .types import Correction
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
