"""Data models for passing information between pipeline stages."""

from collections import defaultdict

from pydantic import BaseModel, Field

from entroppy.core import BoundaryType, Correction
from entroppy.matching import ExclusionMatcher


class StageResult(BaseModel):
    """Base class for stage results with timing."""

    elapsed_time: float = Field(0.0, ge=0)


class DictionaryData(StageResult):
    """Output from dictionary loading stage."""

    validation_set: set[str] = Field(default_factory=set)
    filtered_validation_set: set[str] = Field(default_factory=set)
    exclusions: set[str] = Field(default_factory=set)
    exclusion_matcher: ExclusionMatcher | None = None
    adjacent_letters_map: dict[str, str] = Field(default_factory=dict)
    source_words: list[str] = Field(default_factory=list)
    source_words_set: set[str] = Field(default_factory=set)
    user_words_set: set[str] = Field(default_factory=set)

    model_config = {
        "arbitrary_types_allowed": True,  # For ExclusionMatcher
    }


class TypoGenerationResult(StageResult):
    """Output from typo generation stage."""

    typo_map: dict[str, list[str]] = Field(default_factory=lambda: defaultdict(list))


class CollisionResolutionResult(StageResult):
    """Output from collision resolution stage."""

    corrections: list[Correction] = Field(default_factory=list)
    skipped_collisions: list[tuple[str, list[str], float, BoundaryType]] = Field(default_factory=list)
    skipped_short: list[tuple[str, str, int]] = Field(default_factory=list)
    excluded_corrections: list[tuple[str, str, str | None]] = Field(default_factory=list)


class PatternGeneralizationResult(StageResult):
    """Output from pattern generalization stage."""

    corrections: list[Correction] = Field(default_factory=list)
    patterns: list[Correction] = Field(default_factory=list)
    removed_count: int = Field(0, ge=0)
    pattern_replacements: dict[Correction, list[Correction]] = Field(default_factory=dict)
    rejected_patterns: list[tuple[str, str, str | list[str]]] = Field(default_factory=list)


class ConflictRemovalResult(StageResult):
    """Output from conflict removal stage."""

    corrections: list[Correction] = Field(default_factory=list)
    removed_corrections: list[tuple[str, str, str, str, BoundaryType]] = Field(default_factory=list)
    conflicts_removed: int = Field(0, ge=0)


class OutputGenerationResult(StageResult):
    """Output from output generation stage."""

    files_written: int = Field(0, ge=0)
