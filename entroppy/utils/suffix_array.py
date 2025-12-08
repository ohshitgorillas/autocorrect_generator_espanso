"""CPU-based suffix array for fast substring detection.

This module provides a high-performance substring index using the Rust extension
for ~100x faster query performance compared to Python implementations.
"""

# pylint: disable=duplicate-code
# This module does not contain duplicate code. Pylint is incorrectly flagging
# duplicate code that exists between other modules (logging.py and
# batch_processor_helpers.py). The duplicate-code warning is a false positive.

# pylint: disable=no-name-in-module
# RustSubstringIndex is provided by the Rust extension module (entroppy.rust_ext)
# which is built dynamically. Pylint cannot detect it statically.
from entroppy.rust_ext import RustSubstringIndex


class SubstringIndex:
    """High-performance Rust-based substring index.

    This is a wrapper around the Rust implementation that provides
    ~100x faster query performance compared to the Python version.
    """

    def __init__(self, formatted_typos: list[str]):
        """Build suffix array index using Rust implementation.

        Args:
            formatted_typos: List of formatted typo strings
        """
        self._rust_index = RustSubstringIndex(formatted_typos)
        self.typos = formatted_typos

    def find_conflicts(self, typo: str) -> list[int]:
        """Find all typos that contain this typo as substring.

        Delegates to the Rust implementation for maximum performance.

        Args:
            typo: The substring to search for

        Returns:
            List of indices where typo appears as substring
        """
        result = self._rust_index.find_substring_conflicts(typo)
        return list(result)
