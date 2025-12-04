"""Espanso platform backend implementation."""

from pathlib import Path
import sys
from typing import Any

from loguru import logger

from entroppy.core import Config, Correction
from entroppy.core.types import MatchDirection
from entroppy.platforms.base import PlatformBackend, PlatformConstraints
from entroppy.platforms.espanso.file_writing import write_yaml_files
from entroppy.platforms.espanso.organization import organize_by_letter
from entroppy.platforms.espanso.ram_estimation import estimate_ram_usage
from entroppy.platforms.espanso.reports import generate_espanso_output_report
from entroppy.platforms.espanso.yaml_conversion import correction_to_yaml_dict
from entroppy.platforms.espanso.yaml_helpers import write_yaml_to_stream


class EspansoBackend(PlatformBackend):
    """Backend for Espanso text expander.

    Characteristics:
    - Matches left-to-right
    - Unlimited corrections
    - Full Unicode support
    - Runtime conflict handling
    - YAML output format
    """

    def __init__(self):
        """Initialize Espanso backend with storage for report metadata."""
        self._corrections_by_letter = {}
        self._ram_estimate = {}

    def get_constraints(self) -> PlatformConstraints:
        """Return Espanso constraints (minimal - very permissive)."""
        return PlatformConstraints(
            max_corrections=None,
            max_typo_length=None,
            max_word_length=None,
            allowed_chars=None,
            supports_boundaries=True,
            match_direction=MatchDirection.LEFT_TO_RIGHT,
        )

    def rank_corrections(
        self,
        corrections: list[Correction],
        patterns: list[Correction],
        pattern_replacements: dict[Correction, list[Correction]],
        user_words: set[str],
        config: Config | None = None,
    ) -> list[Correction]:
        """Espanso ranking (passthrough - no prioritization needed)."""
        return corrections

    def generate_output(
        self, corrections: list[Correction], output_path: str | None, config: Config
    ) -> None:
        """Generate Espanso YAML output."""
        if config.verbose:
            logger.info(f"Sorting {len(corrections)} corrections...")
        sorted_corrections = sorted(corrections, key=lambda c: (c[1], c[0]))
        if config.verbose:
            logger.info("Sorting complete.")

        # Estimate RAM usage and store for report
        self._ram_estimate = estimate_ram_usage(sorted_corrections, config.verbose)

        if output_path:
            self._corrections_by_letter = organize_by_letter(sorted_corrections, config.verbose)
            write_yaml_files(
                self._corrections_by_letter,
                output_path,
                config.verbose,
                config.max_entries_per_file,
                config.jobs,
            )
        else:
            yaml_dicts = [correction_to_yaml_dict(c) for c in sorted_corrections]
            yaml_output = {"matches": yaml_dicts}
            write_yaml_to_stream(yaml_output, sys.stdout, "writing to stdout")

    def generate_platform_report(
        self,
        final_corrections: list[Correction],
        ranked_corrections_before_limit: list[Correction],
        all_corrections: list[Correction],
        patterns: list[Correction],
        pattern_replacements: dict[Correction, list[Correction]],
        user_words: set[str],
        report_dir: Path,
        config: Config,
    ) -> dict[str, Any]:
        """Generate Espanso output summary report."""
        return generate_espanso_output_report(
            final_corrections,
            self._corrections_by_letter,
            self._ram_estimate,
            config.max_entries_per_file,
            report_dir,
        )
