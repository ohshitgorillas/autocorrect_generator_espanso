"""Structured report writing functions for debug reports."""

from pathlib import Path
from typing import TextIO

from entroppy.core import format_boundary_display
from entroppy.core.patterns.data_models import (
    IterationData,
    PatternExtraction,
    PatternValidation,
    RankingInfo,
    TypoLifecycle,
)
from entroppy.reports.helpers import (
    write_report_header,
    write_section_header,
    write_subsection_header,
)
from entroppy.utils.helpers import write_file_safely


def write_pattern_extraction_section(
    extractions: list[PatternExtraction],
    f: TextIO,
) -> None:
    """Write pattern extraction section with all occurrences.

    Args:
        extractions: List of pattern extraction events
        f: File to write to
    """
    if not extractions:
        return

    f.write("  Pattern Extraction:\n")
    for extraction in extractions:
        f.write(
            f"    Pattern found: '{extraction.typo_pattern}' → "
            f"'{extraction.word_pattern}' "
            f"(boundary={extraction.boundary}, {extraction.occurrence_count} occurrences)\n"
        )
        if extraction.occurrences:
            f.write("      Occurrences:\n")
            for typo_occ, word_occ, boundary_occ in extraction.occurrences:
                f.write(f"        - '{typo_occ}' → '{word_occ}' (boundary={boundary_occ})\n")
    f.write("\n")


def _write_accepted_validation(validation: PatternValidation, f: TextIO) -> None:
    """Write a single accepted validation entry."""
    boundary_str = f"({validation.boundary})" if validation.boundary else ""
    f.write(
        f"    ACCEPTED: '{validation.typo_pattern}' → "
        f"'{validation.word_pattern}' {boundary_str}\n"
    )
    if validation.replaces_count is not None:
        f.write(f"      Replaces {validation.replaces_count} corrections:\n")
        if validation.replaces:
            for typo_repl, word_repl in validation.replaces[:20]:  # Show first 20
                f.write(f"        - '{typo_repl}' → '{word_repl}'\n")
            if len(validation.replaces) > 20:
                f.write(f"        ... and {len(validation.replaces) - 20} more\n")


def _write_rejected_validation(validation: PatternValidation, f: TextIO) -> None:
    """Write a single rejected validation entry."""
    boundary_str = f"({validation.boundary})" if validation.boundary else ""
    f.write(
        f"    REJECTED: '{validation.typo_pattern}' → "
        f"'{validation.word_pattern}' {boundary_str}\n"
    )
    if validation.reason:
        f.write(f"      Reason: {validation.reason}\n")
    if validation.occurrences:
        f.write("      Occurrences: ")
        occ_strs = [f"{t}→{w}" for t, w in validation.occurrences[:5]]
        f.write(", ".join(occ_strs))
        if len(validation.occurrences) > 5:
            f.write(f", ... and {len(validation.occurrences) - 5} more")
        f.write("\n")


def write_pattern_validation_section(
    validations: list[PatternValidation],
    f: TextIO,
) -> None:
    """Write pattern validation section.

    Args:
        validations: List of pattern validation events
        f: File to write to
    """
    if not validations:
        return

    f.write("  Pattern Validation:\n")

    # Separate ACCEPTED and REJECTED
    accepted = [v for v in validations if v.status == "ACCEPTED"]
    rejected = [v for v in validations if v.status == "REJECTED"]

    # Write accepted patterns
    for validation in accepted:
        _write_accepted_validation(validation, f)

    # Write rejected patterns
    for validation in rejected:
        _write_rejected_validation(validation, f)

    f.write("\n")


def _write_solver_trace(iter_data: IterationData, f: TextIO) -> None:
    """Write solver trace section.

    Args:
        iter_data: Iteration data
        f: File to write to
    """
    if not iter_data.solver_events:
        return

    write_subsection_header(f, "Solver Trace:")
    for entry in sorted(iter_data.solver_events, key=lambda e: e.pass_name):
        boundary_str = format_boundary_display(entry.boundary)
        f.write(
            f"  [{entry.pass_name}] {entry.action}: "
            f"{entry.typo} -> {entry.word} ({boundary_str})\n"
        )
        if entry.reason:
            for line in entry.reason.split("\n"):
                if line.strip():
                    f.write(f"    Reason: {line.strip()}\n")
    f.write("\n")


def _write_pattern_sections(iter_data: IterationData, f: TextIO) -> None:
    """Write pattern extraction and validation sections.

    Args:
        iter_data: Iteration data
        f: File to write to
    """
    # Write pattern extractions
    if iter_data.pattern_extractions:
        write_subsection_header(f, "[PatternGeneralization]")
        write_pattern_extraction_section(iter_data.pattern_extractions, f)

    # Write pattern validations
    if iter_data.pattern_validations:
        # Check if we already wrote the header in pattern extractions
        if not iter_data.pattern_extractions:
            write_subsection_header(f, "[PatternGeneralization]")
        write_pattern_validation_section(iter_data.pattern_validations, f)


def _write_platform_conflicts(
    iter_data: IterationData, f: TextIO, include_conflict_details: bool
) -> None:
    """Write platform conflicts section.

    Args:
        iter_data: Iteration data
        f: File to write to
        include_conflict_details: Whether to include conflict details
    """
    if not iter_data.platform_conflicts:
        return

    f.write("  Platform Conflicts:\n")
    for conflict in iter_data.platform_conflicts:
        f.write(
            f"    {conflict.conflict_type}: {conflict.typo} → {conflict.word} "
            f"({conflict.boundary}) - {conflict.result}\n"
        )
        if include_conflict_details:
            f.write(f"      {conflict.details}\n")
    f.write("\n")


def write_iteration_section(
    iter_data: IterationData,
    iteration: int,
    f: TextIO,
    include_conflict_details: bool = False,
) -> None:
    """Write a single iteration section.

    Args:
        iter_data: Iteration data to write
        iteration: Iteration number
        f: File to write to
        include_conflict_details: Whether to include conflict details (for typo reports)
    """
    write_section_header(f, f"ITERATION {iteration}")

    _write_solver_trace(iter_data, f)
    _write_pattern_sections(iter_data, f)
    _write_platform_conflicts(iter_data, f, include_conflict_details)

    f.write("\n")


def write_ranking_section(
    ranking: RankingInfo | None,
    f: TextIO,
    include_header: bool = True,
) -> None:
    """Write ranking section.

    Args:
        ranking: Ranking information object
        f: File to write to
        include_header: Whether to include the section header
    """
    if not ranking:
        return

    if include_header:
        write_section_header(f, "STAGE 7: RANKING")

    f.write(f"  Classification: {ranking.classification}")
    if ranking.tier is not None:
        tier_names = {0: "User", 1: "Pattern", 2: "Direct Correction"}
        tier_name = tier_names.get(ranking.tier, f"Tier {ranking.tier}")
        f.write(f" (Tier {ranking.tier}: {tier_name})")
    f.write("\n")

    if ranking.score is not None:
        f.write(f"  Score: {ranking.score:.2e}\n")

    if ranking.overall_position is not None:
        f.write(f"  Overall Position: {ranking.overall_position}\n")

    if ranking.tier_position is not None:
        f.write(f"  Tier Position: {ranking.tier_position}\n")

    if ranking.final_status:
        f.write(f"  Final Status: {ranking.final_status}")
        if ranking.limit is not None:
            f.write(f" - position {ranking.overall_position} (within limit of {ranking.limit})")
        f.write("\n")

    f.write("\n")


def write_typo_report_from_lifecycle(
    lifecycle: TypoLifecycle,
    filepath: Path,
) -> None:
    """Write a typo report from a TypoLifecycle object.

    Args:
        lifecycle: TypoLifecycle object with all structured data
        filepath: Path to write the report to
    """

    def write_content(f: TextIO) -> None:
        pattern_info = (
            f" (matched: {', '.join(lifecycle.matched_patterns)})"
            if lifecycle.matched_patterns
            else ""
        )
        write_report_header(f, f"DEBUG TYPO LIFECYCLE REPORT: {lifecycle.typo}{pattern_info}")

        f.write(f'Typo: "{lifecycle.typo}"\n')
        if lifecycle.matched_patterns:
            f.write(f"Matched patterns: {', '.join(lifecycle.matched_patterns)}\n")
        if lifecycle.target_word:
            f.write(f"Target word: {lifecycle.target_word}\n")
        f.write("\n")

        # Write Stage 2 events
        if lifecycle.stage2_events:
            write_section_header(f, "STAGE 2: TYPO GENERATION")
            for event in lifecycle.stage2_events:
                f.write(f"  {event}\n")
            f.write("\n")

        # Write iterations
        for iteration in sorted(lifecycle.iterations.keys()):
            if iteration == 0:
                continue  # Stage 2 already handled

            iter_data = lifecycle.iterations[iteration]
            write_iteration_section(iter_data, iteration, f, include_conflict_details=True)

            # Write other messages
            if iter_data.other_messages:
                for msg in iter_data.other_messages:
                    f.write(f"  {msg}\n")
                f.write("\n")

        # Write Stage 7 ranking
        if lifecycle.stage7_events:
            for ranking in lifecycle.stage7_events:
                write_ranking_section(ranking, f)

        # Write final summary
        write_section_header(f, "FINAL SUMMARY")
        if lifecycle.final_summary:
            f.write(f"  Final Status: {lifecycle.final_summary.final_status}\n")
            if lifecycle.final_summary.final_pattern:
                f.write(
                    f"  Final Pattern: {lifecycle.final_summary.final_pattern} "
                    f"({lifecycle.final_summary.final_boundary})\n"
                )
            f.write(f"  Total Iterations: {lifecycle.final_summary.total_iterations}\n")
            if lifecycle.final_summary.final_rank:
                f.write(f"  Final Rank: {lifecycle.final_summary.final_rank}\n")

        if lifecycle.iterations:
            f.write(f"Total Iterations: {max(lifecycle.iterations.keys())}\n")

    write_file_safely(filepath, write_content, f"writing debug typo report for {lifecycle.typo}")
