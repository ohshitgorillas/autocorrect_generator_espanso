# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

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

