"""Data models for passing information between pipeline stages."""

from pydantic import BaseModel, Field

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

    typo_map: dict[str, list[str]] = Field(default_factory=dict)
    debug_messages: list[str] = Field(default_factory=list)
