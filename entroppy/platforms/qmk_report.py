"""QMK platform-specific report generation."""

from pathlib import Path

from ..config import BoundaryType, Correction
from ..reports import write_report_header


def generate_qmk_ranking_report(
    final_corrections: list[Correction],
    ranked_corrections_before_limit: list[Correction],
    filtered_corrections: list[Correction],
    patterns: list[Correction],
    pattern_replacements: dict,
    user_corrections: list[Correction],
    pattern_scores: list[tuple[float, str, str, BoundaryType]],
    direct_scores: list[tuple[float, str, str, BoundaryType]],
    filter_metadata: dict,
    report_dir: Path,
) -> dict:
    """Generate comprehensive QMK ranking report."""
    report_path = report_dir / "qmk_ranking.txt"

    with open(report_path, "w", encoding="utf-8") as f:
        _write_header(f)
        _write_overview_statistics(f, final_corrections, filtered_corrections)
        _write_filtering_details(f, filter_metadata)
        _write_user_words_section(f, user_corrections)
        _write_patterns_section(f, pattern_scores, pattern_replacements)
        _write_direct_corrections_section(f, direct_scores)
        _write_cutoff_bubble(
            f,
            final_corrections,
            ranked_corrections_before_limit,
            patterns,
            pattern_scores,
            direct_scores,
        )

    return {
        "file_path": str(report_path),
        "total_corrections": len(final_corrections),
        "user_words": len(user_corrections),
        "patterns": len(pattern_scores),
        "direct": len(direct_scores),
    }


def _write_header(f):
    """Write report header."""
    write_report_header(f, "QMK AUTOCORRECT RANKING REPORT")


def _write_overview_statistics(
    f, final_corrections: list[Correction], filtered_corrections: list[Correction]
):
    """Write overview statistics section."""
    f.write("OVERVIEW STATISTICS\n")
    f.write("-" * 80 + "\n")
    f.write(f"Total corrections selected:        {len(final_corrections):,}\n")
    f.write(f"Available after filtering:         {len(filtered_corrections):,}\n")
    selection_rate = (
        (len(final_corrections) / len(filtered_corrections) * 100)
        if filtered_corrections
        else 0
    )
    f.write(f"Selection rate:                    {selection_rate:.1f}%\n\n")


def _write_filtering_details(f, filter_metadata: dict):
    """Write filtering details section."""
    f.write("FILTERING DETAILS\n")
    f.write("-" * 80 + "\n")
    filter_reasons = filter_metadata.get("filter_reasons", {})
    f.write(
        f"Character set violations:          {filter_reasons.get('char_set', 0):,}\n"
    )
    f.write(
        f"Same-typo conflicts resolved:      {filter_reasons.get('same_typo_conflicts', 0):,}\n"
    )
    f.write(
        f"RTL suffix conflicts removed:      {filter_reasons.get('suffix_conflicts', 0):,}\n\n"
    )

    _write_char_violations(f, filter_metadata)
    _write_same_typo_conflicts(f, filter_metadata)
    _write_suffix_conflicts(f, filter_metadata)


def _write_char_violations(f, filter_metadata: dict):
    """Write character set violations examples."""
    char_filtered = filter_metadata.get("char_filtered", [])
    if not char_filtered:
        return

    f.write("  Character Set Violations (first 10 examples):\n")
    for typo, word, reason in char_filtered[:10]:
        f.write(f"    {typo} → {word} ({reason})\n")
    remaining = len(char_filtered) - 10
    if remaining > 0:
        f.write(f"    ... and {remaining} more\n")
    f.write("\n")


def _write_same_typo_conflicts(f, filter_metadata: dict):
    """Write same-typo conflicts examples."""
    same_typo_conflicts = filter_metadata.get("same_typo_conflicts", [])
    if not same_typo_conflicts:
        return

    f.write("  Same-Typo Conflicts (first 10 examples):\n")
    for (
        removed_typo,
        removed_word,
        kept_typo,
        kept_word,
        boundary,
    ) in same_typo_conflicts[:10]:
        f.write(
            f"    REMOVED: {removed_typo} → {removed_word} ({_format_boundary_name(boundary)})\n"
        )
        f.write(f"    KEPT:    {kept_typo} → {kept_word} (less restrictive)\n")
        f.write("\n")
    remaining = len(same_typo_conflicts) - 10
    if remaining > 0:
        f.write(f"    ... and {remaining} more\n")
    f.write("\n")


def _write_suffix_conflicts(f, filter_metadata: dict):
    """Write RTL suffix conflicts examples."""
    suffix_conflicts = filter_metadata.get("suffix_conflicts", [])
    if not suffix_conflicts:
        return

    f.write("  RTL Suffix Conflicts (first 10 examples):\n")
    for long_typo, long_word, short_typo, short_word, _ in suffix_conflicts[:10]:
        f.write(f"    {long_typo} → {long_word}\n")
        f.write(f"      blocked by: {short_typo} → {short_word}\n")
        f.write("\n")
    remaining = len(suffix_conflicts) - 10
    if remaining > 0:
        f.write(f"    ... and {remaining} more\n")
    f.write("\n")


def _write_user_words_section(f, user_corrections: list[Correction]):
    """Write user words section."""
    f.write("USER WORDS\n")
    f.write("-" * 80 + "\n")
    user_count = len(user_corrections)
    f.write(f"User-specified words (always included): {user_count:,}\n")
    if user_count > 0:
        f.write("First 20:\n")
        for typo, word, _ in user_corrections[:20]:
            f.write(f"  {typo} → {word}\n")
        remaining = user_count - 20
        if remaining > 0:
            f.write(f"  ... and {remaining} more\n")
    f.write("\n")


def _write_patterns_section(
    f,
    pattern_scores: list[tuple[float, str, str, BoundaryType]],
    pattern_replacements: dict,
):
    """Write patterns section."""
    f.write("PATTERNS\n")
    f.write("-" * 80 + "\n")
    pattern_count = len(pattern_scores)
    f.write(f"Pattern corrections: {pattern_count:,}\n\n")

    if pattern_count == 0:
        return

    f.write("Top 20 patterns by score:\n\n")
    sorted_patterns = sorted(pattern_scores, key=lambda x: x[0], reverse=True)
    for i, (score, typo, word, boundary) in enumerate(sorted_patterns[:20], 1):
        f.write(f"{i}. {typo} → {word} {_format_boundary_display(boundary)}\n")
        f.write(f"   Score: {score:.6f} (sum of replaced word frequencies)\n")

        pattern_key = (typo, word, boundary)
        if pattern_key in pattern_replacements:
            replacements = pattern_replacements[pattern_key][:15]
            f.write(
                f"   Replaces {len(pattern_replacements[pattern_key])} corrections, examples:\n"
            )
            for repl_typo, repl_word, _ in replacements:
                f.write(f"     {repl_typo} → {repl_word}\n")
        f.write("\n")

    remaining = pattern_count - 20
    if remaining > 0:
        f.write(f"... and {remaining} more patterns\n\n")


def _write_direct_corrections_section(
    f, direct_scores: list[tuple[float, str, str, BoundaryType]]
):
    """Write direct corrections section."""
    f.write("DIRECT CORRECTIONS\n")
    f.write("-" * 80 + "\n")
    direct_count = len(direct_scores)
    f.write(f"Direct corrections: {direct_count:,}\n\n")

    if direct_count == 0:
        return

    f.write("Top 20 by word frequency:\n\n")
    sorted_direct = sorted(direct_scores, key=lambda x: x[0], reverse=True)
    for i, (score, typo, word, boundary) in enumerate(sorted_direct[:20], 1):
        f.write(f"{i}. {typo} → {word} {_format_boundary_display(boundary)}\n")
        f.write(f"   Frequency: {score:.6f}\n\n")

    remaining = direct_count - 20
    if remaining > 0:
        f.write(f"... and {remaining} more direct corrections\n\n")


def _write_cutoff_bubble(
    f,
    final_corrections: list[Correction],
    ranked_corrections_before_limit: list[Correction],
    patterns: list[Correction],
    pattern_scores: list[tuple[float, str, str, BoundaryType]],
    direct_scores: list[tuple[float, str, str, BoundaryType]],
):
    """Write the cutoff bubble section showing what made/missed the cut."""
    f.write("THE CUTOFF BUBBLE\n")
    f.write("=" * 80 + "\n")
    f.write("This shows what made the cut and what didn't - the most critical\n")
    f.write("decisions in the ranking process.\n\n")

    cutoff_index = len(final_corrections)

    # Last 10 that made the cut
    f.write("LAST 10 CORRECTIONS THAT MADE THE CUT:\n")
    f.write("-" * 80 + "\n")
    start_idx = max(0, cutoff_index - 10)
    for i in range(start_idx, cutoff_index):
        typo, word, boundary = final_corrections[i]
        score = _get_score_for_correction(
            typo, word, boundary, pattern_scores, direct_scores
        )
        correction_type = _get_correction_type(typo, word, patterns)
        f.write(f"{i + 1}. {typo} → {word} {_format_boundary_display(boundary)}\n")
        f.write(f"   Type: {correction_type}, Score: {score:.6f}\n\n")

    # First 10 that got cut
    f.write("\nFIRST 10 CORRECTIONS THAT GOT CUT:\n")
    f.write("-" * 80 + "\n")
    if len(ranked_corrections_before_limit) > cutoff_index:
        for i in range(
            cutoff_index, min(cutoff_index + 10, len(ranked_corrections_before_limit))
        ):
            typo, word, boundary = ranked_corrections_before_limit[i]
            score = _get_score_for_correction(
                typo, word, boundary, pattern_scores, direct_scores
            )
            correction_type = _get_correction_type(typo, word, patterns)
            f.write(f"{i + 1}. {typo} → {word} {_format_boundary_display(boundary)}\n")
            f.write(f"   Type: {correction_type}, Score: {score:.6f}\n\n")
    else:
        f.write("(No corrections were cut - all made the final selection)\n")


def _format_boundary_name(boundary: BoundaryType) -> str:
    """Format boundary type as a name."""
    if boundary == BoundaryType.NONE:
        return "NONE"
    if boundary == BoundaryType.LEFT:
        return "LEFT"
    if boundary == BoundaryType.RIGHT:
        return "RIGHT"
    if boundary == BoundaryType.BOTH:
        return "BOTH"
    raise ValueError(f"Invalid boundary type: {boundary}")

def _format_boundary_display(boundary: BoundaryType) -> str:
    """Format boundary type for display in report."""
    if boundary == BoundaryType.NONE:
        return ""
    if boundary == BoundaryType.LEFT:
        return "(LEFT boundary)"
    if boundary == BoundaryType.RIGHT:
        return "(RIGHT boundary)"
    if boundary == BoundaryType.BOTH:
        return "(BOTH boundaries)"
    raise ValueError(f"Invalid boundary type: {boundary}")


def _get_score_for_correction(
    typo: str,
    word: str,
    boundary: BoundaryType,
    pattern_scores: list[tuple[float, str, str, BoundaryType]],
    direct_scores: list[tuple[float, str, str, BoundaryType]],
) -> float:
    """Get the score for a specific correction."""
    # Check pattern scores
    for score, p_typo, p_word, p_boundary in pattern_scores:
        if p_typo == typo and p_word == word and p_boundary == boundary:
            return score

    # Check direct scores
    for score, d_typo, d_word, d_boundary in direct_scores:
        if d_typo == typo and d_word == word and d_boundary == boundary:
            return score

    # User corrections have infinite priority (use a large number for display)
    return float("inf")


def _get_correction_type(typo: str, word: str, patterns: list[Correction]) -> str:
    """Determine if a correction is a PATTERN or DIRECT correction."""
    pattern_set = {(p[0], p[1]) for p in patterns}
    if (typo, word) in pattern_set:
        return "PATTERN"
    return "DIRECT"
