"""Report data models."""

from dataclasses import dataclass, field
from typing import Any

from entroppy.core import BoundaryType, Correction


@dataclass
class ReportData:
    """Collects data throughout the pipeline for reporting."""

    # Timing
    stage_times: dict[str, float] = field(default_factory=dict)
    start_time: float = 0.0

    # Collisions
    skipped_collisions: list[tuple[str, list[str], float, BoundaryType]] = field(
        default_factory=list
    )

    # Patterns
    generalized_patterns: list[tuple[str, str, BoundaryType, int]] = field(default_factory=list)
    pattern_replacements: dict[tuple[str, str, BoundaryType], list[Correction]] = field(
        default_factory=dict
    )
    rejected_patterns: list[tuple[str, str, str]] = field(default_factory=list)

    # Conflicts: (long_typo, long_word, blocking_typo, blocking_word, boundary)
    removed_conflicts: list[tuple[str, str, str, str, BoundaryType]] = field(default_factory=list)

    # Short typos
    skipped_short: list[tuple[str, str, int]] = field(default_factory=list)

    # Exclusions
    excluded_corrections: list[tuple[str, str, str]] = field(default_factory=list)

    # Summary stats
    words_processed: int = 0
    corrections_before_generalization: int = 0
    corrections_after_generalization: int = 0
    corrections_after_conflicts: int = 0
    total_corrections: int = 0

    # Platform-specific data for reports
    final_corrections: list[Correction] = field(default_factory=list)
    ranked_corrections_before_limit: list[Correction] = field(default_factory=list)
    filtered_corrections: list[Correction] = field(default_factory=list)
    filter_metadata: dict[str, Any] = field(default_factory=dict)
