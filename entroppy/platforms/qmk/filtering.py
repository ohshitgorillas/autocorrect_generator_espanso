"""QMK filtering logic for corrections."""

from collections import defaultdict

from entroppy.core import BoundaryType, Correction
from entroppy.platforms.qmk.typo_index import TypoIndex


def filter_character_set(corrections: list[Correction]) -> tuple[list[Correction], list]:
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


def filter_character_set_and_resolve_same_typo(
    corrections: list[Correction],
) -> tuple[list[Correction], list, list]:
    """
    Combined pass: filter invalid characters and resolve same-typo conflicts.

    This combines two operations in a single pass to reduce iterations:
    1. Character set validation (only a-z and ')
    2. Same-typo conflict resolution (keep least restrictive boundary)

    Returns:
        Tuple of (filtered_corrections, char_filtered, same_typo_conflicts)
    """
    char_filtered = []
    typo_groups = defaultdict(list)

    # Single pass: filter characters and group by typo
    for typo, word, boundary in corrections:
        # Character validation
        if not all(c.isalpha() or c == "'" for c in typo.lower()):
            char_filtered.append((typo, word, "typo contains invalid chars"))
            continue
        if not all(c.isalpha() or c == "'" for c in word.lower()):
            char_filtered.append((typo, word, "word contains invalid chars"))
            continue

        # Convert to lowercase and group by typo
        typo_lower = typo.lower()
        word_lower = word.lower()
        typo_groups[typo_lower].append((typo_lower, word_lower, boundary))

    # Resolve same-typo conflicts
    boundary_priority = {
        BoundaryType.NONE: 0,
        BoundaryType.LEFT: 1,
        BoundaryType.RIGHT: 1,
        BoundaryType.BOTH: 2,
    }

    deduped = []
    same_typo_conflicts = []

    for _, corrections_list in typo_groups.items():
        if len(corrections_list) == 1:
            deduped.append(corrections_list[0])
        else:
            sorted_by_restriction = sorted(corrections_list, key=lambda c: boundary_priority[c[2]])
            kept = sorted_by_restriction[0]
            deduped.append(kept)

            for removed in sorted_by_restriction[1:]:
                same_typo_conflicts.append((removed[0], removed[1], kept[0], kept[1], removed[2]))

    return deduped, char_filtered, same_typo_conflicts


def resolve_same_typo_conflicts(corrections: list[Correction]) -> tuple[list[Correction], list]:
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
            sorted_by_restriction = sorted(corrections_list, key=lambda c: boundary_priority[c[2]])
            kept = sorted_by_restriction[0]
            deduped.append(kept)

            for removed in sorted_by_restriction[1:]:
                conflicts.append((removed[0], removed[1], kept[0], kept[1], removed[2]))

    return deduped, conflicts


def detect_suffix_conflicts(corrections: list[Correction]) -> tuple[list[Correction], list]:
    """
    Detect RTL suffix conflicts across ALL typos.

    QMK scans right-to-left. If typing "wriet":
    - Finds suffix "riet" first
    - Produces "w" + "rite" = "write"
    - So `riet -> rite` makes `wriet -> write` redundant

    This checks across all boundary types since QMK's RTL matching
    doesn't respect boundaries during the matching phase.

    Uses TypoIndex for optimized O(n log n) conflict detection instead of O(n²).
    """
    if not corrections:
        return [], []

    # Build index once for efficient lookups
    index = TypoIndex(corrections)
    return index.find_suffix_conflicts(corrections)


def detect_substring_conflicts(corrections: list[Correction]) -> tuple[list[Correction], list]:
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

    Uses TypoIndex for optimized O(n log n) conflict detection instead of O(n²).
    """
    if not corrections:
        return [], []

    # Build index once for efficient lookups
    index = TypoIndex(corrections)
    return index.find_substring_conflicts(corrections)


def filter_corrections(
    corrections: list[Correction], allowed_chars: set[str]
) -> tuple[list[Correction], dict]:
    """
    Apply QMK-specific filtering.

    - Character set validation (only a-z and ')
    - Same-typo-text conflict detection (different boundaries)
    - Suffix conflict detection (RTL matching optimization)
    - Substring conflict detection (QMK's hard constraint)

    Optimized to combine character filtering and same-typo resolution in a single pass.

    Args:
        corrections: List of corrections to filter
        allowed_chars: Set of allowed characters (for validation)

    Returns:
        Tuple of (filtered_corrections, metadata)
    """
    # Combined pass: character filtering + same-typo conflict resolution
    deduped, char_filtered, same_typo_conflicts = filter_character_set_and_resolve_same_typo(
        corrections
    )

    # Conflict detection passes (require sorted/grouped data, so kept separate)
    after_suffix, suffix_conflicts = detect_suffix_conflicts(deduped)
    final, substring_conflicts = detect_substring_conflicts(after_suffix)

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
