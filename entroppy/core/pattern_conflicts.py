"""Pattern conflict checking functions."""

from typing import TYPE_CHECKING

from entroppy.core.boundaries import BoundaryType
from entroppy.core.types import Correction

if TYPE_CHECKING:
    from entroppy.core.pattern_indexes import CorrectionIndex


def check_pattern_would_incorrectly_match_other_corrections(
    typo_pattern: str,
    word_pattern: str,
    all_corrections: list[Correction],
    pattern_occurrences: list[Correction],
    correction_index: "CorrectionIndex | None" = None,  # type: ignore[name-defined]
) -> tuple[bool, str | None]:
    """Check if a pattern would incorrectly match other corrections.

    Checks for substring conflicts in BOTH directions regardless of platform or matching direction:
    - SUFFIX conflicts: If pattern appears as suffix of another correction's typo
      (relevant for QMK RTL matching where patterns match at end)
    - PREFIX conflicts: If pattern appears as prefix of another correction's typo
      (relevant for Espanso LTR matching where patterns match at start)

    If applying the pattern would produce a different result than the direct correction,
    the pattern is unsafe and should be rejected.

    Example:
        Pattern: `toin → tion` (suffix pattern)
        Direct correction: `washingtoin → washington`
        Problem: Pattern would match `washingtoin` as suffix and produce
            `washingtion` ≠ `washington`
        Result: Pattern should be rejected

    Args:
        typo_pattern: The typo pattern to check
        word_pattern: The word pattern to check
        all_corrections: All corrections that exist (to check against)
        pattern_occurrences: Corrections that this pattern would replace (exclude from check)
        correction_index: Optional pre-built index for faster lookups

    Returns:
        Tuple of (is_safe, error_message). error_message is None if safe.
    """
    # Build set of corrections that this pattern replaces (to exclude from check)
    pattern_typos = {(typo, word) for typo, word, _ in pattern_occurrences}

    # Use index if available, otherwise fall back to linear scan
    if correction_index is not None:
        # Check suffix matches (for RTL/QMK)
        suffix_matches = correction_index.get_suffix_matches(typo_pattern)
        for other_typo, other_word, _ in suffix_matches:
            # Skip corrections that this pattern replaces
            if (other_typo, other_word) in pattern_typos:
                continue
            # Skip if pattern is the same as the typo (no conflict)
            if other_typo == typo_pattern:
                continue

            # Calculate what applying the pattern would produce
            # For suffix matches, we need to preserve any suffix that comes after the pattern
            # in the original word
            remaining_typo = other_typo[: -len(typo_pattern)]
            # Find what comes after the typo_pattern in the original word
            # The typo_pattern appears at the end of other_typo, so find where it appears
            # in other_word and get what comes after it
            typo_pattern_pos_in_word = other_word.rfind(typo_pattern)
            if typo_pattern_pos_in_word != -1:
                # Pattern found in word, get what comes after it
                word_suffix = other_word[typo_pattern_pos_in_word + len(typo_pattern) :]
                pattern_result = remaining_typo + word_pattern + word_suffix
            else:
                # Pattern not found in word, just do simple replacement
                pattern_result = remaining_typo + word_pattern

            # If pattern would produce different result, it's unsafe
            if pattern_result != other_word:
                return False, (
                    f"Would incorrectly match '{other_typo}' → '{other_word}' "
                    f"as suffix (would produce '{pattern_result}' instead)"
                )

        # Check prefix matches (for LTR/Espanso)
        prefix_matches = correction_index.get_prefix_matches(typo_pattern)
        for other_typo, other_word, _ in prefix_matches:
            # Skip corrections that this pattern replaces
            if (other_typo, other_word) in pattern_typos:
                continue
            # Skip if pattern is the same as the typo (no conflict)
            if other_typo == typo_pattern:
                continue

            # Calculate what applying the pattern would produce
            remaining = other_typo[len(typo_pattern) :]
            pattern_result = word_pattern + remaining

            # If pattern would produce different result, it's unsafe
            if pattern_result != other_word:
                return False, (
                    f"Would incorrectly match '{other_typo}' → '{other_word}' "
                    f"as prefix (would produce '{pattern_result}' instead)"
                )
    else:
        # Fallback to original linear scan (for backward compatibility)
        for other_typo, other_word, _ in all_corrections:
            # Skip corrections that this pattern replaces
            if (other_typo, other_word) in pattern_typos:
                continue

            # Check if pattern appears as SUFFIX of other correction's typo
            if other_typo.endswith(typo_pattern) and other_typo != typo_pattern:
                # Calculate what applying the pattern would produce
                # For suffix matches, we need to preserve any suffix that comes after the pattern
                # in the original word
                remaining_typo = other_typo[: -len(typo_pattern)]
                # Find what comes after the typo_pattern in the original word
                # The typo_pattern appears at the end of other_typo, so find where it appears
                # in other_word and get what comes after it
                typo_pattern_pos_in_word = other_word.rfind(typo_pattern)
                if typo_pattern_pos_in_word != -1:
                    # Pattern found in word, get what comes after it
                    word_suffix = other_word[typo_pattern_pos_in_word + len(typo_pattern) :]
                    pattern_result = remaining_typo + word_pattern + word_suffix
                else:
                    # Pattern not found in word, just do simple replacement
                    pattern_result = remaining_typo + word_pattern

                # If pattern would produce different result, it's unsafe
                if pattern_result != other_word:
                    return False, (
                        f"Would incorrectly match '{other_typo}' → '{other_word}' "
                        f"as suffix (would produce '{pattern_result}' instead)"
                    )

            # Check if pattern appears as PREFIX of other correction's typo
            if other_typo.startswith(typo_pattern) and other_typo != typo_pattern:
                # Calculate what applying the pattern would produce
                remaining = other_typo[len(typo_pattern) :]
                pattern_result = word_pattern + remaining

                # If pattern would produce different result, it's unsafe
                if pattern_result != other_word:
                    return False, (
                        f"Would incorrectly match '{other_typo}' → '{other_word}' "
                        f"as prefix (would produce '{pattern_result}' instead)"
                    )

    return True, None


def check_pattern_redundant_with_other_patterns(
    typo_pattern: str,
    word_pattern: str,
    boundary: BoundaryType,
    accepted_patterns: list[Correction],
) -> tuple[bool, str | None, Correction | None]:
    """Check if a pattern would be redundant given already-accepted patterns.

    A pattern is redundant if a shorter pattern would produce the same result.
    For example, if `tehr -> ther` is already accepted, then `otehr -> other`
    is redundant because applying `tehr -> ther` to `otehr` produces `other`.

    This check works regardless of matching direction because it checks if
    applying the shorter pattern to the longer typo produces the same result.

    Args:
        typo_pattern: The typo pattern to check
        word_pattern: The word pattern to check
        boundary: The boundary type of the pattern
        accepted_patterns: List of already-accepted patterns to check against

    Returns:
        Tuple of (is_redundant, error_message, blocking_pattern).
        error_message and blocking_pattern are None if not redundant.
    """
    for other_typo, other_word, other_boundary in accepted_patterns:
        # Only check patterns with the same boundary type
        if other_boundary != boundary:
            continue

        # Skip if patterns are the same
        if other_typo == typo_pattern and other_word == word_pattern:
            continue

        # Only check if shorter pattern is a substring of longer pattern
        if len(other_typo) >= len(typo_pattern):
            continue

        # Check all positions where shorter pattern appears in longer pattern
        start_pos = 0
        while True:
            pos = typo_pattern.find(other_typo, start_pos)
            if pos == -1:
                break

            # Calculate what applying the shorter pattern would produce
            # Replace other_typo with other_word at position pos in typo_pattern
            remaining_prefix = typo_pattern[:pos]
            remaining_suffix = typo_pattern[pos + len(other_typo) :]
            result = remaining_prefix + other_word + remaining_suffix

            # If applying shorter pattern produces same result, longer pattern is redundant
            if result == word_pattern:
                blocking_pattern = (other_typo, other_word, other_boundary)
                return (
                    True,
                    (
                        f"Redundant: shorter pattern '{other_typo}' → '{other_word}' "
                        f"already produces '{word_pattern}' when applied to '{typo_pattern}' "
                        f"(at position {pos})"
                    ),
                    blocking_pattern,
                )

            start_pos = pos + 1

    return False, None, None
