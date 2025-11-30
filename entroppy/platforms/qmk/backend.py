"""QMK platform backend implementation."""

import os
import sys
from collections import defaultdict

from loguru import logger
from wordfreq import word_frequency

from entroppy.core import BoundaryType, Config, Correction
from entroppy.platforms.base import MatchDirection, PlatformBackend, PlatformConstraints
from entroppy.platforms.qmk.reports import generate_qmk_ranking_report


class QMKBackend(PlatformBackend):
    """
    Backend for QMK firmware autocorrect.

    Characteristics:
    - Matches right-to-left
    - Limited corrections
        (6000 theoretical max, effective max depends on flash size)
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
        self._all_scored = []

    def get_constraints(self) -> PlatformConstraints:
        """Return QMK constraints."""
        return PlatformConstraints(
            max_corrections=6000,  # Theoretical max, user-configurable
            max_typo_length=62,  # QMK string length limit
            max_word_length=62,
            allowed_chars=self.ALLOWED_CHARS,
            supports_boundaries=True,  # Via ':' notation
            supports_case_propagation=True,
            supports_regex=False,
            match_direction=MatchDirection.RIGHT_TO_LEFT,
            output_format="text",
        )

    def _filter_character_set(self, corrections: list[Correction]) -> tuple[list[Correction], list]:
        """Filter out corrections with invalid characters and convert to lowercase."""
        filtered = []
        char_filtered = []

        for typo, word, boundary in corrections:
            if not all(c.isalpha() or c == "'" for c in typo.lower()):
                char_filtered.append((typo, word, "typo contains invalid chars"))
                continue
            if not all(c.isalpha() or c == "'" for c in word.lower()):
                char_filtered.append((typo, word, "word contains invalid chars"))
                continue

            filtered.append((typo.lower(), word.lower(), boundary))

        return filtered, char_filtered

    def _resolve_same_typo_conflicts(
        self, corrections: list[Correction]
    ) -> tuple[list[Correction], list]:
        """
        When multiple boundaries exist for same typo text, keep least restrictive.

        Example: `riet` (NONE) and `:riet` (LEFT) both present
        → Keep `riet` (NONE) since it's less restrictive
        """
        typo_groups = defaultdict(list)
        for typo, word, boundary in corrections:
            typo_groups[typo].append((typo, word, boundary))

        boundary_priority = {
            BoundaryType.NONE: 0,
            BoundaryType.LEFT: 1,
            BoundaryType.RIGHT: 1,
            BoundaryType.BOTH: 2,
        }

        deduped = []
        conflicts = []

        for _, corrections_list in typo_groups.items():
            if len(corrections_list) == 1:
                deduped.append(corrections_list[0])
            else:
                sorted_by_restriction = sorted(
                    corrections_list, key=lambda c: boundary_priority[c[2]]
                )
                kept = sorted_by_restriction[0]
                deduped.append(kept)

                for removed in sorted_by_restriction[1:]:
                    conflicts.append((removed[0], removed[1], kept[0], kept[1], removed[2]))

        return deduped, conflicts

    def _detect_conflicts_generic(
        self, corrections: list[Correction], conflict_check_fn
    ) -> tuple[list[Correction], list]:
        """
        Generic conflict detection for QMK constraints.

        Args:
            corrections: List of corrections to analyze
            conflict_check_fn: Function that takes (typo1, word1, typo2, word2)
                             and returns True if there's a conflict

        Returns:
            Tuple of (kept_corrections, conflicts)
        """
        # Sort all corrections by typo length (shortest first)
        sorted_corrections = sorted(corrections, key=lambda c: len(c[0]))

        kept = []
        conflicts = []
        removed_typos = set()

        for i, (typo1, word1, bound1) in enumerate(sorted_corrections):
            if typo1 in removed_typos:
                continue

            is_blocked = False
            # Check against all shorter typos (processed earlier)
            for typo2, word2, _ in sorted_corrections[:i]:
                if typo2 in removed_typos:
                    continue

                if conflict_check_fn(typo1, word1, typo2, word2):
                    is_blocked = True
                    conflicts.append((typo1, word1, typo2, word2, bound1))
                    removed_typos.add(typo1)
                    break

            if not is_blocked:
                kept.append((typo1, word1, bound1))

        return kept, conflicts

    def _detect_suffix_conflicts(
        self, corrections: list[Correction]
    ) -> tuple[list[Correction], list]:
        """
        Detect RTL suffix conflicts across ALL typos.

        QMK scans right-to-left. If typing "wriet":
        - Finds suffix "riet" first
        - Produces "w" + "rite" = "write"
        - So `riet -> rite` makes `wriet -> write` redundant

        This checks across all boundary types since QMK's RTL matching
        doesn't respect boundaries during the matching phase.
        """

        def check_suffix_conflict(typo1, word1, typo2, word2):
            # Check if typo1 ends with typo2 AND produces same correction
            if typo1.endswith(typo2) and typo1 != typo2:
                remaining = typo1[: -len(typo2)]
                expected = remaining + word2
                return expected == word1
            return False

        return self._detect_conflicts_generic(corrections, check_suffix_conflict)

    def _detect_substring_conflicts(
        self, corrections: list[Correction]
    ) -> tuple[list[Correction], list]:
        """
        Detect general substring conflicts required by QMK.

        QMK's compiler rejects any case where one typo is a substring
        of another typo, regardless of position (prefix, suffix, or middle)
        or boundary type. This is a hard constraint in QMK's trie structure.

        Examples that QMK rejects:
        - "asbout" contains "sbout" as suffix
        - "beejn" contains "beej" as prefix
        - "xbeejy" contains "beej" in middle

        We keep the shorter typo and remove the longer one.
        """

        def check_substring_conflict(typo1, word1, typo2, word2):
            # If typo2 is anywhere in typo1, QMK rejects it
            return typo2 in typo1 and typo1 != typo2

        return self._detect_conflicts_generic(corrections, check_substring_conflict)

    def filter_corrections(
        self, corrections: list[Correction], config: Config
    ) -> tuple[list[Correction], dict]:
        """
        Apply QMK-specific filtering.

        - Character set validation (only a-z and ')
        - Same-typo-text conflict detection (different boundaries)
        - Suffix conflict detection (RTL matching optimization)
        - Substring conflict detection (QMK's hard constraint)
        """
        filtered, char_filtered = self._filter_character_set(corrections)
        deduped, same_typo_conflicts = self._resolve_same_typo_conflicts(filtered)
        after_suffix, suffix_conflicts = self._detect_suffix_conflicts(deduped)
        final, substring_conflicts = self._detect_substring_conflicts(after_suffix)

        metadata = {
            "total_input": len(corrections),
            "total_output": len(final),
            "filtered_count": len(corrections) - len(final),
            "filter_reasons": {
                "char_set": len(char_filtered),
                "same_typo_conflicts": len(same_typo_conflicts),
                "suffix_conflicts": len(suffix_conflicts),
                "substring_conflicts": len(substring_conflicts),
            },
            "char_filtered": char_filtered,
            "same_typo_conflicts": same_typo_conflicts,
            "suffix_conflicts": suffix_conflicts,
            "substring_conflicts": substring_conflicts,
        }

        return final, metadata

    def _separate_by_type(
        self,
        corrections: list[Correction],
        patterns: list[Correction],
        pattern_replacements: dict,
        user_words: set[str],
    ) -> tuple[list[Correction], list[Correction], list[Correction]]:
        """Separate corrections into user words, patterns, and direct corrections."""
        user_corrections = []
        pattern_corrections = []
        direct_corrections = []

        pattern_typos = {(p[0], p[1]) for p in patterns}

        replaced_by_patterns = set()
        for pattern in patterns:
            pattern_key = (pattern[0], pattern[1], pattern[2])
            if pattern_key in pattern_replacements:
                for replaced in pattern_replacements[pattern_key]:
                    replaced_by_patterns.add((replaced[0], replaced[1]))

        for typo, word, boundary in corrections:
            if word in user_words:
                user_corrections.append((typo, word, boundary))
            elif (typo, word) in pattern_typos:
                pattern_corrections.append((typo, word, boundary))
            elif (typo, word) not in replaced_by_patterns:
                direct_corrections.append((typo, word, boundary))

        return user_corrections, pattern_corrections, direct_corrections

    def _score_patterns(
        self, pattern_corrections: list[Correction], pattern_replacements: dict
    ) -> list[tuple[float, str, str, BoundaryType]]:
        """Score patterns by sum of replaced word frequencies."""
        scores = []
        for typo, word, boundary in pattern_corrections:
            pattern_key = (typo, word, boundary)
            if pattern_key in pattern_replacements:
                total_freq = sum(
                    word_frequency(replaced_word, "en")
                    for _, replaced_word, _ in pattern_replacements[pattern_key]
                )
                scores.append((total_freq, typo, word, boundary))
        return scores

    def _score_direct_corrections(
        self, direct_corrections: list[Correction]
    ) -> list[tuple[float, str, str, BoundaryType]]:
        """Score direct corrections by word frequency."""
        scores = []
        for typo, word, boundary in direct_corrections:
            freq = word_frequency(word, "en")
            scores.append((freq, typo, word, boundary))
        return scores

    def rank_corrections(
        self,
        corrections: list[Correction],
        patterns: list[Correction],
        pattern_replacements: dict,
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
        """
        user_corrections, pattern_corrections, direct_corrections = self._separate_by_type(
            corrections, patterns, pattern_replacements, user_words
        )

        pattern_scores = self._score_patterns(pattern_corrections, pattern_replacements)
        direct_scores = self._score_direct_corrections(direct_corrections)

        all_scored = pattern_scores + direct_scores
        all_scored.sort(key=lambda x: x[0], reverse=True)

        ranked = user_corrections + [(t, w, b) for _, t, w, b in all_scored]

        # Store scoring information for report generation
        self._user_corrections = user_corrections
        self._pattern_scores = pattern_scores
        self._direct_scores = direct_scores
        self._all_scored = all_scored

        # Apply max_corrections limit if specified
        if config and config.max_corrections:
            ranked = ranked[: config.max_corrections]

        return ranked

    def _format_correction_line(self, typo: str, word: str, boundary: BoundaryType) -> str:
        """Format a single correction line with boundary markers."""
        if boundary == BoundaryType.BOTH:
            formatted_typo = f":{typo}:"
        elif boundary == BoundaryType.LEFT:
            formatted_typo = f":{typo}"
        elif boundary == BoundaryType.RIGHT:
            formatted_typo = f"{typo}:"
        else:  # NONE
            formatted_typo = typo

        return f"{formatted_typo} -> {word}"

    def _sort_corrections(self, lines: list[str]) -> list[str]:
        """Sort correction lines alphabetically by correction word."""
        return sorted(lines, key=lambda line: line.split(" -> ")[1])

    def _determine_output_path(self, output_path: str | None) -> str | None:
        """Determine final output file path."""
        if not output_path:
            return None

        if os.path.isdir(output_path) or not output_path.endswith(".txt"):
            return os.path.join(output_path, "autocorrect.txt")
        return output_path

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
        lines = [
            self._format_correction_line(typo, word, boundary)
            for typo, word, boundary in corrections
        ]

        lines = self._sort_corrections(lines)

        output_file = self._determine_output_path(output_path)

        if output_file:

            os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)

            with open(output_file, "w", encoding="utf-8") as f:
                for line in lines:
                    f.write(line + "\n")

            if config.verbose:
                logger.info(f"\nWrote {len(lines)} corrections to {output_file}")
        else:
            for line in lines:
                print(line, file=sys.stdout)

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
