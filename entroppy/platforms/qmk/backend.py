"""QMK platform backend implementation."""

from pathlib import Path
from typing import Any

from entroppy.core import Config, Correction
from entroppy.platforms.base import MatchDirection, PlatformBackend, PlatformConstraints
from entroppy.platforms.qmk.filtering import filter_corrections as qmk_filter_corrections
from entroppy.platforms.qmk.output import generate_output as qmk_generate_output
from entroppy.platforms.qmk.ranking import (
    _build_pattern_sets,
    rank_corrections as qmk_rank_corrections,
)
from entroppy.platforms.qmk.reports import generate_qmk_ranking_report
from entroppy.utils import Constants


class QMKBackend(PlatformBackend):
    """
    Backend for QMK firmware autocorrect.

    Characteristics:
    - Matches right-to-left
    - Limited corrections
        (theoretical max depends on flash size, default 6000)
    - Alphas + apostrophe only
    - Compile-time validation (rejects overlapping patterns)
    - Text output format
    """

    # QMK character constraints
    ALLOWED_CHARS = set("abcdefghijklmnopqrstuvwxyz'")

    def __init__(self):
        """Initialize QMK backend with storage for scoring metadata."""
        # Store scoring information for report generation
        self._user_corrections = []
        self._pattern_scores = []
        self._direct_scores = []
        # Cache for pattern sets to avoid rebuilding on every ranking call
        self._cached_pattern_typos: set[tuple[str, str]] | None = None
        self._cached_replaced_by_patterns: set[tuple[str, str]] | None = None

    def get_constraints(self) -> PlatformConstraints:
        """Return QMK constraints."""
        return PlatformConstraints(
            max_corrections=Constants.QMK_MAX_CORRECTIONS,  # Theoretical max, user-configurable
            max_typo_length=Constants.QMK_MAX_STRING_LENGTH,  # QMK string length limit
            max_word_length=Constants.QMK_MAX_STRING_LENGTH,
            allowed_chars=self.ALLOWED_CHARS,
            supports_boundaries=True,  # Via ':' notation
            supports_case_propagation=True,
            supports_regex=False,
            match_direction=MatchDirection.RIGHT_TO_LEFT,
            output_format="text",
        )

    def filter_corrections(
        self, corrections: list[Correction], config: Config
    ) -> tuple[list[Correction], dict[str, Any]]:
        """
        Apply QMK-specific filtering.

        - Character set validation (only a-z and ')
        - Same-typo-text conflict detection (different boundaries)
        - Suffix conflict detection (RTL matching optimization)
        - Substring conflict detection (QMK's hard constraint)
        """
        return qmk_filter_corrections(corrections)

    def rank_corrections(
        self,
        corrections: list[Correction],
        patterns: list[Correction],
        pattern_replacements: dict[Correction, list[Correction]],
        user_words: set[str],
        config: Config | None = None,
    ) -> list[Correction]:
        """
        Rank corrections by QMK-specific usefulness.

        Three-tier system:
        1. User words (infinite priority)
        2. Patterns (scored by sum of replaced word frequencies)
        3. Direct corrections (scored by word frequency)

        Applies max_corrections limit if specified in config.
        Uses cached pattern sets to avoid rebuilding on every call.
        """
        max_corrections = config.max_corrections if config else None

        # Build or use cached pattern sets
        if self._cached_pattern_typos is None or self._cached_replaced_by_patterns is None:
            self._cached_pattern_typos, self._cached_replaced_by_patterns = _build_pattern_sets(
                patterns, pattern_replacements
            )

        (
            ranked,
            self._user_corrections,
            self._pattern_scores,
            self._direct_scores,
            _,
        ) = qmk_rank_corrections(
            corrections,
            patterns,
            pattern_replacements,
            user_words,
            max_corrections,
            self._cached_pattern_typos,
            self._cached_replaced_by_patterns,
        )

        return ranked

    def generate_output(
        self, corrections: list[Correction], output_path: str | None, config: Config
    ) -> None:
        """
        Generate QMK text output.

        Format:
        typo -> correction
        :typo -> correction
        typo: -> correction
        :typo: -> correction

        Sorted alphabetically by correction word.
        """
        qmk_generate_output(corrections, output_path, config)

    def generate_platform_report(
        self,
        final_corrections: list[Correction],
        ranked_corrections_before_limit: list[Correction],
        filtered_corrections: list[Correction],
        patterns: list[Correction],
        pattern_replacements: dict[Correction, list[Correction]],
        user_words: set[str],
        filter_metadata: dict[str, Any],
        report_dir: Path,
        config: Config,
    ) -> dict[str, Any]:
        """Generate QMK ranking report."""
        return generate_qmk_ranking_report(
            final_corrections,
            ranked_corrections_before_limit,
            filtered_corrections,
            patterns,
            pattern_replacements,
            self._user_corrections,
            self._pattern_scores,
            self._direct_scores,
            filter_metadata,
            report_dir,
        )
