"""Statistics CSV report generation."""

from pathlib import Path

from entroppy.reports.data import ReportData


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
