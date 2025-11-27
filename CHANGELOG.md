# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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

- **0.1.5** (2025-11-26): Fixed conflict report incorrectly identifying blockers
- **0.1.4** (2025-11-26): Parallelized YAML file generation with progress tracking
- **0.1.3** (2025-11-26): Reverted v0.1.1 containment check (Espanso bug, not generator issue)
- **0.1.2** (2025-11-26): Fixed useless no-op pattern generation
- **0.1.1** (2025-11-26): Critical bug fix for race conditions with fast typing
- **0.1.0** (2025-11-26): Initial beta release

