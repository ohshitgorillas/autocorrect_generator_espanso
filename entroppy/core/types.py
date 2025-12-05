"""Type definitions for EntropPy."""

from enum import Enum

from entroppy.core.boundaries import BoundaryType


class MatchDirection(Enum):
    """Direction in which platform scans for matches."""

    LEFT_TO_RIGHT = "ltr"  # Espanso
    RIGHT_TO_LEFT = "rtl"  # QMK


# Type alias for corrections: (typo, correct_word, boundary_type)
Correction = tuple[str, str, BoundaryType]
