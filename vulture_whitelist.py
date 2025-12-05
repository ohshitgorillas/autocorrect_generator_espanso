"""Vulture whitelist for false positives.

This file contains code that vulture incorrectly flags as unused
but is actually used by frameworks (Pydantic) that static analysis cannot detect.
"""
# pylint: disable=all
# Pydantic field validator - used by framework via @field_validator decorator
_.parse_string_set  # noqa: F821  # unused method (entroppy/core/config.py:50)

# Pydantic model validator - used by framework via @model_validator decorator
_.validate_cross_fields  # noqa: F821  # unused method (entroppy/core/config.py:62)

# Pydantic model_config class variable - read by framework at class definition time
# Required to allow non-Pydantic types (DebugTypoMatcher) in Config model
model_config  # noqa: F821  # unused variable (entroppy/core/config.py:74)

# Pydantic model_config class variable - read by framework at class definition time
# Required to allow non-Pydantic types (ExclusionMatcher) in DictionaryData model
model_config  # noqa: F821  # unused variable (entroppy/processing/stages/data_models.py:26)
