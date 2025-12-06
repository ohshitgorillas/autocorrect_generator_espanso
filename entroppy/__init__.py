"""EntropPy - Autocorrect dictionary generator for Espanso.

Generate mechanical typing error corrections for Espanso text expander.
"""

from entroppy.core import BoundaryType, Config, Correction, load_config
from entroppy.processing import run_pipeline
from entroppy.utils.debug import DebugTypoMatcher
from entroppy.utils.logging import setup_logger

__version__ = "0.7.1"
__all__ = [
    "BoundaryType",
    "Config",
    "Correction",
    "load_config",
    "run_pipeline",
    "DebugTypoMatcher",
    "setup_logger",
]
