"""Base classes and types for platform abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from entroppy.core.types import MatchDirection

if TYPE_CHECKING:
    from entroppy.core.config import Config
    from entroppy.core.types import Correction


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

    # Behavior
    match_direction: MatchDirection


class PlatformBackend(ABC):
    """Abstract base class for platform-specific behavior."""

    @abstractmethod
    def get_constraints(self) -> PlatformConstraints:
        """Return platform-specific constraints and capabilities."""

    @abstractmethod
    def rank_corrections(
        self,
        corrections: list["Correction"],
        patterns: list["Correction"],
        pattern_replacements: dict["Correction", list["Correction"]],
        user_words: set[str],
        config: "Config" | None = None,
    ) -> list["Correction"]:
        """Rank corrections by platform-specific usefulness.

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
        """Generate platform-specific output format.

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
        all_corrections: list["Correction"],
        patterns: list["Correction"],
        pattern_replacements: dict["Correction", list["Correction"]],
        user_words: set[str],
        report_dir: Path,
        config: "Config",
    ) -> dict[str, Any]:
        """Generate platform-specific report.

        Args:
            final_corrections: Final corrections after limit applied
            ranked_corrections_before_limit: All ranked corrections before applying limit
            all_corrections: All corrections (direct + patterns)
            patterns: Pattern corrections
            pattern_replacements: Map of pattern -> list of corrections it replaces
            user_words: User-specified words
            report_dir: Directory to write report to (Path object)
            config: Configuration object

        Returns:
            Dictionary containing report metadata (file path, statistics, etc.)
        """

    def get_name(self) -> str:
        """Return platform name for display."""
        return self.__class__.__name__.replace("Backend", "").lower()
