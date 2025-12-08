"""Boundary detection functions."""

from entroppy.core.boundaries.types import BoundaryIndex, BoundaryType


def _batch_check_substrings(
    typos: list[str],
    validation_index: BoundaryIndex,
    source_index: BoundaryIndex,
) -> tuple[dict[str, bool], dict[str, bool]]:
    """Batch check substring conflicts for multiple typos using suffix arrays.

    This helper function extracts the common pattern of checking substring conflicts
    using suffix arrays for both validation and source indexes.

    Args:
        typos: List of typo strings to check
        validation_index: Pre-built index for validation set
        source_index: Pre-built index for source words

    Returns:
        Tuple of (substring_val_results, substring_src_results) dicts
    """
    val_suffix_index = validation_index.get_suffix_array_index()
    src_suffix_index = source_index.get_suffix_array_index()

    substring_val_results = {}
    substring_src_results = {}
    for typo in typos:
        val_matches = val_suffix_index.find_conflicts(typo)
        src_matches = src_suffix_index.find_conflicts(typo)
        substring_val_results[typo] = len(val_matches) > 0
        substring_src_results[typo] = len(src_matches) > 0

    return substring_val_results, substring_src_results


def _check_typo_in_wordset(
    typo: str,
    check_type: str,
    index: BoundaryIndex,
) -> bool:
    """Check if typo matches any word in the set based on check type.

    Args:
        typo: The typo string to check
        check_type: Type of check - 'substring', 'prefix', or 'suffix'
        index: Pre-built index for faster lookups

    Returns:
        True if typo matches any word according to check_type
    """
    if check_type == "substring":
        return typo in index.substring_set
    if check_type == "prefix":
        # Check if typo is a prefix of any word (excluding exact match)
        if typo in index.prefix_index:
            matching_words = index.prefix_index[typo]
            # Exclude exact match
            return any(word != typo for word in matching_words)
        return False
    if check_type == "suffix":
        # Check if typo is a suffix of any word (excluding exact match)
        if typo in index.suffix_index:
            matching_words = index.suffix_index[typo]
            # Exclude exact match
            return any(word != typo for word in matching_words)
        return False

    return False


def is_substring_of_any(typo: str, index: BoundaryIndex) -> bool:
    """Check if typo is a substring of any word.

    Args:
        typo: The typo string to check
        index: Pre-built index for faster lookups

    Returns:
        True if typo is a substring of any word (excluding exact matches)
    """
    # First check the pre-built substring_set for fast lookup
    if typo in index.substring_set:
        return True
    # Also do a direct check against all words in case substring_set is incomplete
    # This is a fallback for when validation set doesn't include all possible words
    for word in index.word_set:
        if typo in word and typo != word:
            return True
    return False


def would_trigger_at_start(typo: str, index: BoundaryIndex) -> bool:
    """Check if typo appears as prefix.

    Args:
        typo: The typo string to check
        index: Pre-built index for faster lookups

    Returns:
        True if typo appears as a prefix of any word (excluding exact matches)
    """
    return _check_typo_in_wordset(typo, "prefix", index)


def would_trigger_at_end(typo: str, index: BoundaryIndex) -> bool:
    """Check if typo appears as suffix.

    Args:
        typo: The typo string to check
        index: Pre-built index for faster lookups

    Returns:
        True if typo appears as a suffix of any word (excluding exact matches)
    """
    return _check_typo_in_wordset(typo, "suffix", index)


def determine_boundaries(
    typo: str,
    validation_index: BoundaryIndex,
    source_index: BoundaryIndex,
) -> BoundaryType:
    """Determine what boundaries are needed for a typo.

    Args:
        typo: The typo string
        validation_index: Pre-built index for validation set
        source_index: Pre-built index for source words

    Returns:
        BoundaryType indicating what boundaries are needed
    """
    # Check if typo appears as substring in other contexts
    is_substring_source = is_substring_of_any(typo, source_index)
    is_substring_validation = is_substring_of_any(typo, validation_index)

    if not is_substring_source and not is_substring_validation:
        return BoundaryType.NONE

    appears_as_prefix = would_trigger_at_start(typo, validation_index)
    appears_as_suffix = would_trigger_at_end(typo, validation_index)

    if not appears_as_prefix and not appears_as_suffix:
        return BoundaryType.BOTH
    if appears_as_suffix and not appears_as_prefix:
        return BoundaryType.LEFT
    if appears_as_prefix and not appears_as_suffix:
        return BoundaryType.RIGHT
    return BoundaryType.BOTH


def batch_determine_boundaries(
    typos: list[str],
    validation_index: BoundaryIndex,
    source_index: BoundaryIndex,
) -> dict[str, BoundaryType]:
    """Batch determine boundaries for multiple typos.

    Uses batch operations for efficiency instead of calling determine_boundaries
    individually for each typo.

    Args:
        typos: List of typo strings to check
        validation_index: Pre-built index for validation set
        source_index: Pre-built index for source words

    Returns:
        Dict mapping typo -> BoundaryType
    """
    # Batch check all conditions at once
    start_val_results = validation_index.batch_check_start(typos)
    end_val_results = validation_index.batch_check_end(typos)

    # Get substring checks using suffix array (efficient)
    substring_val_results, substring_src_results = _batch_check_substrings(
        typos, validation_index, source_index
    )

    # Determine boundaries for each typo
    boundary_map: dict[str, BoundaryType] = {}
    for typo in typos:
        is_substring_source = substring_src_results[typo]
        is_substring_validation = substring_val_results[typo]

        if not is_substring_source and not is_substring_validation:
            boundary_map[typo] = BoundaryType.NONE
            continue

        appears_as_prefix = start_val_results[typo]
        appears_as_suffix = end_val_results[typo]

        if not appears_as_prefix and not appears_as_suffix:
            boundary_map[typo] = BoundaryType.BOTH
        elif appears_as_suffix and not appears_as_prefix:
            boundary_map[typo] = BoundaryType.LEFT
        elif appears_as_prefix and not appears_as_suffix:
            boundary_map[typo] = BoundaryType.RIGHT
        else:
            boundary_map[typo] = BoundaryType.BOTH

    return boundary_map
