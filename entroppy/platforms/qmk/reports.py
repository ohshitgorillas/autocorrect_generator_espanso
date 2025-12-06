"""QMK platform-specific report generation."""

from pathlib import Path
from typing import Any, TextIO

from entroppy.core import BoundaryType, Correction, format_boundary_display
from entroppy.reports import write_report_header
from entroppy.reports.helpers import write_section_header
from entroppy.utils.helpers import write_file_safely


def generate_qmk_ranking_report(
    final_corrections: list[Correction],
    all_corrections: list[Correction],
    patterns: list[Correction],
    pattern_replacements: dict[Correction, list[Correction]],
    user_corrections: list[Correction],
    pattern_scores: list[tuple[float, str, str, BoundaryType]],
    direct_scores: list[tuple[float, str, str, BoundaryType]],
    report_dir: Path,
) -> dict[str, Any]:
    """Generate comprehensive QMK ranking report."""
    report_path = report_dir / "qmk_ranking.txt"

    def write_content(f: TextIO) -> None:
        write_report_header(f, "QMK AUTOCORRECT RANKING REPORT")
        _write_overview_statistics(f, final_corrections, all_corrections)
        _write_summary_by_type(
            f,
            final_corrections,
            user_corrections,
            pattern_scores,
            direct_scores,
            pattern_replacements,
        )
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

    write_file_safely(report_path, write_content, "writing QMK ranking report")

    return {
        "file_path": str(report_path),
        "total_corrections": len(final_corrections),
        "user_words": len(user_corrections),
        "patterns": len(pattern_scores),
        "direct": len(direct_scores),
    }


def _write_overview_statistics(
    f: TextIO, final_corrections: list[Correction], all_corrections: list[Correction]
) -> None:
    """Write overview statistics section."""
    write_section_header(f, "OVERVIEW STATISTICS")
    f.write(f"Total corrections selected:        {len(final_corrections):,}\n")
    f.write(f"Available corrections:              {len(all_corrections):,}\n")
    selection_rate = (len(final_corrections) / len(all_corrections) * 100) if all_corrections else 0
    f.write(f"Selection rate:                    {selection_rate:.1f}%\n\n")


def _count_corrections_by_type(
    final_corrections: list[Correction],
    user_set: set[Correction],
    pattern_set: set[tuple[str, str]],
) -> tuple[int, int, int]:
    """Count corrections by type in final list.

    Args:
        final_corrections: Final list of corrections
        user_set: Set of user corrections
        pattern_set: Set of (typo, word) tuples for patterns

    Returns:
        Tuple of (user_count, pattern_count, direct_count)
    """
    user_count = sum(1 for c in final_corrections if c in user_set)
    pattern_count = sum(
        1 for c in final_corrections if (c[0], c[1]) in pattern_set and c not in user_set
    )
    direct_count = len(final_corrections) - user_count - pattern_count
    return user_count, pattern_count, direct_count


def _count_pattern_replacements(
    final_corrections: list[Correction],
    pattern_set: set[tuple[str, str]],
    user_set: set[Correction],
    pattern_replacements: dict[Correction, list[Correction]],
) -> int:
    """Count total replacements for patterns in final list.

    Args:
        final_corrections: Final list of corrections
        pattern_set: Set of (typo, word) tuples for patterns
        user_set: Set of user corrections
        pattern_replacements: Dictionary mapping patterns to replacements

    Returns:
        Total number of replacements
    """
    total_replacements = 0
    for typo, word, boundary in final_corrections:
        if (typo, word) in pattern_set and (typo, word, boundary) not in user_set:
            pattern_key = (typo, word, boundary)
            if pattern_key in pattern_replacements:
                total_replacements += len(pattern_replacements[pattern_key])
    return total_replacements


def _write_pattern_score_range(
    f: TextIO,
    final_set: set[Correction],
    user_set: set[Correction],
    pattern_scores: list[tuple[float, str, str, BoundaryType]],
) -> None:
    """Write score range for patterns."""
    pattern_scores_in_final = [
        s[0]
        for s in pattern_scores
        if (s[1], s[2], s[3]) in final_set and (s[1], s[2], s[3]) not in user_set
    ]
    if pattern_scores_in_final:
        min_score = min(pattern_scores_in_final)
        max_score = max(pattern_scores_in_final)
        f.write(f"Score range (patterns):             {min_score:.6f} - {max_score:.6f}\n")


def _write_direct_score_range(
    f: TextIO,
    final_set: set[Correction],
    pattern_set: set[tuple[str, str]],
    direct_scores: list[tuple[float, str, str, BoundaryType]],
) -> None:
    """Write score range for direct corrections."""
    direct_scores_in_final = [
        s[0]
        for s in direct_scores
        if (s[1], s[2], s[3]) in final_set and (s[1], s[2]) not in pattern_set
    ]
    if direct_scores_in_final:
        min_score = min(direct_scores_in_final)
        max_score = max(direct_scores_in_final)
        f.write(f"Score range (direct):                {min_score:.6f} - {max_score:.6f}\n")


def _write_score_ranges(
    f: TextIO,
    final_set: set[Correction],
    user_set: set[Correction],
    pattern_set: set[tuple[str, str]],
    pattern_scores: list[tuple[float, str, str, BoundaryType]],
    direct_scores: list[tuple[float, str, str, BoundaryType]],
) -> None:
    """Write score ranges for patterns and direct corrections.

    Args:
        f: File to write to
        final_set: Set of final corrections
        user_set: Set of user corrections
        pattern_set: Set of (typo, word) tuples for patterns
        pattern_scores: Pattern scores list
        direct_scores: Direct correction scores list
    """
    if pattern_scores:
        _write_pattern_score_range(f, final_set, user_set, pattern_scores)

    if direct_scores:
        _write_direct_score_range(f, final_set, pattern_set, direct_scores)


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
    user_count, pattern_count, direct_count = _count_corrections_by_type(
        final_corrections, user_set, pattern_set
    )

    # Count total replacements for patterns in final list
    total_replacements = _count_pattern_replacements(
        final_corrections, pattern_set, user_set, pattern_replacements
    )

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
    _write_score_ranges(f, final_set, user_set, pattern_set, pattern_scores, direct_scores)

    f.write("\n")


def _build_score_lookup_maps(
    pattern_scores: list[tuple[float, str, str, BoundaryType]],
    direct_scores: list[tuple[float, str, str, BoundaryType]],
) -> tuple[
    dict[tuple[str, str, BoundaryType], float],
    dict[tuple[str, str, BoundaryType], float],
]:
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
    user_set = set(user_corrections)
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
        if (typo, word) not in pattern_set and (
            typo,
            word,
            boundary,
        ) in direct_score_map:
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
