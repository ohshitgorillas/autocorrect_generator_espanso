"""Type definitions for EntropPy."""

from enum import Enum

from entroppy.core.boundaries import BoundaryType


class MatchDirection(Enum):
    """Direction in which platform scans for matches."""

    LEFT_TO_RIGHT = "ltr"  # Espanso
    RIGHT_TO_LEFT = "rtl"  # QMK


class PatternType(Enum):
    """Type of pattern based on where it appears in words."""

    PREFIX = "prefix"  # Pattern appears at start of words
    SUFFIX = "suffix"  # Pattern appears at end of words
    SUBSTRING = "substring"  # Pattern appears in middle of words (true substring)


# Type alias for corrections: (typo, correct_word, boundary_type)
Correction = tuple[str, str, BoundaryType]
