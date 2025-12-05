"""Boundary detection for typo corrections."""

from enum import Enum

from entroppy.utils.constants import Constants


class BoundaryIndex:
    """Index for efficient boundary detection queries.

    Pre-builds indexes for prefix, suffix, and substring checks to avoid
    linear searches through word sets. Provides O(1) or O(log n) lookups
    instead of O(n) linear scans.

    Attributes:
        prefix_index: Dict mapping prefixes to sets of words starting with that prefix
        suffix_index: Dict mapping suffixes to sets of words ending with that suffix
        substring_set: Set of all substrings (excluding exact matches) from all words
        word_set: Original word set for reference
    """

    def __init__(self, word_set: set[str] | frozenset[str]) -> None:
        """Build indexes from a word set.

        Args:
            word_set: Set of words to build indexes from
        """
        self.word_set = word_set
        self.prefix_index: dict[str, set[str]] = {}
        self.suffix_index: dict[str, set[str]] = {}
        self.substring_set: set[str] = set()

        # Build prefix index: for each word, add all prefixes to index
        for word in word_set:
            for i in range(1, len(word) + 1):
                prefix = word[:i]
                if prefix not in self.prefix_index:
                    self.prefix_index[prefix] = set()
                self.prefix_index[prefix].add(word)

        # Build suffix index: for each word, add all suffixes to index
        for word in word_set:
            for i in range(len(word)):
                suffix = word[i:]
                if suffix not in self.suffix_index:
                    self.suffix_index[suffix] = set()
                self.suffix_index[suffix].add(word)

        # Build substring set: for each word, add all substrings (excluding exact match)
        for word in word_set:
            for i in range(len(word)):
                for j in range(i + 1, len(word) + 1):
                    substring = word[i:j]
                    if substring != word:  # Exclude exact matches
                        self.substring_set.add(substring)


class BoundaryType(Enum):
    """Boundary types for Espanso matches."""

    NONE = "none"  # No boundaries - triggers anywhere
    LEFT = "left"  # Left boundary only - must be at word start
    RIGHT = "right"  # Right boundary only - must be at word end
    BOTH = "both"  # Both boundaries - standalone word only


def parse_boundary_markers(pattern: str) -> tuple[str, BoundaryType | None]:
    """Parse boundary markers from a pattern string.

    Supports the following formats:
    - :pattern: -> (pattern, BoundaryType.BOTH)
    - :pattern -> (pattern, BoundaryType.LEFT)
    - pattern: -> (pattern, BoundaryType.RIGHT)
    - pattern -> (pattern, None)

    Args:
        pattern: The pattern string with optional boundary markers

    Returns:
        Tuple of (core_pattern, boundary_type)
    """
    if not pattern:
        return pattern, None

    starts_with_colon = pattern.startswith(Constants.BOUNDARY_MARKER)
    ends_with_colon = pattern.endswith(Constants.BOUNDARY_MARKER)

    # Determine boundary type
    if starts_with_colon and ends_with_colon:
        boundary_type = BoundaryType.BOTH
        core_pattern = pattern[1:-1]
    elif starts_with_colon:
        boundary_type = BoundaryType.LEFT
        core_pattern = pattern[1:]
    elif ends_with_colon:
        boundary_type = BoundaryType.RIGHT
        core_pattern = pattern[:-1]
    else:
        boundary_type = None
        core_pattern = pattern

    return core_pattern, boundary_type


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


def format_boundary_name(boundary: BoundaryType) -> str:
    """Format boundary type as a name (e.g., 'NONE', 'LEFT', 'RIGHT', 'BOTH').

    Args:
        boundary: The boundary type to format

    Returns:
        Formatted boundary name
    """
    if boundary == BoundaryType.NONE:
        return "NONE"
    if boundary == BoundaryType.LEFT:
        return "LEFT"
    if boundary == BoundaryType.RIGHT:
        return "RIGHT"
    if boundary == BoundaryType.BOTH:
        return "BOTH"
    raise ValueError(f"Invalid boundary type: {boundary}")


def format_boundary_display(boundary: BoundaryType) -> str:
    """Format boundary type for display in reports (e.g., '(LEFT boundary)' or empty string).

    Args:
        boundary: The boundary type to format

    Returns:
        Formatted boundary display string, empty string for NONE
    """
    if boundary == BoundaryType.NONE:
        return ""
    if boundary == BoundaryType.LEFT:
        return "(LEFT boundary)"
    if boundary == BoundaryType.RIGHT:
        return "(RIGHT boundary)"
    if boundary == BoundaryType.BOTH:
        return "(BOTH boundaries)"
    raise ValueError(f"Invalid boundary type: {boundary}")
