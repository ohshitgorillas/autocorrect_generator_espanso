# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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

- **0.1.1** (2025-11-26): Critical bug fix for race conditions with fast typing
- **0.1.0** (2025-11-26): Initial beta release

