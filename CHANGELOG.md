# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## Unreleased

## [0.9.0] - 2025-12-08

### Added

- **PatternType enum for type-safe pattern classification**: Added `PatternType` enum (`PREFIX`, `SUFFIX`, `SUBSTRING`) to replace string-based pattern type classification, improving type safety and code clarity throughout the pattern validation system.

- **Pre-commit hook for single assertion per test**: Added `check-single-assertion` pre-commit hook that verifies each test function has at most one assertion, enforcing the one-assertion-per-test best practice.

- **Comprehensive test coverage improvements**: Added integration tests for exclusion patterns, platform substring conflicts, pattern boundary assignment, pattern generalization regression, and solver debug logging. Expanded unit tests for iterative solver, conflict resolution, false trigger checking, pattern extraction, stages, and word processing.

### Changed

- **Enhanced debug typo and word reports**: Completely rewrote debug typo and word report generation to be far more comprehensive and organized by iteration first, then by pass/stage. Reports now include:
  - Full pattern extraction details with all occurrences
  - Complete pattern validation information (acceptances and rejections with detailed reasons)
  - Platform conflict checks (boundary comparisons and false trigger checks)
  - Ranking information (scores, positions, tiers)
  - Organized by iteration, showing the complete lifecycle of each typo/word through the solver
  - All messages mentioning the typo/word are now extracted and displayed, not just [DEBUG TYPO/WORD:] messages

- **Debug logging infrastructure refactoring**: Refactored debug word and typo logging to use centralized message collection infrastructure instead of direct logger calls. Stage 1 (dictionary loading) and Stage 3+ (solver) debug messages are now collected into `debug_messages` lists and merged with Stage 2 messages for comprehensive debug reports. All logging functions (`log_debug_word`, `log_debug_typo`, etc.) now accept an optional `debug_messages` parameter to collect messages for reports while still logging directly for immediate visibility. This ensures debug messages from all stages appear in the generated debug reports.

- **Substring conflict detection now finds conflicts in both directions**: `find_conflicts` (formerly `find_substring_conflicts`) now detects conflicts bidirectionally: it finds both typos that contain the query string (superstring conflicts) and typos that are substrings of the query string (substring conflicts). Previously, it only detected superstring conflicts, causing unresolved conflicts in QMK output where boundary markers create substring relationships (e.g., both `aemr` and `:aemr` were preserved, causing QMK compilation errors). The Rust implementation was refactored into smaller helper functions (`find_superstring_conflicts`, `find_contained_typos`, `position_to_typo_index`, `deduplicate_and_filter_self`) for better maintainability.

### Fixed

- **Multiprocessing pickling error in ConflictRemovalPass**: Fixed `AttributeError` when using parallel processing in ConflictRemovalPass on macOS. The worker function `process_conflict_batch_worker` was imported from a helper module, causing pickling issues with multiprocessing's spawn method. Added a module-level wrapper function to ensure proper serialization.

- **Pattern extraction no longer inherits boundaries from corrections**: Patterns are now extracted with `NONE` boundary instead of inheriting the correction's boundary (e.g., `BOTH`). This allows the solver to independently determine appropriate boundaries for patterns during validation, preventing invalid `BOTH` boundary patterns from being created and incorrectly blocking other corrections.

- **Pattern validation now tries appropriate boundaries**: When pattern validation fails with `NONE` boundary, the solver now automatically tries stricter boundaries based on pattern type: prefix patterns try `LEFT` boundary, suffix patterns try `RIGHT` boundary. Patterns never use `BOTH` boundary, and true substrings (patterns in the middle of words) are rejected if `NONE` fails.

- **Pattern extraction now includes BOTH boundary corrections**: Fixed bug where corrections with BOTH boundary were excluded from suffix and prefix pattern extraction. Since BOTH includes both LEFT and RIGHT boundaries, these corrections can contribute to both prefix and suffix patterns. This fix allows patterns like "thre" → "the" to be found from corrections like "whethre" → "whether" and "bathre" → "bathe" that have BOTH boundary.

- **Pattern validation performance**: Added pre-validation filter to skip patterns shorter than `min_typo_length` before sending them to validation, avoiding unnecessary validation work for patterns that will definitely be rejected.

- **Stage 6 debug logging now appears**: Fixed missing debug logging in PlatformConstraintsPass (Stage 6). The pass now logs debug messages for both words and typos when they pass or fail platform constraint checks, matching the behavior of other stages.

- **Slow test now properly marked**: Added `@pytest.mark.slow` to `test_qmk_solver_contains_patterns` in `test_pattern_generalization_regression.py` so it's skipped during pre-commit runs, preventing it from slowing down the pre-commit hook.

### Removed

- **GPU acceleration feature**: Removed `use_gpu` configuration option and all GPU-related code. GPU functionality was never implemented and has been replaced by Rust-based substring detection which provides better performance.

## [0.8.1] - 2025-12-07

### Fixed

- **Word processing now prevents dropping valid grammatical suffixes**: Fixed bug where corrections that would drop legitimate suffixes like 's' (plural), 'ed' (past tense), 'er' (comparative), or 'or' (agent noun) were not being filtered. Added guard in `process_word` to prevent corrections like "keyboards" → "keyboard", "depreciated" → "depreciate", or "typer" → "type" that would incorrectly drop valid suffixes.

- **Debug logging now respects `--debug` flag**: Fixed bug where many debug log statements were only enabled when `--debug-typos` was used, not when the general `--debug` flag was enabled. Debug logging in pattern extraction, pattern finding, and related modules now checks both specific typo debugging and the global debug flag. Added `is_debug_enabled()` helper function to check if logger is configured for DEBUG level.

- **Exclusion patterns now support wildcards in word part for exact typo patterns**: Fixed bug where exclusion patterns like `jst -> *` (exact typo with wildcard word) didn't work. Previously, exact typo patterns only used exact string matching for the word part, preventing wildcard matching. Now all exclusion patterns use wildcard matching for the word part, allowing patterns like `jst -> *` to exclude all corrections from "jst" to any word, while `jst -> just` still matches only the specific correction.

## [0.8.0] - 2025-12-06

### Added

- **Rust extension for substring indexing**: Implemented high-performance Rust extension using PyO3 and maturin for `SubstringIndex` class. Provides ~100x faster query performance compared to Python implementation. Index build is ~10-50x faster (parallelizable), query time is ~100x faster (no GIL, SIMD optimizations), and memory usage is ~50% lower (no Python object overhead). Extension automatically used when available, falls back to Python implementation if Rust toolchain not installed.
- **Platform substring conflicts Rust optimization**: Replaced Python `pysuffixarray` implementation with Rust `RustSubstringIndex` in platform substring conflict detection. Eliminates O(N²) linear scan bottleneck in `find_substring_matches`, providing the same ~100x speedup (minutes → seconds) as Candidate Selection. The Rust implementation uses O(log N + M) suffix array queries with binary search instead of O(N) linear scans. Automatically used when Rust extension is available, falls back to Python implementation otherwise.
- **Rust batch pattern corruption checking**: Added `batch_check_patterns` Rust function for parallelized pattern corruption checking. Releases GIL and runs across all CPU cores, providing significant speedup for pattern validation preprocessing. Automatically used when Rust extension is available.
- **Pattern validation thin worker architecture**: Refactored pattern validation to use thin worker architecture, eliminating expensive index building in worker processes. Pre-calculates `would_corrupt` checks using Rust batch function in main process, then passes pre-built indexes and results to workers. This eliminates the "half a minute" worker startup time, making worker initialization nearly instant. Similar optimization to CandidateSelection pass.
- **Pattern validation pickle optimization**: Fixed 30-45 second worker initialization hang by pre-calculating all validation checks (start/end/substring triggers) and passing only lightweight results to workers instead of expensive `BoundaryIndex` objects. This eliminates expensive pickle/unpickle operations that were causing the delay. Workers now receive a simple dict mapping pattern -> validation results instead of the full index structure.
- **Pattern validation batch optimization**: Optimized pre-calculation of validation checks by using batch operations (`batch_check_start`, `batch_check_end`) and suffix array queries instead of calling individual functions per pattern. This reduces the pre-calculation time from minutes to seconds for large pattern sets by eliminating O(N) per-pattern overhead.
- **Helper modules for collision processing**: Added `collision_helpers.py` for collision resolution utilities.

### Changed

- **Pre-commit configuration improvements**: Fixed pre-commit issues by reducing cyclomatic complexity in validation functions, adding appropriate pylint ignore comments for acceptable duplicate-code patterns, and configuring pylint to use `pyproject.toml` settings. Added `IterationPassEntry` to vulture whitelist for Protocol structural typing. Fixed mypy error by adding return type annotation to `get_suffix_array_index` method.
- **Pattern validation complexity reduction**: Refactored complex validation functions to reduce cyclomatic complexity:
  - Extracted boundary checks from `_check_pattern_conflicts_with_precalc` into separate helper functions
  - Extracted validation logic from `_validate_single_pattern_worker` into focused helper functions
  - Extracted pre-calculation logic from `run_parallel_validation` to reduce file length and improve maintainability
- **Pipeline reporting optimization**: Enhanced `find_blocking_word` function with optional pre-calculated maps for active and graveyard corrections, providing O(1) lookups instead of O(n) linear scans when maps are available.

## [0.7.0] - 2025-12-04

### Fixed

- **Duplicate corrections in pipeline**: Fixed bug where the same correction (typo, word, boundary) could appear in both `solver_result.corrections` and `solver_result.patterns`, causing duplicates in the final output and QMK compiler errors like "Ignoring duplicate typo". The pipeline now deduplicates when combining corrections and patterns before ranking, preventing duplicates from propagating through the ranking and output generation process.
- **NONE boundary false trigger check now includes prefix/suffix**: Fixed bug where NONE boundary false trigger check only checked for middle substrings, missing cases where the typo appears as a prefix or suffix of the target word or validation words. Now correctly detects false triggers when typo appears anywhere (prefix, suffix, or middle substring) for NONE boundary, ensuring corrections like `alway -> always` with NONE boundary are properly graveyarded when the typo is a prefix of the target word.
- **Test convergence fix**: Updated `test_solver_handles_simple_case` to allow 5 iterations instead of 3, as some cases legitimately need more iterations to converge when corrections are being refined through the iterative solver passes.

- **Pattern validation checks substring conflicts for NONE boundary**: Fixed bug where patterns with NONE boundary were not checked for substring matches in validation words. Previously, `check_pattern_conflicts` only checked prefix/suffix matches, so patterns like "simet" with NONE boundary were accepted even when they appeared as substrings in words like "dosimeter", causing QMK false trigger warnings. Now patterns with NONE boundary are checked for substring matches, preventing garbage patterns from being added.
- **False triggers are graveyarded and safer boundaries are tried**: Fixed bug where corrections that would cause false triggers were not being added to the graveyard. Previously, when a boundary would cause false triggers, the code would skip it but not record it in the graveyard, causing the same boundary to be retried on subsequent iterations. Now false triggers are properly graveyarded with `RejectionReason.FALSE_TRIGGER`, allowing the solver to try safer boundaries (e.g., BOTH instead of NONE) on the next iteration. This ensures garbage corrections are properly rejected and the solver converges to safe boundaries.
- **Boundary detection uses filtered validation set**: Fixed boundary detection to use the filtered validation set (respects user exclusion patterns) instead of the full validation set. When users exclude words via patterns like `*ball`, those words should not block valid typos from using NONE boundary during boundary detection. The full validation set is still used for false trigger checking to catch all garbage corrections.
- **Platform substring conflicts prefer less restrictive boundaries**: Fixed logic to prefer less restrictive boundaries (NONE > LEFT/RIGHT > BOTH) when resolving cross-boundary substring conflicts. Now checks if the less restrictive boundary would cause false triggers before making a decision - if it doesn't trigger garbage corrections, the less restrictive boundary is preferred and the more restrictive one is removed (e.g., removes `:aemr` with LEFT boundary in favor of `aemr` with NONE boundary when NONE is safe). Added debug logging in `platform_substring_conflict_debug.py` to show boundary comparisons, false trigger checks, and resolution decisions when using `--debug-words` or `--debug-typos`.
- **Removed verbose debug logging for non-debug typos**: Removed `[CACHE MISS]` and `[CACHE HIT]` debug log messages that were being logged for all typos when `--verbose` was enabled. These messages are now only logged for debug typos/words (when `--debug-typo` or `--debug-word` is specified).

### Changed

- **Increased default max_iterations from 10 to 20**: The default maximum number of solver iterations has been increased from 10 to 20 to allow more time for complex dictionaries to converge. This can be overridden with `--max-iterations` or `"max_iterations"` in JSON config.
- **Removed redundant QMK character filtering**: Removed duplicate character filtering from QMK platform backend. Character filtering is already handled by `PlatformConstraintsPass` earlier in the pipeline, making the QMK-specific filtering phase redundant. Removed `filter_corrections` method from platform backends and all related filtering metadata.
- **Missing false trigger checks in CandidateSelectionPass**: Added false trigger validation to all boundary selection paths in `CandidateSelectionPass`. Previously, corrections could be added with `NONE` boundary even when the typo appeared as a substring in valid words (e.g., `wmo -> wom` matching inside "snowmobile"), causing QMK compiler warnings. Now all boundaries are checked for false triggers before being added, ensuring corrections only use safe boundaries or are rejected if no safe boundary exists.
- **Cross-boundary substring conflicts**: Added `PlatformSubstringConflictPass` to detect and remove substring conflicts that occur when the same typo text appears with different boundaries. For QMK (RTL), formatted strings like `"aemr"` and `":aemr"` are substrings of each other, causing compiler errors. The pass removes duplicates based on platform matching direction and boundary restrictiveness. Fixes QMK compilation errors like "Typos may not be substrings of one another".
- **Pattern redundancy detection**: Longer patterns are now rejected when a shorter pattern already handles the same cases (e.g., `otehr -> other` rejected if `tehr -> ther` exists). Prevents duplicate patterns and ensures QMK compilation succeeds.
- **Debug typos exact vs wildcard matching**: Exact patterns (e.g., `"teh"`) now use exact matching only, while wildcard patterns (e.g., `"*teh*"`) use substring matching. Previously, exact patterns would match all typos containing the substring.
- **Pattern validation boundary checks**: Patterns with safe boundaries (RIGHT, LEFT, BOTH) now skip position checks where they cannot match, fixing incorrect rejections like "teh -> the" with RIGHT boundary.
- **Substring conflict detection**: Now includes patterns in conflict detection (not just direct corrections), checks all positions (not just prefix/suffix), and simplified QMK filtering to prevent restoring invalid corrections.
- **Type errors and report generation**: Fixed all mypy type errors across 88 files and ensured report generation properly extracts data from solver state.
- **Progress bars in iterative solver**: Progress bars now track actual work items (typos, corrections, patterns) instead of passes, and the top-level iterations progress bar has been removed. Individual passes show progress for their specific work items:
  - CandidateSelectionPass: Shows progress for typos being processed
  - PatternGeneralizationPass: Shows progress for patterns being validated
  - ConflictRemovalPass: Shows progress for corrections/patterns being checked
  - PlatformSubstringConflictPass: Shows progress for typos being checked (now tracks individual typos instead of length buckets)
  - PlatformConstraintsPass: Shows separate progress for corrections and patterns
- **Refactored pattern extraction**: Split `_find_patterns()` (260 → 70 lines) into focused helper functions for better maintainability.
- **Code refactoring for maintainability**: Broke up large files and functions to improve code maintainability:
  - Split `candidate_selection.py` (834 lines) into `candidate_selection.py` (479 lines) and `candidate_selection_workers.py` (404 lines) for better separation of worker functions
  - Extracted helper functions from large functions in `pattern_validation_runner.py` and `correction_processing.py` to reduce function complexity
  - All functions are now under 100 lines of code (excluding comments)
  - Files over 500 lines have been split into focused modules with single responsibilities

### Performance

- **Suffix array optimization for platform substring conflicts**: Implemented suffix array-based substring detection in `PlatformSubstringConflictPass` using `pysuffixarray` library. Replaces O(N²) nested loop with O(log N + M) suffix array queries, reducing conflict detection time from 4-14 min to ~2 min (85% reduction). Builds suffix array once from all formatted typos, then queries efficiently for substring matches.
- **Batch false trigger checks**: Added batch checking methods to `BoundaryIndex` class (`batch_check_start`, `batch_check_end`, `batch_check_substring`) and integrated batch processing into `CandidateSelectionPass`. Instead of making 420K individual index queries (6-11 min), all typos are checked in a single batch operation, reducing false trigger check time to 2-3 min (65% reduction). Batch results are cached and reused for individual false trigger checks.
- **QMK ranking optimizations**: Batch word frequency lookups (O(1) access), lazy pattern scoring, optimized debug logging, and separate tier sorting. Expected 70-90% reduction in ranking time.
- **Parallelized solver passes**: Candidate selection, pattern generalization, and conflict detection now use multiprocessing with linear speedup proportional to CPU cores. Pattern extraction results cached across iterations.
- **Platform substring conflict detection optimizations**:
  - Parallelized typo formatting phase (2-4x speedup on multi-core systems)
  - TypoIndex-style conflict detection algorithm (O(n log n) sort + dict-based lookups instead of O(n²) nested loops)
  - Cached formatted results to eliminate redundant formatting calls
  - Stored conflict pairs during detection to eliminate O(n²) debug logging phase
  - **Character-based indexing**: Index formatted typos by first character to reduce comparisons from O(N²) to O(N × K) where K = average candidates per character (typically < 50). Expected 10-100x reduction in comparisons.
  - **Early termination for correction pairs**: Track corrections already marked for removal and skip checking pairs where one correction is already marked. Expected 2-5x reduction in correction pair checks.
  - **Optimized substring checks**: Use `startswith()` and `endswith()` fast paths for prefix/suffix checks (common for QMK), falling back to `in` operator only for middle substrings. Expected 1.5-2x speedup for prefix/suffix cases.
  - **Length bucket processing**: Group formatted typos by length into buckets and only check conflicts between adjacent length buckets. A typo of length 3 can't be a substring of a typo of length 2, reducing unnecessary comparisons. Expected 1.5-3x speedup.
  - Expected 20-500x speedup for large datasets (10k+ corrections) with all optimizations combined

### Added

- **`--hurtmycpu` flag for comprehensive pattern discovery**: Added `--hurtmycpu` (aliases: `--overnight`, `--takeforever`) flag that generates typos for ALL words in the `english-words` dictionary instead of just the top-N from wordfreq. This enables complete pattern discovery (e.g., finding all `*king` words like "walking", "talking", "working", "looking", etc. to discover the `kign -> king` pattern) while still respecting `--top-n` for final dictionary selection. Processing time increases significantly (hours to overnight) but finds patterns that would otherwise be missed.
- **Pass timing in verbose output**: Each solver pass now logs its execution time in the verbose output (e.g., "completed in 1m 12s"). This helps identify performance bottlenecks and optimize slow passes.


## [0.6.0] - 2025-12-02

### Added

- **Iterative Solver Architecture**: Replaced linear stages 3-6 with a convergence-based solver that can backtrack and self-heal
  - **DictionaryState**: Centralized state manager with graveyard to prevent infinite loops
  - **IterativeSolver**: Orchestrator that runs passes until convergence
  - **Pass System**: Modular architecture with four specialized passes:
    - `CandidateSelectionPass`: Promotes raw typos to active corrections with graveyard-based backtracking
    - `PatternGeneralizationPass`: Compresses specific corrections into general patterns
    - `ConflictRemovalPass`: Enforces substring/overlap rules and triggers self-healing
    - `PlatformConstraintsPass`: Enforces hard platform limits
  - **Self-Healing**: When conflicts arise, the solver automatically retries with stricter boundaries
  - **Debug Tracing**: Comprehensive trace log showing all decisions affecting debug targets
  - New function `run_iterative_solver_pipeline()` in `entroppy/processing/pipeline.py`
  - Detailed documentation in `docs/ALGORITHMS.md`

- **Log file saving**: When `--reports` is enabled, all logs are now automatically saved to `entroppy-(timestamp).log` in the report directory
  - Logs continue to be displayed on stderr as before
  - File handler is added without disrupting existing console output
  - Log file uses the same timestamp format as the report directory for easy correlation
  - File format matches console output (no color codes, timestamps in debug mode)

- **Configurable solver iterations**: Added `max_iterations` setting (CLI: `--max-iterations`, JSON: `"max_iterations"`) to control the maximum number of solver iterations (default: 20)

### Changed

- **Code refactoring and modularization**: Split large files (>500 lines) into focused modules, extracted debug logging into separate modules, and refactored large functions into smaller helpers
  - Pattern generalization: Split `patterns.py` (618 → 90 lines) into validation workers/runners and index/conflict modules
  - Pattern validation: Split into `pattern_indexes.py` and `pattern_conflicts.py` modules
  - Boundary selection: Split `boundary_selection.py` (717 lines) into selection, logging, utils, and false trigger check modules
  - Collision processing: Split large functions into focused helpers
  - Debug logging: Moved to dedicated modules (`word_processing_logging.py`, `pattern_logging.py`, `conflict_logging.py`, `qmk_logging.py`)
  - Removed redundant code: Eliminated duplicate implementations in pattern validation and config modules, simplified boundary checks

- **Pattern extraction and validation improvements**: Enhanced pattern discovery and validation logic
  - Now extracts both prefix and suffix patterns for all platforms (previously platform-specific)
  - Fixed pattern extraction to find patterns across corrections with different prefixes/suffixes
  - Pattern validation now checks substring conflicts in both directions and uses boundary type instead of match direction
  - Added `CorrectionIndex` class for O(1) lookups in pattern validation

- **QMK platform enhancements**: Improved filtering, ranking, and reporting
  - Performance optimizations: Indexed conflict detection (10-50x speedup), combined filtering passes (20-30% faster), unified ranking sort (10-20% faster), pattern set caching
  - Enhanced ranking report: Added summary by type, complete ranked list, enhanced pattern/direct correction details with full replacement lists
  - Debug logging: Added comprehensive logging for filtering, ranking, substring conflicts, and pattern extraction

### Fixed

- **Infinite loop in pattern generalization**: Fixed issue where rejected patterns were repeatedly reprocessed
  - Rejected patterns are now added to graveyard and skipped during extraction
  - Updated `rejected_patterns` format to include boundary: `(typo_pattern, word_pattern, boundary, reason)`
  - Graveyard check now happens during pattern extraction to prevent reprocessing

- **QMK substring conflict detection**: Fixed multiple issues preventing garbage corrections and compilation errors
  - Now prevents garbage corrections by checking if shorter typos would produce incorrect results for longer typos
  - Catches all substring relationships (prefix, suffix, middle) to satisfy QMK's hard constraint
  - Only checks suffixes (not middle substrings) to eliminate false positives

- **Collision resolution architecture**: Fixed issue where valid corrections with different boundaries were incorrectly rejected
  - Now determines boundaries before frequency comparison, allowing multiple valid corrections per typo when using different boundaries

- **Solver convergence detection**: Fixed issue where solver continued running after convergence
  - Solver now properly detects convergence when net changes are zero (corrections, patterns, and graveyard all unchanged)
  - Previously, solver would continue until max iterations even when passes were making offsetting changes (e.g., CandidateSelection adding corrections that PatternGeneralization immediately removed)
  - Convergence is now based on net state changes rather than just the `is_dirty` flag

### Performance

- **Word frequency lookup caching**: Added `@functools.lru_cache` wrapper, reducing collision resolution time by 30-50% for large datasets
- **Boundary detection indexing**: Created `BoundaryIndex` class with pre-built prefix/suffix/substring indexes, achieving 37x speedup (5 → 188 words/sec) and 80-95% reduction in boundary detection time
- **Pattern extraction optimization**: Optimized grouping and filtering, reducing extraction time by 40-60% for large correction sets
- **Substring index optimization**: Pre-computes substring relationships for collision resolution, reducing boundary selection time by 60-80% for large typo maps
- **Blocking map optimization**: Pre-computes blocking relationships during conflict removal, reducing conflict analysis time by 70-90%

### Added

- **Iteration logging**: Added per-iteration logging to iterative solver showing corrections, patterns, graveyard size, and convergence progress
- **Progress bars and debug logging**: Added progress indicators for pattern generalization and comprehensive debug logging for pattern extraction, QMK filtering, and ranking phases
- **Enhanced debug logging coverage**: Added separate debug logging modules for pattern generalization, dictionary loading, and platform filtering stages. Improved visibility into previously silent areas including pattern collision resolution, cross-boundary pattern conflicts, pattern substring conflicts, and platform max_corrections limit application

## [0.5.3] - 2025-12-01

### Fixed

- **Critical security fix: Prevented predictive corrections**: Added target word validation to boundary selection and pattern validation. Corrections like `alway -> always` with NONE/LEFT boundary no longer trigger when typing "always" correctly. Target word checks have highest priority.

### Changed

- **Code cleanup**: Removed redundant type validation (~60 lines), unused function parameters, unified file writing with `write_file_safely()` helper, optimized QMK report score lookups (O(n) → O(1)), created centralized file I/O utilities, extracted boundary details collection logic.


## [0.5.2] - 2025-12-01

### Changed

- **Simplified boundary selection**: Removed candidate preparation logic, boundaries checked in fixed order (NONE → LEFT → RIGHT → BOTH). Removed unused parameters.
- **Enhanced boundary debugging**: Added detailed logging for boundary decisions when using `--debug-typos`.
- **Refactored collision resolution**: Split `collision.py` (928 → 330 lines) into focused modules (worker_context, typo_index, exclusion, boundary_selection, correction_processing, substring_conflicts).
- **Improved logging and UX**: Added startup banner, completion summary, standardized stage numbering, visual indicators (✓/✗/⚠️), consistent error formatting.

### Performance

- **Collision resolution parallelization**: Parallelized collision resolution with multiprocessing, chunk-based substring index building. Near-linear speedup with number of workers.
- **Pattern validation optimization**: Added `SourceWordIndex` class for O(1) lookups instead of O(source_words) scans. 50-70% reduction in validation time.

## [0.5.1] - 2025-11-30

### Fixed

- **Pattern classification bug in QMK ranking reports**: Fixed incorrect classification where patterns were reported as "direct corrections". Added `update_patterns_from_conflicts()` to update `pattern_replacements` when conflicts detected during platform filtering. Reports now correctly classify patterns.

## [0.5.0] - 2025-01-29

### Added

- **Pydantic v2 type validation**: Replaced manual validation with Pydantic BaseModel. Converted Config and stage result models, added field constraints, automatic type coercion. ~50 lines of manual validation eliminated.
- **Constants and helper functions**: Centralized magic numbers/strings in `constants.py`, added `log_if_debug_correction()` and `expand_file_path()` helpers.

### Changed

- **Code deduplication**: Replaced magic numbers with constants, consolidated debug logging patterns, unified file path expansion.
- **Code style**: Standardized import organization, improved type hinting, resolved circular dependencies by moving `Correction` type to `core/types.py`.
- **Error handling**: Added comprehensive error handling for file I/O, JSON parsing, external libraries, and input validation.
- **Backend refactoring**: Split QMK backend (437 lines) and Espanso backend (292 lines) into focused modules (formatting, filtering, ranking, output, etc.).
- **Code consolidation**: Consolidated report headers, moved QMK-specific code to QMK module, extracted helper functions from large functions.

### Fixed

- **Circular imports**: Resolved circular dependencies, moved `Correction` type to dedicated module, removed lazy imports.


## [0.4.3] - 2025-12-01

### Changed

- **Code consolidation**: Removed redundant header wrappers, consolidated boundary formatting utilities, removed duplicate imports.
- **File structure refactoring**: Split `collision.py` (623 → 388 lines) and `patterns.py` (463 → 160 lines) into focused modules.

## [0.4.2] - 2025-12-01

### Changed

- **Major file structure reorganization**: Reorganized codebase into logical modules (`core/`, `processing/`, `resolution/`, `matching/`, `platforms/`, `data/`, `reports/`, `utils/`, `cli/`). Improved module naming, updated all imports, added `pyproject.toml`.

## [0.4.1] - 2025-11-30

### Changed

- **Code refactoring**: Consolidated duplicate boundary checking functions, unified pattern finding, streamlined QMK conflict detection, created shared report utilities. ~200 lines of duplicate code eliminated.

## [0.4.0] - 2025-11-30

### Added

- **Debug tracing flags**: Added `--debug-words` and `--debug-typos` flags for tracing words/typos through pipeline. Supports exact matches, wildcards, and boundary patterns. Requires `--debug` and `--verbose`.
- **Structured logging with loguru**: Replaced all `print()` statements with loguru. Three log levels (WARNING/INFO/DEBUG), `--debug` flag, centralized logger configuration.

### Changed

- Updated all modules to use loguru instead of print statements.

### Fixed

- **QMK substring conflicts**: Fixed bug where QMK rejected dictionaries with substring typos. Implemented comprehensive `_detect_substring_conflicts()` to enforce QMK's constraint.
- **Pipeline bug**: Fixed `UnboundLocalError` in pattern generalization stage.

## [0.3.1] - 2025-11-29

### Added

- **Platform-specific reporting**: Added `generate_platform_report()` method, platform name in report folders, QMK and Espanso report implementations with platform-specific details.
- **QMK pattern generation**: Added `find_prefix_patterns()` for RTL matching, pattern generalization now platform-aware.

### Changed

- Report folders include platform name, pattern generalization respects match direction.

### Known Limitations

- Pattern generation incomplete for QMK (misses common patterns like `teh → the`).

## [0.3.0] - 2025-11-29

### Added

- **Platform abstraction system**: `PlatformBackend` abstract base class, `PlatformConstraints` dataclass, `MatchDirection` enum, factory function for platform selection.
- **Platform backends**: Espanso backend (fully implemented), QMK backend (architecture ready with constraints).
- **Pipeline integration**: Platform-specific filtering, ranking, and output generation. `--platform` CLI option and JSON config field.

### Changed

- Pipeline now platform-aware, output generation delegated to platform backends.


## [0.2.1] - 2025-11-28

### Fixed

- **Cross-boundary deduplication**: Fixed bug causing Espanso disambiguation windows when typing typos. Pattern generalization could create corrections with different boundaries for same (typo, word) pair. Added deduplication logic to ensure only one correction per pair reaches output.

## [0.2.0] - 2025-11-28

### Changed

- **Major refactoring**: Unified pattern matching, extracted conflict resolution, refactored pipeline into modular stages, eliminated global state. Reduced `pipeline.py` from 395 to 132 lines.

### Added

- **New modules**: `pattern_matching.py`, `conflict_resolution.py`, `stages/` directory with modular pipeline stages, `worker_context.py` for thread-safe state.
- **Testing**: 145 tests covering all refactored components.

---

## [0.1.6] - 2025-11-27

### Fixed

- **Exclusion filtering**: Fixed bug where boundary specifiers (`:`) in exclusion patterns were ignored. `ExclusionMatcher` now correctly parses and enforces boundary specifiers.

## [0.1.5] - 2025-11-26

### Changed

- **Report format**: Conflicts now grouped by correction word instead of listing each blocked typo individually. Reports ~95% smaller.

### Fixed

- **Report generation**: Fixed incorrect blocker identification. Added validation to match conflict removal logic.
- **Pattern generation**: Fixed invalid suffix patterns (now requires identical prefixes) and nonsensical candidate patterns (requires at least 2 characters of prefix).

## [0.1.4] - 2025-11-26

### Performance

- **Parallelized YAML writing**: 10-12x speedup with multiple workers.

### Added

- **Progress tracking**: Added progress bar for report analysis, status messages for output stages.

### Changed

- **Progress indicators**: Only shown for long-running operations, quick operations show status messages.

## [0.1.3] - 2025-11-26

### Changed

- **Reverted v0.1.1 containment check**: Removed boundary logic forcing `word: true` for substring containment. Fast-typing issues appear to be upstream Espanso bug.

## [0.1.2] - 2025-11-26

### Fixed

- **Pattern generation**: Fixed useless no-op patterns where typo and correction suffixes were identical.

## [0.1.1] - 2025-11-26

### Fixed

- **Race condition with fast typing**: Corrections now automatically get `word: true` boundary when typo contains correction as substring or vice versa, preventing partial matches mid-keystroke.

## [0.1.0] - 2025-11-26

### Initial Beta Release

First beta release with core functionality: typo generation, boundary detection, collision resolution, pattern generalization, multiprocessing support, comprehensive reporting system, and configurable pipeline.

---

## Version History

- **0.7.0** (2025-12-04): Pipeline deduplication, false trigger improvements, pattern validation enhancements, and performance optimizations
- **0.6.0** (2025-12-02): Code refactoring, pattern improvements, QMK enhancements, and performance optimizations
- **0.5.3** (2025-12-01): Critical security fix for predictive corrections, code cleanup and simplification
- **0.5.2** (2025-12-01): Simplified boundary selection, collision resolution refactoring, parallelization, and improved logging
- **0.5.1** (2025-11-30): Fixed pattern classification bug in QMK ranking reports
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
