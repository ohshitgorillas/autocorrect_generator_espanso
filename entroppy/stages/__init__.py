"""Pipeline stages for processing typos."""

from .data_models import (
    DictionaryData,
    TypoGenerationResult,
    CollisionResolutionResult,
    PatternGeneralizationResult,
    ConflictRemovalResult,
    OutputGenerationResult,
)
from .dictionary_loading import load_dictionaries
from .typo_generation import generate_typos
from .collision_resolution import resolve_typo_collisions
from .pattern_generalization import generalize_typo_patterns
from .conflict_removal import remove_typo_conflicts
from .output_generation import generate_output

__all__ = [
    # Data models
    "DictionaryData",
    "TypoGenerationResult",
    "CollisionResolutionResult",
    "PatternGeneralizationResult",
    "ConflictRemovalResult",
    "OutputGenerationResult",
    # Stage functions
    "load_dictionaries",
    "generate_typos",
    "resolve_typo_collisions",
    "generalize_typo_patterns",
    "remove_typo_conflicts",
    "generate_output",
]