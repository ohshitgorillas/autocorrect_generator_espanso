# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Changed

- **Refactored collision resolution module**
  - Split `entroppy/resolution/collision.py` (928 lines) into smaller, focused modules:
    - `worker_context.py`: Worker context dataclass and thread-local storage management
    - `typo_index.py`: Typo substring index building with parallel processing support
    - `exclusion.py`: Exclusion handling logic
    - `boundary_selection.py`: Boundary choosing logic for typos
    - `correction_processing.py`: Single word and collision case processing
    - `substring_conflicts.py`: Substring conflict removal functionality
    - `collision.py`: Main `resolve_collisions()` function (now ~330 lines)
  - **Reduced redundancies**:
    - Consolidated duplicate boundary selection logic
    - Unified exclusion handling in a single module
    - Shared correction processing logic between single-threaded and parallel modes
  - **Fixed bug**: Corrected indentation error in single-threaded collision resolution loop
  - **Maintained backward compatibility**: All public APIs remain unchanged
  - **Impact**: Improved code maintainability, easier testing, and clearer separation of concerns

- **Improved logging and user experience**
  - **Startup and completion messages**:
    - Added startup banner with program name and configuration summary
    - Added completion summary with success/failure indicators
    - Improved error handling with clear visual feedback
  - **Pipeline stage messages**:
    - Standardized stage numbering (Stage 1-8) for better clarity
    - Added stage completion indicators (✓) for visual feedback
    - Improved message formatting with consistent indentation
    - Added summary statistics after each major stage
    - Removed inconsistent `#` prefixes from messages
  - **Error messages**:
    - Added ✗ prefix to all error messages for visual clarity
    - Added actionable suggestions (e.g., "Please check file permissions")
    - Improved error context and troubleshooting hints
    - Consistent error formatting across all modules
  - **Output messages**:
    - Replaced `print()` with `logger.info()` for consistency (QMK stdout output)
    - Improved file writing confirmation messages
    - Better report generation feedback
  - **User experience enhancements**:
    - Clear visual indicators (✓ for success, ✗ for errors, ⚠️ for warnings)
    - Consistent message formatting throughout the application
    - Better progress feedback at each processing stage
    - More informative statistics and summaries
    - Improved readability with proper indentation and spacing

### Performance

- **Collision resolution parallelization**
  - Parallelized the "resolving collisions" phase for better performance
  - **Multiprocessing support** (`entroppy/resolution/collision.py`):
    - Added `CollisionResolutionContext` dataclass for passing immutable data to worker processes
    - Created `_process_typo_worker()` function to process individual typo collisions in parallel
    - Uses `multiprocessing.Pool` with configurable number of workers (via `config.jobs`)
    - Pre-builds boundary indexes eagerly during worker initialization to prevent progress bar freezing
    - Falls back to single-threaded mode when `jobs=1` or for small datasets
  - **Substring index building parallelization**:
    - Parallelized `_build_typo_substring_index()` function using chunk-based processing
    - Splits typos into chunks (4 chunks per worker) for load balancing
    - Each worker processes a chunk independently, checking all typos against the full typo list
    - Results are merged efficiently after parallel processing
  - **Progress tracking**:
    - Added progress bars for both parallel and single-threaded modes
    - Progress bar tracks typos processed (not chunks) for better user feedback
    - Added logging messages during initialization to show what's happening before progress bar starts
    - Shows chunk creation, worker initialization, and processing start messages
  - **Integration**:
    - Updated `resolve_collisions()` to accept `jobs` and `exclusion_set` parameters
    - Updated `resolve_typo_collisions()` stage to pass `config.jobs` and `dict_data.exclusions`
    - Maintains backward compatibility (defaults to `jobs=1` for sequential processing)
  - **Impact**: Significant speedup proportional to number of CPU cores for large typo maps (10K+ typos)
  - **Estimated Improvement**: Near-linear speedup with number of workers for collision resolution phase

- **Pattern validation optimization (Phase 6)**
  - Optimized source word corruption checks in pattern validation
  - **SourceWordIndex class** (`entroppy/core/pattern_validation.py`):
    - Pre-builds indexes of patterns that appear at word boundaries in source words
    - For RTL patterns: indexes all prefixes that appear at word boundaries (start or after non-alpha)
    - For LTR patterns: indexes all suffixes that appear at word boundaries (end or before non-alpha)
    - Eliminates O(patterns × source_words) linear searches through source words
  - **Caching**:
    - Added `@functools.lru_cache` wrapper for fallback corruption checks
    - Caches validation results for patterns that have been checked before
  - **Integration**:
    - Updated `generalize_patterns()` to build `SourceWordIndex` once and reuse for all pattern checks
    - Updated `check_pattern_conflicts()` to accept optional `SourceWordIndex` parameter
    - Maintains backward compatibility with fallback to cached linear search
  - **Impact**: 50-70% reduction in pattern validation time for large datasets with many source words
  - **Estimated Improvement**: Pattern validation now uses O(1) lookups instead of O(source_words) scans per pattern

## [0.5.1] - 2025-11-30

### Fixed

- **Pattern classification bug in QMK ranking reports**
  - Fixed incorrect classification where patterns were being reported as "direct corrections" instead of "patterns"
  - Root cause: Patterns that block other corrections (substring/suffix conflicts) were not being added to `pattern_replacements` when conflicts were detected during platform filtering
  - **Universal pattern update logic** (`entroppy/processing/stages/conflict_removal.py`):
    - Added `update_patterns_from_conflicts()` function that works for all platforms
    - Updates `pattern_replacements` when conflicts are detected during platform filtering
    - When a shorter correction blocks a longer one, the shorter correction is now correctly identified as a pattern
  - **Pattern classification** (`entroppy/platforms/qmk/reports.py`):
    - Report classification now uses `pattern_replacements` as the source of truth
    - Corrections in `pattern_replacements` are correctly classified as PATTERNS
    - BOTH boundary corrections are correctly excluded from being patterns (they can't block anything by definition)
  - **Pipeline integration** (`entroppy/processing/pipeline.py`):
    - Pattern updates now happen after platform filtering for all platforms
    - Collects conflicts from filter metadata (suffix_conflicts, substring_conflicts) and updates patterns accordingly
  - **Impact**: Reports now correctly show pattern counts and classifications. For example, "tje → the" that blocks "tjen → then" is now correctly classified as a PATTERN

## [0.5.0] - 2025-01-29

### Added

- **Pydantic v2 type validation system**
  - Replaced manual validation with Pydantic BaseModel for automatic type checking
  - Added Pydantic v2 dependency (`pydantic>=2.0.0,<3.0.0`)
  - **Config class** (`entroppy/core/config.py`):
    - Converted from `@dataclass` to Pydantic `BaseModel`
    - Added field validators with constraints (e.g., `ge=1`, `gt=0`)
    - Added `Literal["espanso", "qmk"]` for platform validation
    - Field validator for string set parsing (`debug_words`, `debug_typos`)
    - Model validator for cross-field validation (max_word_length >= min_word_length, QMK requirements)
    - Automatic type coercion from JSON configuration
  - **Data models** (`entroppy/processing/stages/data_models.py`):
    - Converted all stage result models from `@dataclass` to Pydantic `BaseModel`
    - Added field constraints (e.g., `elapsed_time >= 0`, `removed_count >= 0`)
    - Fixed type definitions to match actual code behavior:
      - `adjacent_letters_map`: `dict[str, str]` (strings, not lists)
      - `skipped_collisions`: `tuple[str, list[str], float]` (list of words, not single string)
      - `skipped_short`: `list[tuple[str, str, int]]` (tuples, not strings)
      - `rejected_patterns`: `tuple[str, str, str | list[str]]` (flexible reason type)
  - **Benefits**:
    - ~50 lines of manual validation code eliminated
    - Better error messages with field-level validation details
    - Automatic type coercion for JSON configuration loading
    - Runtime validation at object creation time
    - Improved developer experience with IDE support and field descriptions
    - Backward compatible with existing code and tests

- **Code quality improvements: constants and helper functions**
  - **Constants file** (`entroppy/utils/constants.py`):
    - Centralized all magic numbers and strings to avoid duplication
    - Added `ESPANSO_MAX_ENTRIES_WARNING` (1000) for Espanso file size warnings
    - Added `WORDFREQ_MULTIPLIER` (3) for wordfreq fetching
    - Added `ADJACENT_MAP_SEPARATOR` (" -> ") for adjacent letters map parsing
    - Added `EXCLUSION_SEPARATOR` ("->") for exclusion pattern detection
    - Added `QMK_OUTPUT_SEPARATOR` (" -> ") for QMK output formatting
    - Added `BOUNDARY_MARKER` (":") for boundary pattern parsing
    - Added `QMK_MAX_CORRECTIONS` (6000) for QMK theoretical maximum
    - Added `QMK_MAX_STRING_LENGTH` (62) for QMK string length limits
  - **Helper functions**:
    - Added `log_if_debug_correction()` in `entroppy/utils/debug.py`:
      - Reduces code duplication by combining `is_debug_correction()` check and `log_debug_correction()` call
      - Used throughout codebase to simplify debug logging patterns
    - Added `expand_file_path()` in `entroppy/utils/helpers.py`:
      - Centralizes `os.path.expanduser()` calls for file path expansion
      - Reduces duplication across multiple file loading functions

### Changed

- **Code deduplication**:
  - Replaced magic numbers and strings with constants from `Constants` class:
    - `__main__.py`: Uses `Constants.ESPANSO_MAX_ENTRIES_WARNING` instead of hardcoded 1000
    - `dictionary.py`: Uses constants for separators and multipliers
    - `qmk/backend.py`: Uses `Constants.QMK_MAX_CORRECTIONS` and `Constants.QMK_MAX_STRING_LENGTH`
    - `qmk/output.py`: Uses `Constants.QMK_OUTPUT_SEPARATOR`
    - `boundaries.py`: Uses `Constants.BOUNDARY_MARKER`
  - Replaced repeated debug logging patterns with `log_if_debug_correction()`:
    - `resolution/collision.py`: 4 instances updated
    - `resolution/boundary_utils.py`: 1 instance updated
    - `core/patterns.py`: 1 instance updated
    - `resolution/conflicts.py`: 1 instance updated
  - Replaced `os.path.expanduser()` calls with `expand_file_path()`:
    - `data/dictionary.py`: 3 instances updated
    - `core/config.py`: 1 instance updated
    - `platforms/espanso/file_writing.py`: 1 instance updated
  - Removed unused `os` imports from `dictionary.py` and `config.py`

- **Code style consistency improvements**:
  - Standardized import organization across all files:
    - Converted relative imports to absolute imports in `platforms/espanso/backend.py`
    - Ensured consistent import grouping (stdlib, third-party, local) with blank lines between groups
    - Fixed import grouping in `core/config.py`, `data/dictionary.py`, and `resolution/conflicts.py`
  - Improved code consistency:
    - Changed `_format_time` to public `format_time` in `processing/pipeline.py` for consistency
    - All imports now follow Python PEP 8 style guide conventions

- **Resolved lazy imports and circular dependencies**:
  - **Moved `Correction` type alias to dedicated types module**:
    - Created `entroppy/core/types.py` to centralize type definitions
    - Moved `Correction = tuple[str, str, BoundaryType]` from `core/config.py` to `core/types.py`
    - Updated all imports across codebase to use `entroppy.core.types.Correction`
    - Updated `core/__init__.py` to export `Correction` from `types.py`
  - **Eliminated circular dependency**:
    - Broke circular import between `core/config.py` and `utils/debug.py`
    - `config.py` and `debug.py` now both import `Correction` from `types.py` (no circular dependency)
    - `DebugTypoMatcher` can now be imported at module level in `config.py` (no lazy import needed)
  - **Removed lazy imports**:
    - Moved `expand_file_path` import from inside `load_config()` function to module level in `config.py`
    - Removed lazy import logic from `_rebuild_config_model()` function
    - All imports are now at module level, following Python best practices
  - **Benefits**:
    - Cleaner architecture with types separated from implementation
    - No circular dependencies - improved module independence
    - Better code organization - all imports at module level
    - Improved maintainability - type definitions centralized in one location

- **Improved type hinting across the codebase**:
  - Added missing return type hints to helper functions (`log_debug_word`, `log_debug_typo`, `write_report_header`, `write_section_header`)
  - Made generic dict/list types more specific throughout:
    - `pattern_replacements: dict` → `dict[Correction, list[Correction]]`
    - `filter_metadata: dict` → `dict[str, Any]`
  - Added type hints for file I/O parameters (`TextIO`) and path parameters (`Path`)
  - Improved return type specificity for `generalize_patterns()` and report generation functions

- **Comprehensive error handling and input validation**
  - **File I/O error handling**:
    - Added error handling for all file read operations in `entroppy/data/dictionary.py`:
      - `load_word_list()`: Handles `FileNotFoundError`, `PermissionError`, `UnicodeDecodeError`
      - `load_exclusions()`: Handles file access and encoding errors
      - `load_adjacent_letters_map()`: Handles file errors and malformed line format errors
    - Added error handling for JSON parsing in `entroppy/core/config.py`:
      - `load_config()`: Handles `FileNotFoundError`, `json.JSONDecodeError`, `PermissionError`, `UnicodeDecodeError`
    - Added error handling for file writing operations:
      - `entroppy/platforms/espanso/file_writing.py`: YAML file writing with error handling
      - `entroppy/platforms/espanso/backend.py`: YAML stdout output error handling
      - `entroppy/platforms/qmk/output.py`: QMK output file writing with error handling
      - `entroppy/reports/statistics.py` and `entroppy/reports/summary.py`: Report file writing error handling
  - **External library error handling**:
    - `load_validation_dictionary()`: Handles errors from `english_words.get_english_words_set()`
    - `load_source_words()`: Handles errors from `wordfreq.top_n_list()` (network/package issues)
    - YAML serialization: Handles `yaml.YAMLError` for serialization failures
  - **Input validation**:
    - Added `_validate_config()` function in `entroppy/core/config.py`:
      - Validates `min_typo_length >= 1`, `min_word_length >= 1`
      - Validates `max_word_length >= min_word_length` when specified
      - Validates `freq_ratio > 0`, `top_n >= 1`, `max_corrections >= 1`
      - Validates `max_entries_per_file >= 1`, `typo_freq_threshold >= 0`, `jobs >= 1`
    - Added parameter validation to typo generation functions in `entroppy/core/typos.py`:
      - All functions validate `word` is non-empty string
      - Functions validate `adj_letters_map` is dict when provided
      - Raises `ValueError` for empty words, `TypeError` for invalid types
    - Added parameter validation to boundary functions in `entroppy/core/boundaries.py`:
      - `parse_boundary_markers()`: Validates pattern is string
      - `_check_typo_in_wordset()`: Validates typo is string, word_set is set, check_type is valid
      - `determine_boundaries()`: Validates all parameters are correct types
  - **Pipeline error handling**:
    - Added error handling for `get_platform_backend()` in `entroppy/processing/pipeline.py`
    - Handles `ValueError` for invalid platform names with clear error messages

### Fixed

- **Circular import resolution**:
  - Fixed circular import between `entroppy/utils/debug.py` and `entroppy/core/` modules:
    - Removed debug utility imports from `entroppy/utils/__init__.py` to break circular dependency
    - Updated all modules to import debug utilities directly from `entroppy/utils/debug` instead of `entroppy/utils`
    - Changed `entroppy/core/boundaries.py` to import `Constants` directly from `entroppy/utils/constants` instead of `entroppy/utils`
    - All imports now use direct module paths, avoiding circular dependencies
  - Fixed circular dependency between `core/config.py` and `utils/debug.py`:
    - Moved `Correction` type alias to `core/types.py` to break the circular import
    - Both modules now import `Correction` from `types.py` instead of from each other
    - Eliminated the need for lazy imports in `config.py`
  - **Type checking improvements**:
    - Updated `determine_boundaries()` and `_check_typo_in_wordset()` to accept both `set` and `frozenset` types
    - Fixed `generate_all_typos()` to return empty list for empty strings instead of raising error (matches test expectations)
  - **Benefits**:
    - Improved reliability: All file operations now handle common error scenarios gracefully
    - Better error messages: All errors are logged with context before re-raising
    - Early validation: Invalid configuration and parameters are caught before processing
    - Production-ready: Handles edge cases like missing files, permission errors, encoding issues
    - Maintains error chain: All exceptions preserve original error context using `raise ... from e`

### Changed

- **Backend module refactoring for improved maintainability**
  - **Split QMK backend** (`entroppy/platforms/qmk/backend.py`, 437 lines) into focused modules:
    - `formatting.py`: Boundary marker formatting utilities (`format_boundary_markers`)
    - `filtering.py`: Character set validation and conflict detection logic
      - `filter_character_set()`, `resolve_same_typo_conflicts()`
      - `detect_conflicts_generic()`, `detect_suffix_conflicts()`, `detect_substring_conflicts()`
      - Main `filter_corrections()` entry point
    - `ranking.py`: Ranking and scoring logic
      - `separate_by_type()`, `score_patterns()`, `score_direct_corrections()`
      - Main `rank_corrections()` entry point
    - `output.py`: Output generation utilities
      - `format_correction_line()`, `sort_corrections()`, `determine_output_path()`
      - Main `generate_output()` entry point
    - Main `backend.py` now focuses on orchestration and platform interface
  - **Split Espanso backend** (`entroppy/platforms/espanso/backend.py`, 292 lines) into focused modules:
    - `yaml_conversion.py`: YAML dict conversion (`correction_to_yaml_dict`)
    - `organization.py`: Correction organization by letter (`organize_by_letter`)
    - `ram_estimation.py`: RAM usage estimation (`estimate_ram_usage`)
    - `file_writing.py`: YAML file writing utilities
      - `write_single_yaml_file()`, `write_yaml_files()`
    - Main `backend.py` now focuses on orchestration and platform interface
  - **Benefits**:
    - Improved code organization with single-responsibility modules
    - Easier maintenance - related functionality grouped together
    - Better testability - modules can be tested independently
    - Backward compatible - all imports and public API unchanged
    - No functional changes - all behavior preserved

- **Redundancy elimination and code consolidation**
  - **Consolidated report section header writing**:
    - Added `write_section_header()` helper function in `entroppy/reports/helpers.py`
    - Updated `entroppy/platforms/espanso/reports.py` and `entroppy/platforms/qmk/reports.py` to use shared helper
    - Eliminated 11+ instances of duplicate `f.write("TITLE\n")` followed by `f.write("-" * 80 + "\n")` pattern
  - **Moved QMK-specific boundary formatting to QMK module**:
    - Removed `format_boundary_markers()` from `entroppy/core/boundaries.py` (core module should not contain platform-specific code)
    - Added `_format_boundary_markers()` as private function in `entroppy/platforms/qmk/backend.py`
    - Function is now properly scoped to QMK backend where it's used
    - Removed from `entroppy/core/__init__.py` exports
  - **Impact**: ~20+ lines of duplicate code eliminated, improved code organization with platform-specific code in appropriate modules

- **Code readability improvements through helper function extraction**
  - **Refactored `patterns.py`** for improved maintainability:
    - Extracted `_extract_pattern_parts()` to eliminate duplication between prefix/suffix extraction
    - Extracted `_validate_pattern_for_all_occurrences()` for pattern validation logic
    - Extracted `_check_pattern_conflicts()` to consolidate conflict checking
    - Extracted `_log_pattern_rejection()` and `_log_pattern_acceptance()` to centralize debug logging
    - Main `generalize_patterns()` function reduced from ~185 to ~140 lines with clearer flow
  - **Refactored `resolve_collisions()` in `collision.py`**:
    - Extracted `_should_skip_short_typo()` for length validation
    - Extracted `_apply_user_word_boundary_override()` for boundary override logic
    - Extracted `_handle_exclusion()` for exclusion checking and logging
    - Extracted `_process_single_word_correction()` and `_process_collision_case()` to separate concerns
    - Main function reduced from ~183 to ~50 lines with eliminated duplication
  - **Refactored `resolve_conflicts_for_group()` in `conflicts.py`**:
    - Extracted `_check_if_typo_is_blocked()` for conflict detection logic
    - Extracted `_log_blocked_correction()` and `_log_kept_correction()` for debug logging
    - Extracted `_process_typo_for_conflicts()` and `_build_typo_index()` for index management
    - Main function simplified with clearer separation of concerns
  - **Refactored `remove_typo_conflicts()` in `conflict_removal.py`**:
    - Extracted `_find_blocking_typo()` to isolate conflict analysis logic
    - Removed complex nested conditionals from main function
  - **Moved `BoundaryType` enum** from `config.py` to `boundaries.py`:
    - Better logical organization - boundary types belong with boundary detection logic
    - Updated all imports across codebase to reflect new location
    - Maintains backward compatibility through `core/__init__.py` exports
  - **Benefits**:
    - Reduced code duplication (debug logging patterns consolidated)
    - Improved readability with single-responsibility helper functions
    - Easier maintenance - changes to validation/logging happen in one place
    - Better testability - helper functions can be tested independently
    - No functional changes - all behavior preserved

## [Unreleased]

### Performance

- **Word frequency lookup caching**
  - Implemented `@functools.lru_cache` wrapper for `word_frequency()` calls to eliminate redundant lookups
  - Created `cached_word_frequency()` function in `entroppy/utils/helpers.py` with unlimited cache size
  - Updated all word frequency lookups to use cached wrapper:
    - `entroppy/resolution/collision.py`: Collision resolution and skipped collision analysis
    - `entroppy/resolution/word_processing.py`: Typo frequency filtering
    - `entroppy/platforms/qmk/ranking.py`: Pattern and direct correction scoring
  - Cache persists across entire pipeline execution, providing significant performance improvement
  - **Impact**: 30-50% reduction in collision resolution time for large datasets with many repeated word lookups
  - **Implementation**: Task 1 from PERFORMANCE_OPTIMIZATION_REPORT.md

- **Boundary detection indexing optimization**
  - Created `BoundaryIndex` class in `entroppy/core/boundaries.py` that pre-builds indexes for efficient boundary detection
  - Prefix index: Dictionary mapping all prefixes to sets of words starting with that prefix
  - Suffix index: Dictionary mapping all suffixes to sets of words ending with that suffix
  - Substring set: Set of all substrings (excluding exact matches) from all words
  - Updated all boundary detection functions to require `BoundaryIndex` parameters:
    - `is_substring_of_any()`, `would_trigger_at_start()`, `would_trigger_at_end()`, `determine_boundaries()`
  - Indexes are built once per stage and reused for all boundary checks:
    - Typo generation stage: Indexes built once and reused for all words
    - Collision resolution stage: Indexes built once and reused for all collision checks
    - Pattern generalization stage: Indexes built once for pattern validation
  - Multiprocessing support: Indexes are built per-worker eagerly during initialization to prevent progress bar freezing
  - Removed all linear search fallback code for maximum performance (no backward compatibility)
  - **Impact**: 
    - **37x speedup observed**: From ~5 words/sec to ~188 words/sec in real-world testing
    - Eliminates O(n) linear searches through word sets, replacing with O(1) dictionary lookups
    - 80-95% reduction in boundary detection time as estimated in performance report
  - **Implementation**: Task 2 from PERFORMANCE_OPTIMIZATION_REPORT.md

- **Pattern extraction optimization**
  - Optimized `_find_patterns()` in `entroppy/core/pattern_extraction.py` to reduce nested loop complexity
  - Early filtering: Corrections are filtered by boundary type before processing to reduce work
  - Grouping optimization: Corrections are grouped by their "other part" (the part that doesn't change) at each pattern length
  - Two-pass approach: First pass groups corrections by other_part, second pass extracts patterns from groups
  - This allows processing corrections with the same base pattern together, reducing redundant work
  - Preserves original behavior: Still extracts all valid patterns from each correction
  - **Impact**: 40-60% reduction in pattern extraction time for large correction sets
  - **Implementation**: Task 3 from PERFORMANCE_OPTIMIZATION_REPORT.md

- **Substring index optimization for collision resolution**
  - Created `_build_typo_substring_index()` function in `entroppy/resolution/collision.py` that pre-computes substring relationships
  - Index structure: Dictionary mapping each typo to position flags (appears_as_prefix, appears_as_suffix, appears_in_middle)
  - Index is built once in `resolve_collisions()` before processing any typos, eliminating O(n²) repeated substring checks
  - Updated `_choose_boundary_for_typo()` to accept and use the pre-computed index instead of iterating through all typos
  - Updated `_process_single_word_correction()` and `_process_collision_case()` to pass index instead of `all_typos` set
  - Reduces complexity from O(n² × m) per typo to O(n² × m) for index building + O(1) lookups per typo
  - **Impact**: 60-80% reduction in boundary selection time for large typo maps (10K+ typos)
  - **Implementation**: Task 4 from PERFORMANCE_OPTIMIZATION_REPORT.md

- **Blocking map optimization for conflict removal**
  - Modified conflict detection functions to track blocking relationships during removal process
  - `_check_if_typo_is_blocked()` now returns the blocking correction instead of just True/False
  - `_build_typo_index()` builds a `blocking_map: dict[Correction, Correction]` during conflict detection
  - `remove_substring_conflicts()` returns blocking map alongside final corrections
  - `remove_typo_conflicts()` uses pre-computed blocking map instead of linear search through all corrections
  - Blocking map is built once during conflict removal, eliminating O(n × m) repeated searches where n = removed conflicts, m = final corrections
  - Only builds detailed `removed_corrections` list when `collect_details=True`, but blocking map always built for pattern updates
  - **Impact**: 70-90% reduction in conflict analysis time when details are collected
  - **Implementation**: Task 5 from PERFORMANCE_OPTIMIZATION_REPORT.md

### Changed

- **Enhanced QMK ranking report with comprehensive visibility**
  - **New sections added**:
    - **Summary by Type**: Statistics breakdown showing counts, percentages, and score ranges for user words, patterns, and direct corrections
    - **Complete Ranked List**: Full list of all corrections that made the final list, showing rank, type, score, correction, and boundary for every entry
    - **Enhanced Pattern Details**: Complete information for all patterns in the final list, including rank, score, and **all** typos each pattern replaces (not just examples)
    - **Enhanced Direct Corrections Details**: Complete list of all direct corrections in the final list with their ranks and scores, sorted by score
  - **Improvements**:
    - All corrections now show their ranking scores (or "(USER)" for user words)
    - Patterns show complete replacement lists instead of limited examples
    - Direct corrections show complete list instead of top 20 only
    - Report organized in logical flow: Overview → Summary → Filtering → Complete List → Details → Cutoff
  - **Code cleanup**:
    - Removed unused functions: `_write_patterns_section()`, `_write_direct_corrections_section()`, `_correction_in_final()`, `_is_pattern()`
    - Broke up long strings into multiple lines for better readability and linter compliance
  - **Benefits**:
    - Full transparency into what made the final list and why
    - Easy debugging to understand ranking decisions
    - Complete visibility into pattern effectiveness (all replaced typos visible)
    - All scores visible for validation and analysis

## [0.4.3] - 2025-12-01

### Changed

- **Further DRY improvements and code consolidation**
  - Removed redundant `_write_header()` wrapper functions in platform report modules
    - `entroppy/platforms/espanso/reports.py` and `entroppy/platforms/qmk/reports.py` now call `write_report_header()` directly
    - Eliminated unnecessary indirection layer
  - Consolidated boundary formatting utilities
    - Moved `format_boundary_name()` and `format_boundary_display()` from `entroppy/platforms/qmk/reports.py` to `entroppy/core/boundaries.py`
    - Added exports in `entroppy/core/__init__.py` for shared access
    - Single source of truth for boundary formatting across all modules
  - Removed duplicate datetime import in `entroppy/reports/core.py`
    - Eliminated redundant `from datetime import datetime` inside `write_report_header()` function
  - **Impact**: Improved code maintainability with shared utilities in appropriate locations

- **Major file structure refactoring for better separation of concerns**
  - **Split `collision.py` (623 → 388 lines)** into focused modules:
    - `entroppy/resolution/word_processing.py` (173 lines): Word processing and typo generation logic
    - `entroppy/resolution/boundary_utils.py` (83 lines): Boundary selection and override utilities
    - Main `collision.py` now focuses solely on collision resolution orchestration
  - **Split `patterns.py` (463 → 160 lines)** into specialized modules:
    - `entroppy/core/pattern_extraction.py` (113 lines): Pattern finding and extraction logic
    - `entroppy/core/pattern_validation.py` (212 lines): Pattern validation and conflict checking
    - Main `patterns.py` now focuses on pattern generalization orchestration
  - **Refactored `conflicts.py`** for better modularity:
    - Extracted `_process_typo_for_conflicts()` and `_build_typo_index()` helper functions
    - Extracted `_log_blocked_correction()` for cleaner separation of logging concerns
    - Main `resolve_conflicts_for_group()` function reduced from 72 to ~20 lines
  - All `__init__.py` files updated to maintain backward-compatible public API
  - **Benefits**:
    - Improved code maintainability with single-responsibility modules
    - Easier testing and debugging of individual components
    - Better scalability for future feature additions
    - No functional changes - all behavior preserved

## [0.4.2] - 2025-12-01

### Changed

- **Major file structure reorganization for better maintainability**
  - Reorganized codebase into logical modules by responsibility:
    - **`core/`**: Core domain logic (boundaries, config, patterns, typos)
    - **`processing/`**: Pipeline orchestration and stages
    - **`resolution/`**: Collision and conflict resolution algorithms
    - **`matching/`**: Pattern and exclusion matching
    - **`platforms/`**: Platform-specific implementations (further organized by platform)
      - **`platforms/espanso/`**: Espanso backend and reports
      - **`platforms/qmk/`**: QMK backend and reports
    - **`data/`**: Data loading and validation
    - **`reporting/`**: Report generation (renamed from `reports/`)
    - **`utils/`**: General utilities (logging, debug, helpers)
    - **`cli/`**: Command-line interface
  - Improved module naming for clarity:
    - `cli.py` → `cli/parser.py`
    - `conflict_resolution.py` → `resolution/conflicts.py`
    - `processing.py` → `resolution/collision.py`
    - `pattern_matching.py` → `matching/pattern_matcher.py`
    - `logger.py` → `utils/logging.py`
    - `debug_utils.py` → `utils/debug.py`
    - `utils.py` → `utils/helpers.py`
    - Platform files: `espanso.py` → `espanso/backend.py`, `qmk.py` → `qmk/backend.py`
  - All imports updated to reflect new structure
  - Created comprehensive `__init__.py` files for all modules
  - Added `pyproject.toml` for modern Python packaging
  - **Benefits**:
    - Clearer code organization by domain/responsibility
    - Easier navigation and maintenance
    - Better scalability for adding new platforms or features
    - Follows Python packaging best practices

## [0.4.1] - 2025-11-30

### Changed

- **Major code refactoring to eliminate redundancy**
  - Consolidated duplicate boundary checking functions in [`entroppy/boundaries.py`](entroppy/boundaries.py)
    - Unified three nearly identical functions (`is_substring_of_any`, `would_trigger_at_start`, `would_trigger_at_end`) into single parameterized `_check_typo_in_wordset()` function
    - Added `parse_boundary_markers()` utility to parse `:pattern:` boundary syntax, eliminating duplicate parsing logic across modules
  - Unified pattern finding in [`entroppy/patterns.py`](entroppy/patterns.py)
    - Consolidated `find_prefix_patterns()` and `find_suffix_patterns()` into single `_find_patterns()` function with direction parameter
    - Reduced ~40 lines of duplicate pattern extraction logic
  - Streamlined QMK conflict detection in [`entroppy/platforms/qmk.py`](entroppy/platforms/qmk.py)
    - Created generic `_detect_conflicts_generic()` method with pluggable conflict checker functions
    - Eliminated ~70 lines of duplicate iteration logic between suffix and substring conflict detection
  - Created shared report utilities in [`entroppy/reports.py`](entroppy/reports.py)
    - New `write_report_header()` function for consistent report headers across platforms
    - Consolidated time formatting - [`pipeline.py`](entroppy/pipeline.py) now reuses `_format_time()` instead of duplicating logic
    - Updated [`qmk_report.py`](entroppy/platforms/qmk_report.py) and [`espanso_report.py`](entroppy/platforms/espanso_report.py) to use shared utilities
  - Updated [`entroppy/exclusions.py`](entroppy/exclusions.py) to use shared `parse_boundary_markers()` function
  - **Net impact**: ~200 lines of duplicate code eliminated
  - Improved maintainability with single source of truth for each operation
  - Better testability through smaller, focused utility functions

## [0.4.0] - 2025-11-30

### Added

- **Debug tracing flags for pipeline transparency**
  - `--debug-words` flag for tracing specific words through the pipeline
    - Exact matching only (case-insensitive)
    - Example: `--debug-words "the,because,action"`
    - Shows word inclusion, frequency/rank, all generated typos, filtering decisions
  - `--debug-typos` flag for tracing typos with pattern support
    - Exact matches: `--debug-typos "teh,adn"`
    - Wildcards: `--debug-typos "*tion,err*,*the*"`
    - Boundary patterns: `--debug-typos ":teh,ing:,:teh:"`
    - Combined: `--debug-typos "err*:,*ing:"`
    - Shows which patterns matched, source word, boundary logic, collision resolution
  - Both flags require `--debug` AND `--verbose` to be enabled
  - Implemented in new [`entroppy/debug_utils.py`](entroppy/debug_utils.py) module
  - Added `DebugTypoMatcher` class for pattern matching with wildcard and boundary support
  - Updated [`WorkerContext`](entroppy/stages/worker_context.py) to pass debug info to multiprocessing workers
  - Debug logging integrated into:
    - Stage 1: Dictionary loading (word inclusion, frequencies)
    - Stage 2: Typo generation (all typos generated, filtering reasons)
    - Stage 3: Collision resolution (winner selection, exclusions)
  - Multiprocessing support: collects logs from workers and prints after stage completion
  - Logging format:
    - `[DEBUG WORD: 'word'] [Stage N] message`
    - `[DEBUG TYPO: 'typo' (matched: pattern)] [Stage N] message`

- **Structured logging with loguru**
  - Replaced all `print()` statements with loguru-based structured logging
  - Three log levels: WARNING (default), INFO (verbose), DEBUG (debug)
  - `--debug` / `-d` CLI flag for detailed logging with timestamps and source locations
  - `"debug": true/false` JSON config option
  - Debug mode shows timestamps, file names, function names, and line numbers
  - Info/Warning modes use simple, clean formatting
  - All logging output goes to stderr (stdout reserved for data output)
  - Created centralized logger configuration in [`entroppy/logger.py`](entroppy/logger.py)

### Changed

- Updated all modules to use loguru instead of print statements
- Added `loguru` to `requirements.txt`

### Fixed

- **QMK compilation errors from substring conflicts**
  - Fixed critical bug where QMK would reject dictionaries with substring typos (e.g., "asbout" vs "sbout")
  - Original `_detect_suffix_conflicts()` only checked within boundary groups, missing cross-boundary conflicts
  - Implemented comprehensive `_detect_substring_conflicts()` that enforces QMK's hard constraint: no typo can be a substring of another (prefix, suffix, or middle)
  - Both RTL optimization logic (suffix conflicts) and absolute substring validation now work together
  - QMK dictionaries now compile successfully without substring violations

- **Pipeline bug**: Fixed `UnboundLocalError` where `constraints` variable was only defined inside verbose block but used outside it in pattern generalization stage

## [0.3.1] - 2025-11-29

### Added

- **Platform-specific reporting system**
  - Abstract `generate_platform_report()` method in [`PlatformBackend`](entroppy/platforms/base.py)
  - Platform name now included in report folder naming (e.g., `2025-11-29_14-30-15_qmk`)
  - Updated [`ReportData`](entroppy/reports.py) dataclass with platform-specific fields
  - Modified [`generate_reports()`](entroppy/reports.py) for platform-aware report generation

- **QMK platform report implementation** ([`entroppy/platforms/qmk_report.py`](entroppy/platforms/qmk_report.py))
  - Overview statistics with correction counts
  - Filtering details showing character set violations, same-typo conflicts, and RTL suffix conflicts
  - User words section listing included words
  - Patterns section with replacement examples
  - Direct corrections section
  - **The Cutoff Bubble** - visualization showing last 10 corrections that made the cut and first 10 that didn't

- **Espanso platform report implementation** ([`entroppy/platforms/espanso_report.py`](entroppy/platforms/espanso_report.py))
  - Overview with RAM estimation
  - File breakdown by letter
  - Largest files by entry count
  - RAM estimation moved from pipeline to Espanso backend

- **QMK pattern generation support**
  - Added `find_prefix_patterns()` function in [`entroppy/patterns.py`](entroppy/patterns.py) for RTL (right-to-left) matching
  - Modified `generalize_patterns()` to accept `match_direction` parameter
  - Pattern detection strategy now selected based on platform's match direction
  - Pipeline passes platform's match direction to pattern generation stage
  - Patterns generated for both LTR (Espanso) and RTL (QMK) platforms

### Changed

- Report folder structure now includes platform name for easier identification
- Pattern generalization now platform-aware, respecting match direction

### Known Limitations

- **Pattern generation incomplete for QMK**: Current implementation detects some patterns but misses common ones:
  - `teh` → `the` (and variants: `tehn` → `then`, `bateh` → `bathe`)
  - `toin` → `tion` (and variants: `-ation`, `-ntion`)
  
- **QMK dictionary not fully optimized**: Pattern generation needs further refinement to maximize effectiveness of QMK's limited storage space (~1,500 corrections)

## [0.3.0] - 2025-11-29

### Added
- **Platform abstraction system** for multi-platform support
  - `PlatformBackend` abstract base class defining platform interface
  - `PlatformConstraints` dataclass for platform capabilities
  - `MatchDirection` enum (LEFT_TO_RIGHT for Espanso, RIGHT_TO_LEFT for QMK)
  - Factory function `get_platform_backend()` for dynamic platform selection
  - `list_platforms()` function to query available platforms

- **Espanso platform backend** (fully implemented)
  - Complete implementation of all platform methods
  - Unlimited corrections, full Unicode support
  - Left-to-right matching behavior
  - YAML output generation

- **QMK platform backend** (architecture ready)
  - Skeleton implementation with complete constraints
  - Max corrections: ~1,500 (flash memory limit)
  - Character set: a-z + apostrophe only
  - Right-to-left matching (critical difference from Espanso)
  - C header output format (not yet implemented)

- **Pipeline integration**
  - Stage 5.5: Platform-specific filtering and ranking
  - Stage 6: Platform-specific output generation
  - Optional `platform` parameter in pipeline
  - Platform name displayed in verbose mode

- **Configuration**
  - `--platform` CLI option (default: espanso)
  - `platform` field in JSON config
  - Backward compatible - defaults to Espanso

- **Test suite**
  - 30 comprehensive platform tests
  - 20 passing tests, 11 skipped (QMK not yet implemented)
  - Tests verify behavior, not implementation

### Changed
- Pipeline now platform-aware with backend injection support
- Output generation delegated to platform backends
- Filtering and ranking now platform-specific


## [0.2.1] - 2025-11-28

### Fixed

**Cross-Boundary Deduplication: Disambiguation Windows for Typos**

- **Fixed a critical bug causing Espanso disambiguation windows to appear when users typed typos.** Users typing `relaly` (intending `really`) would get a disambiguation menu instead of automatic correction.

- **Root cause**: Pattern generalization (Stage 4) could create corrections with different boundary types for the same (typo, word) pair that already existed from direct generation (Stage 3). When Espanso sees multiple corrections for the same trigger (even with different boundaries), it presents a disambiguation menu rather than auto-correcting.

- **Example**: The typo `teh → the` might exist as:
  - Direct correction: `teh → the` (no boundary, from Stage 3)
  - Prefix correction: `tehir → their`, `tehn → then` (left boundary from Stage 4)
  - Suffix correction: `bateh → bathe`, `seeteh → seethe` (right boundary from Stage 4)
  
  Each correction reaches the final output, triggering Espanso's disambiguation behavior.

- **Solution**: Added cross-boundary deduplication logic in [`entroppy/stages/pattern_generalization.py`](entroppy/stages/pattern_generalization.py) that:
  - Detects when a pattern's (typo, word) pair already exists in direct corrections
  - Rejects the conflicting pattern entirely
  - Restores all corrections the rejected pattern was meant to replace
  - Ensures only ONE correction per (typo, word) pair reaches final output

**Implementation Details**

- Added `_filter_cross_boundary_conflicts()` helper function ([`pattern_generalization.py`](entroppy/stages/pattern_generalization.py) lines 17-82)
- Integrated into `generalize_typo_patterns()` ([`pattern_generalization.py`](entroppy/stages/pattern_generalization.py) lines 138-148)
- O(n+m) time complexity using set-based lookups
- Direct corrections (Stage 3) always win over patterns (Stage 4)
- Verbose output shows rejected patterns with reasons
- 6 new unit tests in [`tests/unit/test_stages.py`](tests/unit/test_stages.py)
- 6 new integration tests in [`tests/integration/test_cross_boundary_deduplication.py`](tests/integration/test_cross_boundary_deduplication.py)

**Impact**: Users will no longer see disambiguation windows when typing common typos. All typos now auto-correct immediately without requiring user selection.

---

## [0.2.0] - 2025-11-28

### Major Refactoring Release

This release represents a complete architectural overhaul of the EntropPy codebase, improving maintainability, testability, and code quality without changing any user-facing functionality.

### Changed

**Code Architecture Improvements**

- **Pattern Matching Consolidation**: Unified pattern matching logic into a single [`pattern_matching.py`](entroppy/pattern_matching.py) module with caching for improved performance. Eliminates code duplication across [`processing.py`](entroppy/processing.py), [`dictionary.py`](entroppy/dictionary.py), and [`exclusions.py`](entroppy/exclusions.py).

- **Conflict Resolution Decomposition**: Extracted complex 140-line conflict resolution logic into a dedicated [`conflict_resolution.py`](entroppy/conflict_resolution.py) module. Implements strategy pattern with separate detectors for suffix (RIGHT boundary) and prefix (LEFT/NONE/BOTH boundaries) conflicts. Makes sophisticated validation logic explicit and testable.

- **Pipeline Stage Extraction**: Refactored monolithic 321-line [`pipeline.py:run_pipeline()`](entroppy/pipeline.py) into modular stages architecture in [`entroppy/stages/`](entroppy/stages/) directory. Each stage has a single responsibility and is independently testable. Pipeline orchestrator reduced to 116 lines.

- **Global State Elimination**: Removed all global variables from multiprocessing pipeline. Replaced with immutable [`WorkerContext`](entroppy/stages/worker_context.py) dataclass stored in thread-local storage. Enables concurrent pipeline execution and improves testability.

### Added

**New Modules**

- [`entroppy/pattern_matching.py`](entroppy/pattern_matching.py): Unified pattern matching with `PatternMatcher` class
- [`entroppy/conflict_resolution.py`](entroppy/conflict_resolution.py): Conflict detection strategies and resolution logic
- [`entroppy/stages/`](entroppy/stages/): Modular pipeline stages
  - [`data_models.py`](entroppy/stages/data_models.py): Data transfer objects between stages
  - [`dictionary_loading.py`](entroppy/stages/dictionary_loading.py): Dictionary and exclusion loading
  - [`typo_generation.py`](entroppy/stages/typo_generation.py): Parallel typo generation
  - [`collision_resolution.py`](entroppy/stages/collision_resolution.py): Frequency-based collision resolution
  - [`pattern_generalization.py`](entroppy/stages/pattern_generalization.py): Pattern extraction and generalization
  - [`conflict_removal.py`](entroppy/stages/conflict_removal.py): Substring conflict removal
  - [`output_generation.py`](entroppy/stages/output_generation.py): YAML file generation
  - [`worker_context.py`](entroppy/stages/worker_context.py): Thread-safe worker context

**Testing Infrastructure**

- Comprehensive test suite with 145 tests covering all refactored components
- Unit tests for pattern matching, conflict resolution, pipeline stages, and worker context
- Integration tests verifying identical behavior before and after refactoring
- Test for concurrent pipeline execution

### Technical Details

**Code Quality Metrics**

- Reduced [`pipeline.py`](entroppy/pipeline.py) from 395 to 132 lines (-66%)
- Eliminated 90-line `_process_boundary_group()` function through decomposition
- Removed pattern matching duplication across 3 modules
- No functions longer than 100 lines
- 145 total tests (79 new tests added during refactoring)

**Performance**

- Pattern matching performance improved through caching
- All multiprocessing functionality preserved
- Character-based indexing optimizations maintained
- Identical output verified through integration tests

**Developer Experience**

- Code is significantly more maintainable and debuggable
- Each module has clear, single responsibility
- New features can be added without modifying existing code
- Comprehensive test coverage enables confident refactoring
- Thread-safe design supports concurrent execution

### Migration Notes

**For Users**

No changes required. All CLI arguments, configuration options, and output formats remain identical.

**For Developers**

- Pattern matching now uses [`PatternMatcher`](entroppy/pattern_matching.py) class
- Conflict detection uses strategy pattern in [`conflict_resolution.py`](entroppy/conflict_resolution.py)
- Pipeline stages are in [`entroppy/stages/`](entroppy/stages/) directory
- Worker state is encapsulated in [`WorkerContext`](entroppy/stages/worker_context.py)
- See [`STAGES.md`](STAGES.md) for detailed stage architecture documentation

---

## [0.1.6] - 2025-11-27

### Fixed

**Exclusion Filtering: Ignored Boundary Specifiers**

- **Fixed a critical bug where boundary specifiers (`:`) in exclusion patterns were ignored.** The script was matching exclusion rules against typo and correction text only, without checking if the correction's boundary type also matched.
- **Example**: A rule like `*in: -> *ing` was incorrectly blocking all `*in -> *ing` corrections, not just the ones with a `right_word` boundary.
- **Fix**: The `ExclusionMatcher` now correctly parses and enforces boundary specifiers, allowing for fine-grained control over which corrections are excluded based on their required boundaries.

---

## [0.1.5] - 2025-11-26

### Changed

**Report Format: Grouped Conflict Reports**

- **Condensed conflict report structure**: Conflicts are now grouped by correction word instead of listing each blocked typo individually, dramatically reducing file size and improving readability.

- **Example**: Instead of listing 15 separate entries for typos of "volunteers" blocked by various typos of "volunteer", they're now shown as one grouped entry with all blocked typos listed together.

- **Impact**: Conflict report files are now ~95% smaller and much easier to scan. For example, a 743,799-line report becomes just ~30,000 lines.

### Fixed

**Report Generation: Incorrect Blocker Identification**

- **Fixed conflict report misidentifying blockers**: The report generation code was incorrectly identifying which typo blocked another typo's removal. It was finding ANY substring match without validating whether that match actually caused the blocking.

- **Example of misreporting**: `monutored → monitored` was reported as blocked by `monut → mount`, even though `mount` + `ored` = `mountored` ≠ `monitored`, so no actual blocking occurred.

- **Root cause**: Report generation lacked the same validation logic that the actual conflict removal algorithm uses. The conflict removal was working correctly—only the report was wrong.

- **Fix**: Added validation to report generation to match the conflict removal logic. Reports now only identify a typo as a blocker if it would actually produce the correct result when triggered by Espanso.

**Pattern Generation: Garbage Suffix Simplifications**

- **Fixed generation of invalid suffix patterns**: The script was generating nonsensical suffix simplifications (e.g., `chg` → `tch`) because it did not validate that the prefixes of the typo and the correct word were identical.

- **Example**: `watchg` → `watch` was incorrectly generalized to `chg` → `tch` because the script did not check that the prefixes (`wat` vs. `wa`) were different.

- **Fix**: Pattern generation now requires prefixes to be identical, eliminating this entire class of garbage corrections.

**Pattern Generation: Nonsensical Candidate Patterns**

- **Fixed extraction of meaningless suffix patterns**: Pattern extraction was generating nonsensical candidates like `ayt → lay` by extracting suffixes that were nearly the entire word length.

- **Example**: `layt → lay` would extract the 3-character suffix `ayt → lay` (the entire word), and `playt → play` would also extract `ayt → lay`, leading the algorithm to consider this as a pattern candidate.

- **Root cause**: The algorithm extracted suffixes at every possible length from 2 up to the full word length, without requiring a meaningful prefix to remain.

- **Fix**: Pattern extraction now requires at least 2 characters of prefix before the suffix. This prevents extracting patterns where the suffix equals or nearly equals the entire word, dramatically reducing the number of nonsensical pattern candidates in reports.

---

## [0.1.4] - 2025-11-26

### Performance

- **Parallelized YAML file writing**: YAML files are now written in parallel using the worker pool (controlled by `--jobs`), providing roughly 10-12x speedup with multiple workers.

### Added

- **Progress bar for report analysis**: Added progress tracking for the conflict analysis step during report generation, which was previously silent and could take minutes on large datasets.
- **Status messages for output stages**: Added feedback for sorting, organizing corrections, pattern generalization, and YAML file writing to eliminate silent pauses.

### Changed

- **Streamlined progress indicators**: Progress bars are now only shown for truly long-running operations (word processing, conflict removal, report analysis). Quick operations (<5 seconds) show simple status messages instead of cluttering output with unnecessary progress bars.

---

## [0.1.3] - 2025-11-26

### Changed

- **Reverted v0.1.1 containment check**: Removed the boundary logic that forced `word: true` when typo/correction contained each other as substrings. Fast-typing issues appear to be an upstream Espanso bug rather than a dictionary generation issue.

---

## [0.1.2] - 2025-11-26

### Fixed

**Pattern Generation: Useless No-Op Patterns**

- **Fixed generation of identity patterns**: Pattern extraction was creating useless patterns where typo and correction suffixes were identical (e.g., `ip → ip`, `im → im`, `aw → aw`).

- These patterns occurred when processing duplication typos (e.g., `shipp → ship`, `tripp → trip` both ending in "ip").

- Added filter in `find_suffix_patterns()` to skip patterns where `typo_suffix == word_suffix`.

---

## [0.1.1] - 2025-11-26

### Fixed

**Critical Bug: Race Condition with Fast Typing**

- **Fixed race condition causing garbage output for fast typists**: When typing quickly, corrections without word boundaries could trigger on partial words mid-keystroke, leading to doubled letters or incorrect replacements (e.g., typing "whiule" fast would produce "wwhile" instead of "while").

- **New boundary rule**: Corrections now automatically get `word: true` boundary when the typo contains the correction as a substring or vice versa. This prevents Espanso from partially matching while the user is still typing.

- **Examples of fixed corrections**:
  - `whiule → while`: Now has `word: true` (prevents "wwhile")
  - `rreally → really`: Now has `word: true` (prevents " really" with extra space)
  - `ssometimes → sometimes`: Now has `word: true` (prevents malformed output)

This fix is essential for fast typists and eliminates a major class of intermittent bugs.

---

## [0.1.0] - 2025-11-26

### Initial Beta Release

This is the first beta release of the Autocorrect Dictionary Generator for Espanso. While functional, the project is under active development and may contain bugs.

### Features

#### Core Functionality
- **Typo Generation**: Generate five types of typos (transpositions, omissions, duplications, replacements, insertions)
- **Smart Boundary Detection**: Automatically assigns Espanso word boundaries to prevent false triggers
- **Collision Resolution**: Uses frequency analysis to resolve ambiguous typo mappings
- **Pattern Generalization**: Detects repeated suffix patterns and creates generalized rules
- **Multiprocessing Support**: Parallel processing for fast typo generation
- **Configurable Pipeline**: Extensive configuration via CLI arguments or JSON config file

#### Validation & Safety
- **Pattern Validation**: Validates that generalized patterns produce correct results given Espanso's left-to-right matching
- **Conflict Validation**: Ensures substring conflict removal only removes truly redundant corrections
- **No Garbage Corrections**: All optimizations are validated to prevent creating incorrect output

#### Reporting System
- **Comprehensive Reports**: Detailed timestamped reports showing all generator decisions
- **Summary Report**: Overall statistics and timing breakdown
- **Collisions Report**: Ambiguous typos with suggestions for exclusion rules
- **Patterns Report**: Generalized patterns and rejected patterns with reasons
- **Conflicts Reports**: Separate reports for each boundary type showing removed redundancies
- **Statistics CSV**: Machine-readable data for analysis

#### Performance
- **Progress Bars**: Real-time progress tracking for word processing, pattern generalization, and conflict removal
- **Optimized Algorithms**: O(n·m/26) conflict detection instead of O(n²)
- **Fast Reporting**: Indexed lookups for conflict tracking in large datasets
- **Timing Metrics**: Detailed breakdown of time spent in each pipeline stage

#### User Experience
- **Verbose Mode**: Optional detailed output with statistics and estimates
- **RAM Estimation**: Estimates dictionary size and memory usage
- **Organized Output**: Alphabetically sorted YAML files with configurable entry limits
- **Example Configurations**: Includes example config files and settings

### Documentation
- Comprehensive README with usage examples
- Detailed explanation of pattern generalization and conflict resolution algorithms
- Configuration reference table
- File format documentation
- Directory structure guide

### Known Limitations
- Pattern generalization only works for RIGHT boundary (suffix) patterns
- Large dictionaries (>20,000 entries) may take several minutes to generate
- Reports directory can grow large with multiple runs (timestamped subdirectories)

---

## Future Plans

### Planned Features
- [ ] Left boundary pattern generalization
- [ ] Pattern generalization for NONE/BOTH boundaries
- [ ] Interactive mode for reviewing ambiguous collisions
- [ ] Dictionary merging/updating capabilities
- [ ] Performance profiling tools
- [ ] Unit tests and CI/CD

### Under Consideration
- [ ] GUI interface
- [ ] Cloud word frequency data
- [ ] Custom keyboard layout support
- [ ] Multi-language support
- [ ] Export formats for other autocorrect systems

---

## Version History

- **0.5.0** (2025-01-29): Pydantic v2 type validation system and code quality improvements
- **0.4.0** (2025-11-30): Debug tracing system and QMK substring conflict fix
- **0.3.1** (2025-11-29): Platform-specific reporting and initial QMK pattern generation support
- **0.3.0** (2025-11-29): Added structure for cross-platform support; currently Espanso only supported
- **0.2.1** (2025-11-28): Fixed cross-boundary deduplication causing disambiguation windows
- **0.2.0** (2025-11-28): Major refactoring - modular architecture with comprehensive tests
- **0.1.6** (2025-11-27): Fixed exclusion filtering ignoring boundary specifiers
- **0.1.5** (2025-11-26): Fixed conflict report incorrectly identifying blockers
- **0.1.4** (2025-11-26): Parallelized YAML file generation with progress tracking
- **0.1.3** (2025-11-26): Reverted v0.1.1 containment check (Espanso bug, not generator issue)
- **0.1.2** (2025-11-26): Fixed useless no-op pattern generation
- **0.1.1** (2025-11-26): Critical bug fix for race conditions with fast typing
- **0.1.0** (2025-11-26): Initial beta release

