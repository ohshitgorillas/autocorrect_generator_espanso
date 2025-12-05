"""Passes for the iterative solver."""

from .candidate_selection import CandidateSelectionPass
from .conflict_removal import ConflictRemovalPass
from .pattern_generalization import PatternGeneralizationPass
from .platform_constraints import PlatformConstraintsPass
from .platform_substring_conflicts import PlatformSubstringConflictPass

__all__ = [
    "CandidateSelectionPass",
    "PatternGeneralizationPass",
    "ConflictRemovalPass",
    "PlatformConstraintsPass",
    "PlatformSubstringConflictPass",
]
