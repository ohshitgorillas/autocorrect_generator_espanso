"""Core domain logic for EntropPy."""

from entroppy.core.boundaries import (
    BoundaryIndex,
    BoundaryType,
    determine_boundaries,
    format_boundary_display,
    format_boundary_name,
    parse_boundary_markers,
    would_trigger_at_end,
)

from .config import Config, load_config
from .pattern_generalization import generalize_patterns
from .types import Correction, MatchDirection, PatternType
from .typos import generate_all_typos

__all__ = [
    "BoundaryIndex",
    "BoundaryType",
    "Config",
    "Correction",
    "MatchDirection",
    "PatternType",
    "load_config",
    "determine_boundaries",
    "format_boundary_display",
    "format_boundary_name",
    "would_trigger_at_end",
    "parse_boundary_markers",
    "generalize_patterns",
    "generate_all_typos",
]
