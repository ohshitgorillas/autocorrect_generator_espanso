"""QMK platform-specific report generation."""

from pathlib import Path
from typing import Any, TextIO

from entroppy.core import BoundaryType, Correction, format_boundary_display, format_boundary_name
from entroppy.reports import write_report_header
from entroppy.reports.helpers import write_section_header
from entroppy.utils.helpers import write_file_safely


def generate_qmk_ranking_report(
    final_corrections: list[Correction],
    ranked_corrections_before_limit: list[Correction],
    filtered_corrections: list[Correction],
    patterns: list[Correction],
    pattern_replacements: dict[Correction, list[Correction]],
    user_corrections: list[Correction],
    pattern_scores: list[tuple[float, str, str, BoundaryType]],
    direct_scores: list[tuple[float, str, str, BoundaryType]],
    filter_metadata: dict[str, Any],
    report_dir: Path,
) -> dict[str, Any]:
    """Generate comprehensive QMK ranking report."""
    report_path = report_dir / "qmk_ranking.txt"

    def write_content(f: TextIO) -> None:
        write_report_header(f, "QMK AUTOCORRECT RANKING REPORT")
        _write_overview_statistics(f, final_corrections, filtered_corrections)
        _write_summary_by_type(
            f,
            final_corrections,
            user_corrections,
            pattern_scores,
            direct_scores,
            pattern_replacements,
        )
        _write_filtering_details(f, filter_metadata)
        _write_complete_ranked_list(
            f,
            final_corrections,
            patterns,
            pattern_scores,
            direct_scores,
            user_corrections,
        )
        _write_enhanced_pattern_details(
            f,
            final_corrections,
            patterns,
            pattern_scores,
            pattern_replacements,
        )
        _write_enhanced_direct_details(
            f,
            final_corrections,
            patterns,
            direct_scores,
        )
        _write_user_words_section(f, user_corrections)
        _write_cutoff_bubble(
            f,
            final_corrections,
            ranked_corrections_before_limit,
            patterns,
            pattern_scores,
            direct_scores,
        )

    write_file_safely(report_path, write_content, "writing QMK ranking report")

    return {
        "file_path": str(report_path),
        "total_corrections": len(final_corrections),
        "user_words": len(user_corrections),
        "patterns": len(pattern_scores),
        "direct": len(direct_scores),
    }


def _write_overview_statistics(
    f: TextIO, final_corrections: list[Correction], filtered_corrections: list[Correction]
) -> None:
    """Write overview statistics section."""
    write_section_header(f, "OVERVIEW STATISTICS")
    f.write(f"Total corrections selected:        {len(final_corrections):,}\n")
    f.write(f"Available after filtering:         {len(filtered_corrections):,}\n")
    selection_rate = (
        (len(final_corrections) / len(filtered_corrections) * 100) if filtered_corrections else 0
    )
    f.write(f"Selection rate:                    {selection_rate:.1f}%\n\n")


def _write_summary_by_type(
    f: TextIO,
    final_corrections: list[Correction],
    user_corrections: list[Correction],
    pattern_scores: list[tuple[float, str, str, BoundaryType]],
    direct_scores: list[tuple[float, str, str, BoundaryType]],
    pattern_replacements: dict[Correction, list[Correction]],
) -> None:
    """Write summary statistics by correction type."""
    write_section_header(f, "SUMMARY BY TYPE")

    total = len(final_corrections)
    final_set = set(final_corrections)
    user_set = set(user_corrections)
    pattern_set = {(p_typo, p_word) for _, p_typo, p_word, _ in pattern_scores}

    # Count corrections by type in final list
    user_count = sum(1 for c in final_corrections if c in user_set)
    pattern_count = sum(
        1 for c in final_corrections if (c[0], c[1]) in pattern_set and c not in user_set
    )
    direct_count = total - user_count - pattern_count

    # Count total replacements for patterns in final list
    total_replacements = 0
    for typo, word, boundary in final_corrections:
        if (typo, word) in pattern_set and (typo, word, boundary) not in user_set:
            pattern_key = (typo, word, boundary)
            if pattern_key in pattern_replacements:
                total_replacements += len(pattern_replacements[pattern_key])

    user_pct = (user_count / total * 100) if total > 0 else 0.0
    pattern_pct = (pattern_count / total * 100) if total > 0 else 0.0
    direct_pct = (direct_count / total * 100) if total > 0 else 0.0

    f.write(f"User words:                        {user_count:,} ({user_pct:.1f}%)\n")
    f.write(f"Patterns:                         {pattern_count:,} ({pattern_pct:.1f}%)")
    if pattern_count > 0:
        f.write(f" - replaced {total_replacements:,} corrections total")
    f.write("\n")
    f.write(f"Direct corrections:                {direct_count:,} ({direct_pct:.1f}%)\n")

    # Score ranges
    if pattern_scores:
        pattern_scores_in_final = [
            s[0]
            for s in pattern_scores
            if (s[1], s[2], s[3]) in final_set and (s[1], s[2], s[3]) not in user_set
        ]
        if pattern_scores_in_final:
            min_score = min(pattern_scores_in_final)
            max_score = max(pattern_scores_in_final)
            f.write(f"Score range (patterns):             {min_score:.6f} - {max_score:.6f}\n")

    if direct_scores:
        direct_scores_in_final = [
            s[0]
            for s in direct_scores
            if (s[1], s[2], s[3]) in final_set and (s[1], s[2]) not in pattern_set
        ]
        if direct_scores_in_final:
            min_score = min(direct_scores_in_final)
            max_score = max(direct_scores_in_final)
            f.write(f"Score range (direct):                {min_score:.6f} - {max_score:.6f}\n")

    f.write("\n")


def _build_score_lookup_maps(
    pattern_scores: list[tuple[float, str, str, BoundaryType]],
    direct_scores: list[tuple[float, str, str, BoundaryType]],
) -> tuple[dict[tuple[str, str, BoundaryType], float], dict[tuple[str, str, BoundaryType], float]]:
    """Build lookup dictionaries for pattern and direct scores.

    Returns:
        Tuple of (pattern_score_map, direct_score_map)
    """
    pattern_score_map = {
        (typo, word, boundary): score for score, typo, word, boundary in pattern_scores
    }
    direct_score_map = {
        (typo, word, boundary): score for score, typo, word, boundary in direct_scores
    }
    return pattern_score_map, direct_score_map


def _write_complete_ranked_list(
    f: TextIO,
    final_corrections: list[Correction],
    patterns: list[Correction],
    pattern_scores: list[tuple[float, str, str, BoundaryType]],
    direct_scores: list[tuple[float, str, str, BoundaryType]],
    user_corrections: list[Correction],
) -> None:
    """Write complete ranked list of all corrections that made the final list."""
    write_section_header(f, "COMPLETE RANKED LIST")
    f.write(f"Total corrections in final list: {len(final_corrections):,}\n\n")

    # Create lookup dictionaries for scores
    pattern_score_map, direct_score_map = _build_score_lookup_maps(pattern_scores, direct_scores)
    user_set = {(typo, word, boundary) for typo, word, boundary in user_corrections}
    pattern_set = {(p[0], p[1], p[2]) for p in patterns}

    for rank, (typo, word, boundary) in enumerate(final_corrections, 1):
        correction_key = (typo, word, boundary)

        # Determine type and score
        if correction_key in user_set:
            correction_type = "USER"
            score_str = "(USER)"
        elif boundary != BoundaryType.BOTH and correction_key in pattern_set:
            # BOTH boundary corrections can NEVER be patterns - they can't block anything
            correction_type = "PATTERN"
            score = pattern_score_map.get(correction_key, 0.0)
            score_str = f"{score:.6f}"
        else:
            correction_type = "DIRECT"
            score = direct_score_map.get(correction_key, 0.0)
            score_str = f"{score:.6f}"

        boundary_display = format_boundary_display(boundary)
        f.write(
            f"Rank {rank:4d}  Type: {correction_type:7s}  Score: {score_str:12s}  "
            f"{typo} → {word}  {boundary_display}\n"
        )

    f.write("\n")


def _write_enhanced_pattern_details(
    f: TextIO,
    final_corrections: list[Correction],
    patterns: list[Correction],
    pattern_scores: list[tuple[float, str, str, BoundaryType]],
    pattern_replacements: dict[Correction, list[Correction]],
) -> None:
    """Write enhanced pattern details showing all patterns in final list with ALL replacements."""
    write_section_header(f, "PATTERN DETAILS")

    # Get patterns that are in the final list, ordered by their rank
    pattern_set = {(p[0], p[1]) for p in patterns}
    pattern_score_map = {
        (typo, word, boundary): score for score, typo, word, boundary in pattern_scores
    }

    # Find patterns in final list and their ranks
    patterns_in_final = []
    for rank, (typo, word, boundary) in enumerate(final_corrections, 1):
        if (typo, word) in pattern_set:
            pattern_key = (typo, word, boundary)
            score = pattern_score_map.get(pattern_key, 0.0)
            patterns_in_final.append((rank, typo, word, boundary, score))

    if not patterns_in_final:
        f.write("No patterns in final list.\n\n")
        return

    pattern_total = len(patterns_in_final)
    f.write(f"All patterns that made the final list ({pattern_total:,} total):\n\n")

    for pattern_num, (rank, typo, word, boundary, score) in enumerate(patterns_in_final, 1):
        pattern_key = (typo, word, boundary)
        replacements = pattern_replacements.get(pattern_key, [])

        boundary_display = format_boundary_display(boundary)
        replacement_count = len(replacements)
        f.write(f"Pattern #{pattern_num}: {typo} → {word} {boundary_display}\n")
        f.write(f"  Rank: {rank}\n")
        f.write(f"  Score: {score:.6f} (sum of replaced word frequencies)\n")
        f.write(f"  Replaces {replacement_count:,} corrections:\n")

        for i, (repl_typo, repl_word, repl_boundary) in enumerate(replacements, 1):
            repl_boundary_display = format_boundary_display(repl_boundary)
            f.write(f"    {i:4d}. {repl_typo} → {repl_word} {repl_boundary_display}\n")

        f.write("\n")


def _write_enhanced_direct_details(
    f: TextIO,
    final_corrections: list[Correction],
    patterns: list[Correction],
    direct_scores: list[tuple[float, str, str, BoundaryType]],
) -> None:
    """Write enhanced direct corrections details showing ALL direct corrections."""
    write_section_header(f, "DIRECT CORRECTIONS DETAILS")

    # Get direct corrections that are in the final list
    pattern_set = {(p[0], p[1]) for p in patterns}
    direct_score_map = {
        (typo, word, boundary): score for score, typo, word, boundary in direct_scores
    }

    # Find direct corrections in final list and their ranks
    # Direct corrections are those that are not patterns and have scores in direct_scores
    direct_in_final = []
    for rank, (typo, word, boundary) in enumerate(final_corrections, 1):
        if (typo, word) not in pattern_set and (typo, word, boundary) in direct_score_map:
            score = direct_score_map[(typo, word, boundary)]
            direct_in_final.append((rank, typo, word, boundary, score))

    if not direct_in_final:
        f.write("No direct corrections in final list.\n\n")
        return

    direct_total = len(direct_in_final)
    f.write(
        f"All direct corrections that made the final list "
        f"({direct_total:,} total, ranked by score):\n\n"
    )

    # Sort by score descending for display
    direct_in_final_sorted = sorted(direct_in_final, key=lambda x: x[4], reverse=True)

    for rank, typo, word, boundary, score in direct_in_final_sorted:
        boundary_display = format_boundary_display(boundary)
        f.write(f"Rank {rank:4d}  Score: {score:.6f}  {typo} → {word}  {boundary_display}\n")

    f.write("\n")


def _write_filtering_details(f: TextIO, filter_metadata: dict[str, Any]) -> None:
    """Write filtering details section."""
    write_section_header(f, "FILTERING DETAILS")
    filter_reasons = filter_metadata.get("filter_reasons", {})
    f.write(f"Character set violations:          {filter_reasons.get('char_set', 0):,}\n")
    f.write(
        f"Same-typo conflicts resolved:      {filter_reasons.get('same_typo_conflicts', 0):,}\n"
    )
    f.write(f"RTL suffix conflicts removed:      {filter_reasons.get('suffix_conflicts', 0):,}\n\n")

    _write_char_violations(f, filter_metadata)
    _write_same_typo_conflicts(f, filter_metadata)
    _write_suffix_conflicts(f, filter_metadata)


def _write_char_violations(f: TextIO, filter_metadata: dict[str, Any]) -> None:
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


def _write_same_typo_conflicts(f: TextIO, filter_metadata: dict[str, Any]) -> None:
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
        boundary_name = format_boundary_name(boundary)
        f.write(f"    REMOVED: {removed_typo} → {removed_word} ({boundary_name})\n")
        f.write(f"    KEPT:    {kept_typo} → {kept_word} (less restrictive)\n")
        f.write("\n")
    remaining = len(same_typo_conflicts) - 10
    if remaining > 0:
        f.write(f"    ... and {remaining} more\n")
    f.write("\n")


def _write_suffix_conflicts(f: TextIO, filter_metadata: dict[str, Any]) -> None:
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


def _write_user_words_section(f: TextIO, user_corrections: list[Correction]) -> None:
    """Write user words section."""
    write_section_header(f, "USER WORDS")
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


def _write_cutoff_bubble(
    f: TextIO,
    final_corrections: list[Correction],
    ranked_corrections_before_limit: list[Correction],
    patterns: list[Correction],
    pattern_scores: list[tuple[float, str, str, BoundaryType]],
    direct_scores: list[tuple[float, str, str, BoundaryType]],
) -> None:
    """Write the cutoff bubble section showing what made/missed the cut."""
    f.write("THE CUTOFF BUBBLE\n")
    f.write("=" * 80 + "\n")
    f.write("This shows what made the cut and what didn't - the most critical\n")
    f.write("decisions in the ranking process.\n\n")

    # Build score lookup maps once
    pattern_score_map, direct_score_map = _build_score_lookup_maps(pattern_scores, direct_scores)

    cutoff_index = len(final_corrections)

    # Last 10 that made the cut
    write_section_header(f, "LAST 10 CORRECTIONS THAT MADE THE CUT:")
    start_idx = max(0, cutoff_index - 10)
    for i in range(start_idx, cutoff_index):
        typo, word, boundary = final_corrections[i]
        score = _get_score_for_correction(typo, word, boundary, pattern_score_map, direct_score_map)
        correction_type = _get_correction_type(typo, word, patterns)
        f.write(f"{i + 1}. {typo} → {word} {format_boundary_display(boundary)}\n")
        f.write(f"   Type: {correction_type}, Score: {score:.6f}\n\n")

    # First 10 that got cut
    f.write("\n")
    write_section_header(f, "FIRST 10 CORRECTIONS THAT GOT CUT:")
    if len(ranked_corrections_before_limit) > cutoff_index:
        end_idx = min(cutoff_index + 10, len(ranked_corrections_before_limit))
        for i in range(cutoff_index, end_idx):
            typo, word, boundary = ranked_corrections_before_limit[i]
            score = _get_score_for_correction(
                typo, word, boundary, pattern_score_map, direct_score_map
            )
            correction_type = _get_correction_type(typo, word, patterns)
            f.write(f"{i + 1}. {typo} → {word} {format_boundary_display(boundary)}\n")
            f.write(f"   Type: {correction_type}, Score: {score:.6f}\n\n")
    else:
        f.write("(No corrections were cut - all made the final selection)\n")


def _get_score_for_correction(
    typo: str,
    word: str,
    boundary: BoundaryType,
    pattern_score_map: dict[tuple[str, str, BoundaryType], float],
    direct_score_map: dict[tuple[str, str, BoundaryType], float],
) -> float:
    """Get the score for a specific correction using lookup maps.

    Args:
        typo: Typo string
        word: Correction word
        boundary: Boundary type
        pattern_score_map: Pre-built lookup map for pattern scores
        direct_score_map: Pre-built lookup map for direct scores

    Returns:
        Score value, or float('inf') for user corrections
    """
    correction_key = (typo, word, boundary)

    # Check pattern scores first
    if correction_key in pattern_score_map:
        return pattern_score_map[correction_key]

    # Check direct scores
    if correction_key in direct_score_map:
        return direct_score_map[correction_key]

    # User corrections have infinite priority (use a large number for display)
    return float("inf")


def _get_correction_type(typo: str, word: str, patterns: list[Correction]) -> str:
    """Determine if a correction is a PATTERN or DIRECT correction."""
    pattern_set = {(p[0], p[1]) for p in patterns}
    if (typo, word) in pattern_set:
        return "PATTERN"
    return "DIRECT"
