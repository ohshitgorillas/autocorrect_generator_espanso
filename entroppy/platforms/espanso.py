"""Espanso platform backend implementation."""

import os
from collections import defaultdict
from multiprocessing import Pool

import yaml
from loguru import logger

from .espanso_report import generate_espanso_output_report
from .base import (
    PlatformBackend,
    PlatformConstraints,
    MatchDirection,
)
from ..config import BoundaryType, Correction, Config


class EspansoBackend(PlatformBackend):
    """
    Backend for Espanso text expander.

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
            supports_case_propagation=True,
            supports_regex=True,
            match_direction=MatchDirection.LEFT_TO_RIGHT,
            output_format="yaml",
        )

    def filter_corrections(
        self, corrections: list[Correction], config: Config
    ) -> tuple[list[Correction], dict]:
        """Espanso filtering (minimal - accepts everything)."""
        metadata = {
            "total_input": len(corrections),
            "total_output": len(corrections),
            "filtered_count": 0,
            "filter_reasons": {},
        }

        return corrections, metadata

    def rank_corrections(
        self,
        corrections: list[Correction],
        patterns: list[Correction],
        pattern_replacements: dict,
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
        self._ram_estimate = self._estimate_ram_usage(sorted_corrections, config.verbose)

        if output_path:
            self._corrections_by_letter = self._organize_by_letter(
                sorted_corrections, config.verbose
            )
            self._write_yaml_files(
                self._corrections_by_letter,
                output_path,
                config.verbose,
                config.max_entries_per_file,
                config.jobs,
            )
        else:
            yaml_dicts = [self._correction_to_yaml_dict(c) for c in sorted_corrections]
            yaml_output = {"matches": yaml_dicts}
            yaml.safe_dump(
                yaml_output,
                sys.stdout,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
                width=float("inf"),
            )

    # Private helper methods for YAML generation

    def _correction_to_yaml_dict(self, correction: Correction) -> dict:
        """Convert correction to Espanso match dict."""
        typo, word, boundary = correction

        match_dict = {"trigger": typo, "replace": word, "propagate_case": True}

        if boundary == BoundaryType.BOTH:
            match_dict["word"] = True
        elif boundary == BoundaryType.LEFT:
            match_dict["left_word"] = True
        elif boundary == BoundaryType.RIGHT:
            match_dict["right_word"] = True

        return match_dict

    def _organize_by_letter(
        self, corrections: list[Correction], verbose: bool = False
    ) -> dict[str, list[dict]]:
        """Group corrections by first letter of correct word."""
        by_letter = defaultdict(list)

        if verbose:
            logger.info(f"Organizing {len(corrections)} corrections...")

        for correction in corrections:
            _, word, _ = correction

            first_char = word[0].lower() if word else ""

            if first_char.isalpha():
                file_key = first_char
            else:
                file_key = "symbols"

            yaml_dict = self._correction_to_yaml_dict(correction)
            by_letter[file_key].append(yaml_dict)

        return by_letter

    def _estimate_ram_usage(
        self, corrections: list[Correction], verbose: bool = False
    ) -> dict[str, float]:
        """Estimate RAM usage of generated corrections."""
        avg_trigger_len = (
            sum(len(c[0]) for c in corrections) / len(corrections) if corrections else 0
        )
        avg_replace_len = (
            sum(len(c[1]) for c in corrections) / len(corrections) if corrections else 0
        )

        per_entry_bytes = (
            avg_trigger_len  # trigger string
            + avg_replace_len  # replace string
            + 20  # "propagate_case: true"
            + 15  # boundary property if present
            + 25  # YAML formatting overhead
        )

        total_bytes = per_entry_bytes * len(corrections)
        total_kb = total_bytes / 1024
        total_mb = total_kb / 1024

        estimate = {
            "entries": len(corrections),
            "avg_trigger_len": round(avg_trigger_len, 1),
            "avg_replace_len": round(avg_replace_len, 1),
            "per_entry_bytes": round(per_entry_bytes, 1),
            "total_bytes": round(total_bytes, 1),
            "total_kb": round(total_kb, 2),
            "total_mb": round(total_mb, 3),
        }

        if verbose:
            logger.info("\n# RAM Usage Estimate:")
            logger.info(f"#   {estimate['entries']} corrections")
            logger.info(
                f"#   ~{estimate['per_entry_bytes']:.0f} bytes per entry"
            )
            logger.info(
                f"#   Total: {estimate['total_kb']:.1f} KB ({estimate['total_mb']:.2f} MB)"
            )
            logger.info("#   (Espanso runtime overhead not included)")

        return estimate

    def _write_single_yaml_file(self, args: tuple) -> tuple[str, int]:
        """Worker function to write a single YAML file."""
        filename, chunk = args

        yaml_output = {"matches": chunk}

        with open(filename, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                yaml_output,
                f,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
                width=float("inf"),
            )

        return (os.path.basename(filename), len(chunk))

    def _write_yaml_files(
        self,
        corrections_by_letter: dict[str, list[dict]],
        output_dir: str,
        verbose: bool,
        max_entries_per_file: int = 500,
        jobs: int = 1,
    ) -> None:
        """Write YAML files in parallel, splitting large files into chunks."""
        output_dir = os.path.expanduser(output_dir)
        os.makedirs(output_dir, exist_ok=True)

        write_tasks = []

        for letter, matches in sorted(corrections_by_letter.items()):
            matches_sorted = sorted(matches, key=lambda m: m["replace"])

            for i in range(0, len(matches_sorted), max_entries_per_file):
                chunk = matches_sorted[i : i + max_entries_per_file]

                first_word = chunk[0]["replace"]
                last_word = chunk[-1]["replace"]

                if letter == "symbols":
                    if len(matches_sorted) <= max_entries_per_file:
                        filename = os.path.join(output_dir, "typos_symbols.yml")
                    else:
                        chunk_num = i // max_entries_per_file + 1
                        filename = os.path.join(
                            output_dir, f"typos_symbols_{chunk_num:03d}.yml"
                        )
                else:
                    if len(matches_sorted) <= max_entries_per_file:
                        filename = os.path.join(output_dir, f"typos_{letter}.yml")
                    else:
                        filename = os.path.join(
                            output_dir, f"typos_{first_word}_to_{last_word}.yml"
                        )

                write_tasks.append((filename, chunk))

        total_entries = 0
        total_files = 0

        if jobs > 1 and len(write_tasks) > 1:
            if verbose:
                logger.info(
                    f"Writing {len(write_tasks)} YAML files using {jobs} workers..."
                )

            with Pool(processes=jobs) as pool:
                results = pool.map(self._write_single_yaml_file, write_tasks)

                for _, entry_count in results:
                    total_entries += entry_count
                    total_files += 1
        else:
            if verbose:
                logger.info(f"Writing {len(write_tasks)} YAML files...")

            for filename, chunk in write_tasks:
                _, entry_count = self._write_single_yaml_file((filename, chunk))
                total_entries += entry_count
                total_files += 1

        if verbose:
            logger.info(
                f"\nTotal: {total_entries} corrections across {total_files} files"
            )

    def generate_platform_report(
        self,
        final_corrections: list[Correction],
        ranked_corrections_before_limit: list[Correction],
        filtered_corrections: list[Correction],
        patterns: list[Correction],
        pattern_replacements: dict,
        user_words: set[str],
        filter_metadata: dict,
        report_dir,
        config: Config,
    ) -> dict:
        """Generate Espanso output summary report."""
        return generate_espanso_output_report(
            final_corrections,
            self._corrections_by_letter,
            self._ram_estimate,
            config.max_entries_per_file,
            report_dir,
        )
