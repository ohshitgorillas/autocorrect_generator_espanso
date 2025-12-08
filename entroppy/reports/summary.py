"""Summary report generation."""

from pathlib import Path

from entroppy.reports.data import ReportData
from entroppy.reports.helpers import format_time, write_report_header, write_subsection_header
from entroppy.utils.helpers import write_file_safely


def generate_summary_report(data: ReportData, report_dir: Path) -> None:
    """Generate summary report."""
    filepath = report_dir / "summary.txt"
    total_time = sum(data.stage_times.values())

    def write_summary_content(f):
        write_report_header(f, "AUTOCORRECT GENERATION SUMMARY")

        # Processing stats
        write_subsection_header(f, "PROCESSING STATISTICS", width=70)
        f.write(f"Words processed:                    {data.words_processed:,}\n")
        f.write(f"Corrections generated:              {data.corrections_before_generalization:,}\n")
        f.write(f"After pattern generalization:       {data.corrections_after_generalization:,}\n")
        f.write(f"After conflict removal:             {data.corrections_after_conflicts:,}\n")
        f.write(f"Final corrections:                  {data.total_corrections:,}\n\n")

        # Optimizations
        write_subsection_header(f, "OPTIMIZATIONS", width=70)
        patterns_count = len(data.generalized_patterns)
        replaced_count = sum(len(v) for v in data.pattern_replacements.values())
        f.write(f"Patterns generalized:               {patterns_count:,}\n")
        f.write(f"Specific corrections replaced:      {replaced_count:,}\n")
        f.write(f"Substring conflicts removed:        {len(data.removed_conflicts):,}\n\n")

        # Skipped items
        write_subsection_header(f, "SKIPPED ITEMS", width=70)
        f.write(f"Ambiguous collisions:               {len(data.skipped_collisions):,}\n")
        f.write(f"Too-short typos:                    {len(data.skipped_short):,}\n")
        f.write(f"Excluded by rules:                  {len(data.excluded_corrections):,}\n")
        f.write(f"Rejected patterns:                  {len(data.rejected_patterns):,}\n\n")

        # Timing
        if data.stage_times:
            write_subsection_header(f, "TIMING BREAKDOWN", width=70)
            for stage, duration in data.stage_times.items():
                pct = (duration / total_time * 100) if total_time > 0 else 0
                f.write(f"{stage:<35} {format_time(duration):>12} ({pct:>5.1f}%)\n")
            f.write("-" * 70 + "\n")
            f.write(f"{'Total':<35} {format_time(total_time):>12}\n")

    write_file_safely(filepath, write_summary_content, "writing summary report")
