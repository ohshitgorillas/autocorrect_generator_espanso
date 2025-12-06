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

# Functions used via imports - vulture can't detect usage through imports
format_corrections_with_cache  # noqa: F821  # unused function (entroppy/resolution/platform_conflicts/formatting.py:92)
is_debug_target  # noqa: F821  # unused function (entroppy/resolution/state_debug.py:34)
create_correction_history_entry  # noqa: F821  # unused function (entroppy/resolution/state_history.py:17)
create_pattern_history_entry  # noqa: F821  # unused function (entroppy/resolution/state_history.py:52)
create_debug_trace_entry  # noqa: F821  # unused function (entroppy/resolution/state_history.py:87)
update_pattern_prefix_index_add  # noqa: F821  # unused function (entroppy/resolution/state_patterns.py:13)
update_pattern_prefix_index_remove  # noqa: F821  # unused function (entroppy/resolution/state_patterns.py:28)

# Parallel processing functions - used via module attribute access (parallel.function_name)
# vulture can't detect usage through module.attribute syntax
DebugTypoMatcher  # unused import (entroppy/resolution/platform_conflicts/parallel.py:72)
detect_conflicts_for_chunk  # unused function (entroppy/resolution/platform_conflicts/parallel.py:83)
resolve_conflicts_sequential  # unused function (entroppy/resolution/platform_conflicts/parallel.py:132)
divide_into_chunks  # unused function (entroppy/resolution/platform_conflicts/parallel.py:221)

# StateCaching class and methods - used via instance attribute access (self._caching.method_name)
# vulture can't detect usage through instance.attribute syntax
StateCaching  # unused class (entroppy/resolution/state_caching.py:11)
_._uncovered_typos  # unused attribute (entroppy/resolution/state_caching.py:25)
_.get_cached_boundary  # unused method (entroppy/resolution/state_caching.py:27)
_.get_cached_false_trigger  # unused method (entroppy/resolution/state_caching.py:53)
_.clear_false_trigger_cache  # unused method (entroppy/resolution/state_caching.py:88)
_.invalidate_pattern_coverage_cache  # unused method (entroppy/resolution/state_caching.py:92)
_.invalidate_pattern_coverage_for_typo  # unused method (entroppy/resolution/state_caching.py:96)
_.is_typo_covered_by_pattern  # unused method (entroppy/resolution/state_caching.py:104)
