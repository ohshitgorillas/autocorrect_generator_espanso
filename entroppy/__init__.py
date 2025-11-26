"""EntropPy - Autocorrect dictionary generator for Espanso.

Generate mechanical typing error corrections for Espanso text expander.
"""

from .config import BoundaryType, Config, Correction, load_config
from .pipeline import run_pipeline

__version__ = "0.1.5"
__all__ = ["BoundaryType", "Config", "Correction", "load_config", "run_pipeline"]
