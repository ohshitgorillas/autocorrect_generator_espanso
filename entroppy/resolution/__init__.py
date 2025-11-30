"""Collision and conflict resolution for EntropPy."""

from .boundary_utils import choose_strictest_boundary
from .collision import (
    resolve_collisions,
    remove_substring_conflicts,
)
from .conflicts import (
    ConflictDetector,
    get_detector_for_boundary,
    resolve_conflicts_for_group,
)
from .word_processing import process_word

__all__ = [
    "process_word",
    "resolve_collisions",
    "choose_strictest_boundary",
    "remove_substring_conflicts",
    "ConflictDetector",
    "get_detector_for_boundary",
    "resolve_conflicts_for_group",
]

