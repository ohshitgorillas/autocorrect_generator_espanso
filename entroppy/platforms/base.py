"""Base classes and types for platform abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class MatchDirection(Enum):
    """Direction in which platform scans for matches."""

    LEFT_TO_RIGHT = "ltr"  # Espanso
    RIGHT_TO_LEFT = "rtl"  # QMK


@dataclass
class PlatformConstraints:
    """Platform-specific constraints and capabilities."""

    # Limits
    max_corrections: int | None  # None = unlimited
    max_typo_length: int | None
    max_word_length: int | None

    # Character support
    allowed_chars: set[str] | None  # None = all characters allowed

    # Features
    supports_boundaries: bool
    supports_case_propagation: bool
    supports_regex: bool

    # Behavior
    match_direction: MatchDirection
    output_format: str  # "yaml", "c_array", "json", etc.


class PlatformBackend(ABC):
    """Abstract base class for platform-specific behavior."""

    @abstractmethod
    def get_constraints(self) -> PlatformConstraints:
        """Return platform-specific constraints and capabilities."""

    @abstractmethod
    def filter_corrections(
        self, corrections: list["Correction"], config: "Config"
    ) -> tuple[list["Correction"], dict[str, Any]]:
        """
        Apply platform-specific filtering.

        Args:
            corrections: List of corrections to filter
            config: Configuration object

        Returns:
            (filtered_corrections, metadata)
            metadata: dict with filtering statistics and removed items
        """

    @abstractmethod
    def rank_corrections(
        self,
        corrections: list["Correction"],
        patterns: list["Correction"],
        pattern_replacements: dict["Correction", list["Correction"]],
        user_words: set[str],
        config: "Config" | None = None,
    ) -> list["Correction"]:
        """
        Rank corrections by platform-specific usefulness.

        Args:
            corrections: All corrections (direct + patterns)
            patterns: Pattern corrections only
            pattern_replacements: Map of pattern -> list of corrections it replaces
            user_words: User-specified words (high priority)
            config: Configuration object (optional, for platform-specific limits)

        Returns:
            Ordered list of corrections (most to least useful)
        """

    @abstractmethod
    def generate_output(
        self, corrections: list["Correction"], output_path: str | None, config: "Config"
    ) -> None:
        """
        Generate platform-specific output format.

        Args:
            corrections: Final list of corrections to output
            output_path: Output directory/file path (None = stdout)
            config: Configuration object
        """

    @abstractmethod
    def generate_platform_report(
        self,
        final_corrections: list["Correction"],
        ranked_corrections_before_limit: list["Correction"],
        filtered_corrections: list["Correction"],
        patterns: list["Correction"],
        pattern_replacements: dict["Correction", list["Correction"]],
        user_words: set[str],
        filter_metadata: dict[str, Any],
        report_dir: Path,
        config: "Config",
    ) -> dict[str, Any]:
        """
        Generate platform-specific report.

        Args:
            final_corrections: Final corrections after limit applied
            ranked_corrections_before_limit: All ranked corrections before applying limit
            filtered_corrections: Corrections after filtering but before ranking
            patterns: Pattern corrections
            pattern_replacements: Map of pattern -> list of corrections it replaces
            user_words: User-specified words
            filter_metadata: Metadata from filter_corrections()
            report_dir: Directory to write report to (Path object)
            config: Configuration object

        Returns:
            Dictionary containing report metadata (file path, statistics, etc.)
        """

    def get_name(self) -> str:
        """Return platform name for display."""
        return self.__class__.__name__.replace("Backend", "").lower()
