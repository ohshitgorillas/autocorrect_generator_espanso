"""Utility functions for EntropPy."""

from entroppy.utils.debug import (
    DebugTypoMatcher,
    is_debug_correction,
    is_debug_word,
    is_debug_typo,
    log_debug_correction,
    log_debug_typo,
    log_debug_word,
)
from entroppy.utils.helpers import compile_wildcard_regex
from entroppy.utils.logging import setup_logger

__all__ = [
    "DebugTypoMatcher",
    "is_debug_correction",
    "is_debug_word",
    "is_debug_typo",
    "log_debug_correction",
    "log_debug_typo",
    "log_debug_word",
    "compile_wildcard_regex",
    "setup_logger",
]
