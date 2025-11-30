"""Report generation for autocorrect pipeline."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from loguru import logger

from entroppy.core import BoundaryType, Correction


@dataclass
class ReportData:
    """Collects data throughout the pipeline for reporting."""

    # Timing
    stage_times: dict[str, float] = field(default_factory=dict)
    start_time: float = 0.0

    # Collisions
    skipped_collisions: list[tuple[str, list[str], float]] = field(default_factory=list)

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
    filter_metadata: dict = field(default_factory=dict)


def _format_boundary(boundary: BoundaryType) -> str:
    """Format boundary type for display."""
    if boundary == BoundaryType.NONE:
        return "no boundary"
    if boundary == BoundaryType.LEFT:
        return "LEFT boundary"
    if boundary == BoundaryType.RIGHT:
        return "RIGHT boundary"
    if boundary == BoundaryType.BOTH:
        return "BOTH boundaries"
    return str(boundary)


def _format_time(seconds: float) -> str:
    """Format seconds into human-readable time."""
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, secs = divmod(seconds, 60)
    return f"{int(minutes)}m {secs:.1f}s"


def write_report_header(f, title: str):
    """Write a standard report header with title and timestamp.

    Args:
        f: File object to write to
        title: Title of the report
    """
    f.write("=" * 80 + "\n")
    f.write(f"{title}\n")
    f.write("=" * 80 + "\n")
    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")


def generate_summary_report(data: ReportData, report_dir: Path) -> None:
    """Generate summary report."""
    filepath = report_dir / "summary.txt"
    total_time = sum(data.stage_times.values())

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("AUTOCORRECT GENERATION SUMMARY\n")
        f.write("=" * 70 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # Processing stats
        f.write("PROCESSING STATISTICS\n")
        f.write("-" * 70 + "\n")
        f.write(f"Words processed:                    {data.words_processed:,}\n")
        f.write(f"Corrections generated:              {data.corrections_before_generalization:,}\n")
        f.write(f"After pattern generalization:       {data.corrections_after_generalization:,}\n")
        f.write(f"After conflict removal:             {data.corrections_after_conflicts:,}\n")
        f.write(f"Final corrections:                  {data.total_corrections:,}\n\n")

        # Optimizations
        f.write("OPTIMIZATIONS\n")
        f.write("-" * 70 + "\n")
        patterns_count = len(data.generalized_patterns)
        replaced_count = sum(len(v) for v in data.pattern_replacements.values())
        f.write(f"Patterns generalized:               {patterns_count:,}\n")
        f.write(f"Specific corrections replaced:      {replaced_count:,}\n")
        f.write(f"Substring conflicts removed:        {len(data.removed_conflicts):,}\n\n")

        # Skipped items
        f.write("SKIPPED ITEMS\n")
        f.write("-" * 70 + "\n")
        f.write(f"Ambiguous collisions:               {len(data.skipped_collisions):,}\n")
        f.write(f"Too-short typos:                    {len(data.skipped_short):,}\n")
        f.write(f"Excluded by rules:                  {len(data.excluded_corrections):,}\n")
        f.write(f"Rejected patterns:                  {len(data.rejected_patterns):,}\n\n")

        # Timing
        if data.stage_times:
            f.write("TIMING BREAKDOWN\n")
            f.write("-" * 70 + "\n")
            for stage, duration in data.stage_times.items():
                pct = (duration / total_time * 100) if total_time > 0 else 0
                f.write(f"{stage:<35} {_format_time(duration):>12} ({pct:>5.1f}%)\n")
            f.write("-" * 70 + "\n")
            f.write(f"{'Total':<35} {_format_time(total_time):>12}\n")


def generate_collisions_report(data: ReportData, report_dir: Path) -> None:
    """Generate ambiguous collisions report."""
    if not data.skipped_collisions:
        return

    filepath = report_dir / "collisions.txt"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("AMBIGUOUS COLLISIONS REPORT\n")
        f.write("=" * 70 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("These typos map to multiple words with similar frequencies and were\n")
        f.write("skipped. To force a correction, add unwanted mappings to your\n")
        f.write("exclusion file.\n\n")
        f.write(f"Total skipped: {len(data.skipped_collisions)}\n")
        f.write("=" * 70 + "\n\n")

        # Sort by ratio (closest ambiguities first)
        sorted_collisions = sorted(data.skipped_collisions, key=lambda x: x[2])

        for typo, words, ratio in sorted_collisions:
            f.write(f"{typo} → {words}\n")
            f.write(f"  Ratio: {ratio:.2f}\n")
            f.write("\n")


def generate_patterns_report(data: ReportData, report_dir: Path) -> None:
    """Generate pattern generalization report."""
    filepath = report_dir / "patterns.txt"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("PATTERN GENERALIZATION REPORT\n")
        f.write("=" * 70 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        patterns_count = len(data.generalized_patterns)
        replaced_count = sum(len(v) for v in data.pattern_replacements.values())
        f.write(f"Generalized {patterns_count} patterns, ")
        f.write(f"replacing {replaced_count} specific corrections.\n")
        f.write("=" * 70 + "\n\n")

        if data.generalized_patterns:
            f.write("GENERALIZED PATTERNS\n")
            f.write("-" * 70 + "\n\n")
            for typo_suffix, word_suffix, boundary, count in data.generalized_patterns:
                f.write(f"✓ {typo_suffix} → {word_suffix} ({_format_boundary(boundary)})\n")
                f.write(f"  Replaced {count} specific corrections\n")

                # Show what was replaced
                pattern_key = (typo_suffix, word_suffix, boundary)
                if pattern_key in data.pattern_replacements:
                    replacements = data.pattern_replacements[pattern_key][:10]
                    for typo, word, _ in replacements:
                        f.write(f"    - {typo} → {word}\n")
                f.write("\n")

        if data.rejected_patterns:
            f.write("\nREJECTED PATTERNS\n")
            f.write("-" * 70 + "\n\n")
            for pattern_typo, pattern_word, reason in data.rejected_patterns:
                f.write(f"✗ {pattern_typo} → {pattern_word}\n")
                f.write(f"  Reason: {reason}\n\n")


def generate_conflicts_report(data: ReportData, report_dir: Path) -> None:
    """Generate substring conflicts reports (one per boundary type)."""
    if not data.removed_conflicts:
        return

    # Group by boundary type
    by_boundary = {}
    for (
        long_typo,
        long_word,
        short_typo,
        short_word,
        boundary,
    ) in data.removed_conflicts:
        if boundary not in by_boundary:
            by_boundary[boundary] = []
        by_boundary[boundary].append((long_typo, long_word, short_typo, short_word))

    # Create a separate file for each boundary type
    boundary_file_map = {
        BoundaryType.NONE: "conflicts_none.txt",
        BoundaryType.LEFT: "conflicts_left.txt",
        BoundaryType.RIGHT: "conflicts_right.txt",
        BoundaryType.BOTH: "conflicts_both.txt",
    }

    for boundary, conflicts in by_boundary.items():
        filename = boundary_file_map.get(boundary, f"conflicts_{boundary.value}.txt")
        filepath = report_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("=" * 70 + "\n")
            f.write(f"SUBSTRING CONFLICTS - {_format_boundary(boundary).upper()}\n")
            f.write("=" * 70 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("These corrections were removed because a shorter typo would trigger\n")
            f.write("first, making them unreachable in Espanso.\n\n")
            f.write(f"Total removed: {len(conflicts)}\n")
            f.write("=" * 70 + "\n\n")

            # Group by correction word for compact display
            by_word = {}
            for long_typo, long_word, short_typo, short_word in conflicts:
                if long_word not in by_word:
                    by_word[long_word] = []
                by_word[long_word].append((long_typo, short_typo, short_word))

            # Write grouped conflicts
            for word in sorted(by_word.keys()):
                entries = by_word[word]
                f.write(f"{word} ({len(entries)} blocked typo{'s' if len(entries) != 1 else ''})\n")

                # Show up to 20 typos, then summarize
                for long_typo, short_typo, short_word in entries[:20]:
                    f.write(f"  {long_typo} ← {short_typo} → {short_word}\n")

                f.write("\n")


def generate_short_typos_report(data: ReportData, report_dir: Path) -> None:
    """Generate short typos report."""
    if not data.skipped_short:
        return

    filepath = report_dir / "short_typos.txt"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("SHORT TYPOS REPORT\n")
        f.write("=" * 70 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("These typos were skipped for being too short.\n")
        f.write("Consider adjusting --min-typo-length if needed.\n\n")
        f.write(f"Total skipped: {len(data.skipped_short)}\n")
        f.write("=" * 70 + "\n\n")

        # Group by length
        by_length = {}
        for typo, word, length in data.skipped_short:
            if length not in by_length:
                by_length[length] = []
            by_length[length].append((typo, word))

        for length in sorted(by_length.keys()):
            items = by_length[length]
            f.write(f"\nLENGTH {length} ({len(items)} typos)\n")
            f.write("-" * 70 + "\n")
            for typo, word in items[:30]:
                f.write(f"{typo} → {word}\n")
            remaining = len(items) - 30
            if remaining > 0:
                f.write(f"... and {remaining} more\n")


def generate_exclusions_report(data: ReportData, report_dir: Path) -> None:
    """Generate exclusions report."""
    if not data.excluded_corrections:
        return

    filepath = report_dir / "exclusions.txt"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("EXCLUSIONS REPORT\n")
        f.write("=" * 70 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("These corrections were blocked by exclusion rules.\n\n")
        f.write(f"Total excluded: {len(data.excluded_corrections)}\n")
        f.write("=" * 70 + "\n\n")

        for typo, word, rule in data.excluded_corrections[:100]:
            f.write(f"{typo} → {word}\n")
            f.write(f"  Blocked by rule: {rule}\n\n")

        remaining = len(data.excluded_corrections) - 100
        if remaining > 0:
            f.write(f"... and {remaining} more (showing first 100)\n")


def generate_statistics_csv(data: ReportData, report_dir: Path) -> None:
    """Generate machine-readable statistics CSV."""
    filepath = report_dir / "statistics.csv"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("metric,value\n")
        f.write(f"words_processed,{data.words_processed}\n")
        f.write(f"corrections_before_generalization,{data.corrections_before_generalization}\n")
        f.write(f"corrections_after_generalization,{data.corrections_after_generalization}\n")
        f.write(f"corrections_after_conflicts,{data.corrections_after_conflicts}\n")
        f.write(f"total_corrections,{data.total_corrections}\n")
        f.write(f"patterns_generalized,{len(data.generalized_patterns)}\n")
        replaced_count = sum(len(v) for v in data.pattern_replacements.values())
        f.write(f"specific_corrections_replaced,{replaced_count}\n")
        f.write(f"substring_conflicts_removed,{len(data.removed_conflicts)}\n")
        f.write(f"ambiguous_collisions_skipped,{len(data.skipped_collisions)}\n")
        f.write(f"short_typos_skipped,{len(data.skipped_short)}\n")
        f.write(f"excluded_corrections,{len(data.excluded_corrections)}\n")
        f.write(f"rejected_patterns,{len(data.rejected_patterns)}\n")

        # Timing
        for stage, duration in data.stage_times.items():
            stage_key = stage.lower().replace(" ", "_")
            f.write(f"time_{stage_key},{duration:.3f}\n")
        total_time = sum(data.stage_times.values())
        f.write(f"time_total,{total_time:.3f}\n")


def generate_reports(
    data: ReportData,
    reports_path: str,
    platform_name: str,
    verbose: bool = False,
) -> Path:
    """Generate all reports in a timestamped directory.

    Args:
        data: Report data collected during pipeline execution
        reports_path: Base path for reports directory
        platform_name: Platform name to include in folder name
        verbose: Whether to print progress messages

    Returns:
        Path to the created report directory
    """
    # Create timestamped directory with platform name
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    folder_name = f"{timestamp}_{platform_name}"
    report_dir = Path(reports_path) / folder_name
    report_dir.mkdir(parents=True, exist_ok=True)

    if verbose:
        logger.info(f"\nGenerating reports in {report_dir}/")

    # Generate all report files
    generate_summary_report(data, report_dir)
    generate_collisions_report(data, report_dir)
    generate_patterns_report(data, report_dir)
    generate_conflicts_report(data, report_dir)
    generate_short_typos_report(data, report_dir)
    generate_exclusions_report(data, report_dir)
    generate_statistics_csv(data, report_dir)

    if verbose:
        logger.info("✓ Reports generated successfully")

    return report_dir
