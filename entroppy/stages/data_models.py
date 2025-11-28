"""Data models for passing information between pipeline stages."""

from dataclasses import dataclass, field
from collections import defaultdict

from ..config import BoundaryType, Correction
from ..exclusions import ExclusionMatcher


@dataclass
class StageResult:
    """Base class for stage results with timing."""

    elapsed_time: float = 0.0


@dataclass
class DictionaryData(StageResult):
    """Output from dictionary loading stage."""

    validation_set: set[str] = field(default_factory=set)
    filtered_validation_set: set[str] = field(default_factory=set)
    exclusions: set[str] = field(default_factory=set)
    exclusion_matcher: ExclusionMatcher | None = None
    adjacent_letters_map: dict[str, list[str]] = field(default_factory=dict)
    source_words: list[str] = field(default_factory=list)
    source_words_set: set[str] = field(default_factory=set)
    user_words_set: set[str] = field(default_factory=set)


@dataclass
class TypoGenerationResult(StageResult):
    """Output from typo generation stage."""

    typo_map: dict[str, list[tuple[str, BoundaryType]]] = field(
        default_factory=lambda: defaultdict(list)
    )


@dataclass
class CollisionResolutionResult(StageResult):
    """Output from collision resolution stage."""

    corrections: list[Correction] = field(default_factory=list)
    skipped_collisions: list[tuple[str, str, float]] = field(default_factory=list)
    skipped_short: list[str] = field(default_factory=list)
    excluded_corrections: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class PatternGeneralizationResult(StageResult):
    """Output from pattern generalization stage."""

    corrections: list[Correction] = field(default_factory=list)
    patterns: list[Correction] = field(default_factory=list)
    removed_count: int = 0
    pattern_replacements: dict[Correction, list[Correction]] = field(
        default_factory=dict
    )
    rejected_patterns: list[tuple[str, str, list[str]]] = field(default_factory=list)


@dataclass
class ConflictRemovalResult(StageResult):
    """Output from conflict removal stage."""

    corrections: list[Correction] = field(default_factory=list)
    removed_corrections: list[tuple[str, str, str, str, BoundaryType]] = field(
        default_factory=list
    )
    conflicts_removed: int = 0


@dataclass
class OutputGenerationResult(StageResult):
    """Output from output generation stage."""

    files_written: int = 0
