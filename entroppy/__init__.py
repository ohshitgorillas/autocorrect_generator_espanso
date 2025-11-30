"""EntropPy - Autocorrect dictionary generator for Espanso.

Generate mechanical typing error corrections for Espanso text expander.
"""

from entroppy.core import BoundaryType, Config, Correction, load_config
from entroppy.utils import DebugTypoMatcher, setup_logger
from entroppy.processing import run_pipeline

__version__ = "0.4.2"
__all__ = ["BoundaryType", "Config", "Correction", "load_config", "run_pipeline", "DebugTypoMatcher", "setup_logger"]
