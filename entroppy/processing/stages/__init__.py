"""Pipeline stages for processing typos.

NOTE: Stages 3-6 (collision resolution, pattern generalization, conflict removal)
have been replaced by the iterative solver architecture in entroppy/resolution/.
Only stages 1-2 (dictionary loading, typo generation) remain here.
"""

from .data_models import DictionaryData, TypoGenerationResult
from .dictionary_loading import load_dictionaries
from .typo_generation import generate_typos

__all__ = [
    # Data models
    "DictionaryData",
    "TypoGenerationResult",
    # Stage functions
    "load_dictionaries",
    "generate_typos",
]
