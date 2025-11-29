# EntropPy

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Version 0.3.1 (Beta)** | [Changelog](CHANGELOG.md)

A Python-based autocorrect dictionary generator for multiple text expansion and autocorrect platforms.

It uses `english-words` and `wordfreq` to algorithmically "fuzz" lists of English words, generating typos mapped to their correct spellings.

It generates five types of typing errors:
* **Transpositions**: Swapped characters (e.g., `the` → `teh`).
* **Omissions**: Missing characters (e.g., `because` → `becuse`).
* **Duplications**: Doubled characters (e.g., `entropy` → `entroppy`). 
* **Replacements**: Wrong characters (e.g., `apple` → `applw`).
* **Insertions**: Additional characters (e.g., `food` → `foopd`).

## Inspiration
This project originated as a tool for [QMK Firmware](https://qmk.fm/)'s Autocorrect feature. I was dissatisfied with existing autocorrect dictionaries, which were bloated with spelling mistakes caused by genuine lack of knowledge rather than mechanical typing errors (e.g., `definately` → `definitely`). I know how to spell, I just have fat fingers.

After manually entering my own mistakes for a while, I realized I didn't need a pre-existing dictionary. I could generate an arbitrarily large corpus of typos algorithmically, which led to the creation of this project.

However, different platforms have different constraints. Keyboard firmware has limited storage (my QMK keyboard stores ~1,100 corrections), while host-level tools like Espanso can handle hundreds of thousands. EntropPy generates corrections in 10–20 minutes and can target multiple platforms, optimizing output for each platform's capabilities and constraints.

## Features

* **Multi-Platform Support**: Generate corrections for Espanso, QMK, or other platforms via extensible backend system
* **Smart Boundary Detection**: Automatically assigns word boundaries to prevent typos from triggering inside other valid words (e.g., prevents `nto` → `not` from triggering inside `onto` and producing `onot`)
* **Collision Resolution**: Uses frequency analysis to resolve ambiguous typos that map to multiple words (e.g., `thn` could be `then`, `than`, or `thin`)
* **Pattern Generalization**: Automatically detects repeated patterns and creates generalized rules, reducing dictionary size (platform-specific: respects each platform's match direction)
* **Platform-Specific Reporting**: Detailed reports tailored to each platform showing filtering decisions, cutoff analysis, and optimization results
* **Platform-Specific Optimization**:
  - **Espanso**: Alphabetically organized YAML files with RAM estimation
  - **QMK**: Frequency-based ranking and space-optimized corrections (in progress)
* **Highly Configurable**: Customize input lists, exclusion patterns, adjacent key mappings, and frequency thresholds
* **Progress Tracking**: Real-time progress bars for word processing, pattern generalization, conflict removal, and file writing

---

## Setup Instructions

### 1. Install the Backend
The backend is the software that will actually be using the generated dictionary. This may be:
* QMK
* Espanso
* More to come...

### 2. Environment Setup
It is recommended to run EntropPy inside a virtual environment:

```bash
# Clone the repository
git clone https://github.com/ohshitgorillas/entroppy.git /path/to/project

# Set up the virtual environment
cd /path/to/project
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Set up directories (optional)
mkdir corrections settings reports

# Install dependencies
pip install -r requirements.txt
```

---

## Usage

It's recommended to generate dictionaries into a local `corrections` folder for manual review before deploying them to your target platform. Review the generated reports to verify correction quality.

### Basic Generation
Generate transpositions, omissions, and duplications for the top 1,000 most common English words:

```bash
python -m entroppy --top-n 1000 --output corrections
```

After reviewing the reports, deploy the corrections to your chosen platform (see Platform Support section below).

## Platform Support

EntropPy supports multiple autocorrect platforms through a platform abstraction layer. Each platform has unique characteristics that influence how corrections are generated, filtered, and formatted.

### ✅ Espanso (Default)
Host-level text expander supporting unlimited corrections.

**Status**: Complete
**Output**: YAML files organized alphabetically
**Characteristics**:
- Unlimited corrections
- Full Unicode support
- Left-to-right matching
- RAM estimation included in reports

**Example Usage:**
```bash
python -m entroppy --platform espanso --top-n 5000 --output corrections
```

**Deploying to Espanso:**

**Linux/macOS:**
```bash
mkdir ~/.config/espanso/match/autocorrect
cp corrections/*.yml ~/.config/espanso/match/autocorrect/
espanso restart
```

**Windows (PowerShell):**
```powershell
mkdir "$env:APPDATA\espanso\match\autocorrect"
Copy-Item corrections\*.yml "$env:APPDATA\espanso\match\autocorrect\"
espanso restart
```

### 🚧 QMK Firmware
Keyboard firmware-level autocorrect with strict space constraints.

**Status**: Partial - Pattern generation in progress
**Output**: C header file (format complete, pattern optimization ongoing)
**Characteristics**:
- ~1,500 correction limit (flash memory)
- Alphas + apostrophe only
- Right-to-left matching
- Frequency-based ranking
- Cutoff analysis in reports

**Example Usage:**
```bash
python -m entroppy --platform qmk --top-n 10000 --output corrections --reports reports
```

**Known Limitations:**
- Pattern generation misses some common patterns (`teh` → `the`, `toin` → `tion`)
- Dictionary not yet fully optimized for limited space
- These are active development areas

**Deploying to QMK:**
Copy the generated header file to your QMK keymap directory and configure according to [QMK Autocorrect documentation](https://docs.qmk.fm/#/feature_autocorrect).

### Specifying Platform

**Command line:**
```bash
python -m entroppy --platform espanso  # default
python -m entroppy --platform qmk
```

**Configuration file:**
```json
{
  "platform": "espanso",
  "top_n": 5000,
  "output": "corrections"
}
```

### Advanced Usage
Generate typos using a custom word list, exclusion patterns, and adjacent key map:

```bash
python -m entroppy \
    --platform espanso \
    --verbose \
    --top-n 2000 \
    --include settings/my_custom_words.txt \
    --exclude settings/exclusions.txt \
    --typo-freq-threshold 1e-8 \
    --max-word-length 12 \
    --adjacent-letters settings/qwerty_map.txt \
    --output corrections \
    --reports reports
```

Using `--typo-freq-threshold` catches conjugations and word forms not in `english-words` but present in `wordfreq`. For example, `juts` (both a transposition of `just` and a conjugation of `jut`) appears in `wordfreq` (~2e-7 frequency) but not `english-words`. Without this threshold, the script would incorrectly generate `juts` → `just`.

### Logging and Output Control

EntropPy uses structured logging with three levels:

- **Default** (no flags): Only shows warnings and errors
- **Verbose** (`--verbose` or `-v`): Shows informational messages about progress and statistics
- **Debug** (`--debug` or `-d`): Shows detailed debug information with timestamps and source locations

```bash
# Default - minimal output
python -m entroppy --platform espanso --top-n 1000 --output corrections

# Verbose - show progress and statistics
python -m entroppy --platform espanso --top-n 1000 --output corrections --verbose

# Debug - detailed logging with timestamps
python -m entroppy --platform espanso --top-n 1000 --output corrections --debug
```

All logging output goes to stderr, keeping stdout available for piped data.

### Debug Tracing Flags

For deep debugging and understanding why specific corrections are or aren't generated, use the specialized tracing flags. **Both require `--debug` and `--verbose` to be enabled.**

#### `--debug-words` - Trace Specific Words

Track specific words through the entire pipeline with exact matching (case-insensitive):

```bash
python -m entroppy \
    --platform espanso \
    --top-n 1000 \
    --output corrections \
    --debug --verbose \
    --debug-words "the,because,action"
```

**Logs show:**
- Whether the word is in the source dictionary (with frequency and rank)
- All typos generated from the word
- Why typos were filtered (valid word, frequency threshold, etc.)
- Collision resolution decisions
- Final boundary determination

#### `--debug-typos` - Trace Typos with Pattern Support

Track specific typos with powerful pattern matching:

```bash
# Exact matches
python -m entroppy --debug --verbose --debug-typos "teh,adn,becuse" --top-n 1000 --output corrections

# Wildcards - match any characters
python -m entroppy --debug --verbose --debug-typos "*tion,err*,*the*" --top-n 5000 --output corrections

# Boundaries - match specific boundary types
python -m entroppy --debug --verbose --debug-typos ":teh,ing:,:teh:" --top-n 1000 --output corrections

# Combined patterns
python -m entroppy --debug --verbose --debug-typos "err*:,*ing:,:the" --top-n 1000 --output corrections
```

**Pattern Syntax:**
- **Exact**: `teh` - matches "teh" with any boundary type
- **Wildcards**:
  - `*tion` - matches typos ending in "tion" (e.g., "actoin", "metnoin")
  - `err*` - matches typos starting with "err" (e.g., "erro", "errro")
  - `*the*` - matches typos containing "the" (e.g., "thhe", "theer")
- **Boundaries**:
  - `:teh` - matches "teh" with LEFT or BOTH boundary only
  - `teh:` - matches "teh" with RIGHT or BOTH boundary only
  - `:teh:` - matches "teh" with BOTH boundaries only
- **Combined**: `err*:` - wildcards + boundaries work together

**Logs show:**
- Which pattern matched the typo (for wildcard/boundary patterns)
- Which word generated the typo
- Boundary determination logic
- Collision winners and losers
- Why typos were filtered or excluded

**Example Output:**
```
[DEBUG WORD: 'the'] [Stage 1] Included from wordfreq (rank: 1, zipf freq: 7.73)
[DEBUG WORD: 'the'] [Stage 2] Generating typos for debug word
[DEBUG WORD: 'the'] [Stage 2] Generated typo: teh
[DEBUG WORD: 'the'] [Stage 2] Created correction: teh → the (boundary: right)
[DEBUG TYPO: 'teh' (matched: teh)] [Stage 2] Generated from word: the (boundary: right)
[DEBUG WORD: 'the'] [Stage 3] Selected (no collision, boundary: right) (typo: teh)
[DEBUG TYPO: 'teh' (matched: teh)] [Stage 3] Selected (no collision, boundary: right) (word: the)
```

### Generating Reports

Reports provide detailed analysis of EntropPy's decisions and are essential for understanding and tuning configuration:

```bash
python -m entroppy \
    --platform espanso \
    --top-n 5000 \
    --output corrections \
    --reports reports \
    --verbose
```

This creates a timestamped, platform-specific directory (e.g., `reports/2025-11-29_14-30-15_espanso/`) with:

**Universal Reports** (all platforms):
- **`summary.txt`** - Overall statistics and timing breakdown
- **`collisions.txt`** - Ambiguous typos that were skipped
- **`patterns.txt`** - Generalized patterns and rejected patterns
- **`conflicts_none.txt`** - Substring conflicts (no boundary)
- **`conflicts_left.txt`** - Substring conflicts (left boundary)
- **`conflicts_right.txt`** - Substring conflicts (right boundary)
- **`conflicts_both.txt`** - Substring conflicts (both boundaries)
- **`short_typos.txt`** - Typos skipped for being too short (if any)
- **`exclusions.txt`** - Corrections blocked by exclusion rules (if any)
- **`statistics.csv`** - Machine-readable statistics for analysis

**Platform-Specific Reports:**

**Espanso:**
- RAM estimation and file size breakdown
- Largest files by entry count
- File organization by letter

**QMK:**
- Filtering details (character set violations, conflicts)
- The Cutoff Bubble (last 10 that made the cut, first 10 that didn't)
- User words section
- Pattern and direct correction breakdown

Reports are invaluable for understanding platform-specific optimization decisions.

---

## Configuration Options

You can configure EntropPy via Command Line Arguments or a `config.json` file.

### Command Line Arguments

| Argument | Default | Description |
| :--- | :--- | :--- |
| `--platform` | `espanso` | Target platform (espanso, qmk). |
| `--output`, `-o` | `None` | Directory to output files. (Prints to stdout if omitted). |
| `--reports` | `None` | Directory to generate detailed reports (creates timestamped subdirectories). |
| `--jobs`, `-j` | CPU Count | Number of parallel worker processes. |
| `--top-n` | `None` | Process the top N most frequent English words. |
| `--include` | `None` | Path to a file containing specific words to process. |
| `--exclude` | `None` | File containing exclusion patterns (see below). |
| `--adjacent-letters` | `None` | File mapping keys to neighbors for replacement/insertion typos. |
| `--freq-ratio` | `10.0` | Minimum frequency ratio required to resolve a collision. |
| `--min-typo-length` | `5` | Minimum length of a generated typo to be included. |
| `--min-word-length` | `3` | Minimum word length to generate typos for. |
| `--max-word-length` | `10` | Maximum word length to generate typos for. |
| `--typo-freq-threshold` | `0.0` | Skip typos with a `wordfreq` frequency above this. |
| `--max-entries-per-file`| `500` | Maximum number of corrections per YAML file. |
| `--verbose`, `-v` | `False` | Print statistics, RAM estimates, and dropped typos (INFO level). |
| `--debug`, `-d` | `False` | Enable debug logging with timestamps and source locations. |

### JSON Configuration
Instead of long CLI strings, you can use a `config.json`:

```json
{
  "platform": "espanso",
  "top_n": 5000,
  "output": "corrections",
  "reports": "reports",
  "min_typo_length": 4,
  "exclude": "settings/exclusions.txt",
  "adjacent_letters": "settings/qwerty.txt",
  "verbose": true,
  "debug": false
}
```

Run with:
```bash
python -m entroppy --config settings/config.json
```

The `config.json` file supports all configuration options: just convert `-` into `_`; e.g., `--typo-freq-threshold 1e-8` becomes `"typo_freq_threshold": 1e-8`.

---

## File Formats

### Adjacent Letters (`--adjacent-letters`)
Defines which keys are next to each other to generate **Replacement** and **Insertion** typos.
Format: `key -> neighbors`

```text
# The character you wanted -> the character you got
a -> s
s -> ad
e -> wrd
l -> k;
p -> o[0
```
* **Replacement:** `e -> w` generates `wxample` and `examplw` for `example`.
* **Insertion:** `e -> w` generates `wexample`, `ewxample`, `examplwe`, and `examplew`.

Note that this option is required to generate replacement and insertion typos.

### Include File (`--include`)
Allows the user to specify words for which corrections should be generated.

```text
# Words to generate typos and corrections for
espanso
software
mechanical
keyboard
```

### Exclusion File (`--exclude`)
Provides powerful control over what corrections are generated and what words are considered valid. The file supports two types of rules:

#### 1. Word and Pattern Exclusions
These patterns remove words from the validation dictionary at the start of the process. Any word matching these patterns is treated as a non-word, which is useful for enabling corrections like `teh -> the` which are otherwise blocked by rare words like "tehsildar". Wildcards (`*`) are supported.

```text
# Exclude words containing "teh" from the dictionary, allowing it to be a typo for "the".
*teh*

# Exclude any word ending in "ball".
*ball

# prevents chemistry terms like "cotoin" from blocking the generalization of "-toin" as a typo for "-tion".
*toin
```

#### 2. Correction Filtering
For fine-grained control, you can block specific `(typo, correction)` pairs using the `->` syntax. This supports wildcards and a special colon (`:`) syntax for word boundary requirements.

```text
# Block a specific, exact correction
word -> correction

# Block typos starting with 'xy' from correcting to 'yz'
xy* -> yz

# Block corrections where a typo ends in 'in', corrects to 'ing',
# and requires a right word boundary (e.g., runnin -> running)
*in: -> ing

# Block corrections where a typo starts with 'in', has a left boundary,
# and corrects to a word starting with 'ni'.
:in* -> ni*
```

**Boundary Specifiers:**
- `pattern:`: Requires a **right** word boundary.
- `:pattern`: Requires a **left** word boundary.
- `:pattern:`: Requires **both** word boundaries (a standalone word).

---

## Output Structure

Output format depends on the target platform:

### Espanso Output

Multiple YAML files organized alphabetically by corrected words. Use `--max-entries-per-file` (up to 1000) to control file sizes.

**Example YAML Entry:**
```yaml
matches:
  - trigger: becuse
    replace: because    # No "word" requirement, will trigger anywhere
    propagate_case: true

  - trigger: nto
    replace: not
    word: true          # Must be an isolated word
    propagate_case: true

  - trigger: toin
    replace: tion
    right_word: true    # Must be at the word end or isolated
    propagate_case: true

  - trigger: teh
    replace: the
    left_word: true     # Must be at word start or isolated
    propagate_case: true
```

### QMK Output

Single text file containing corrections ordered alphabetically by the correct spelling.

**Example Text File:**
```text
teh -> the
toin: -> tion
:aer: -> are
```

Refer to platform-specific reports for detailed breakdown of included corrections and filtering decisions.

---

## Boundary Detection

EntropPy automatically determines which boundary constraints are needed to prevent false triggers. This prevents corrections like `nto` → `not` from triggering inside `onto` and producing `onot`.

**Boundary Types:**
- **No boundary** - Typo can trigger anywhere (e.g., `becuse` → `because`)
- **Both boundaries** - Typo must be standalone (e.g., `nto` → `not`)
- **Left boundary** - Typo must be at word start (e.g., `hte` → `the`)
- **Right boundary** - Typo must be at word end (e.g., `toin` → `tion`)

**Platform-Specific Representation:**

**Espanso** uses YAML properties:
- No boundary: No property
- Both: `word: true`
- Left: `left_word: true`
- Right: `right_word: true`

**QMK** uses colon notation in text files:
- No boundary: `teh -> the`
- Both: `:teh: -> the`
- Left: `:teh -> the`
- Right: `teh: -> the`

---

## Pattern Generalization & Conflict Resolution

EntropPy employs sophisticated algorithms to optimize dictionaries and prevent garbage corrections. These optimizations respect each platform's matching behavior (left-to-right vs right-to-left).

### Pattern Generalization

When multiple corrections share a common pattern, EntropPy attempts to create a single generalized rule instead of multiple specific corrections.

**Platform-Specific Pattern Detection:**
- **Espanso (LTR)**: Detects suffix patterns (e.g., `oev → ove`)
- **QMK (RTL)**: Detects prefix patterns (e.g., `teh → the`)

**Example - Valid Generalization (Espanso):**
```
Specific corrections:
  - loev → love
  - moev → move

Generalized to:
  - oev → ove (RIGHT boundary)
```

This works because:
- Typing "loev": triggers `oev → ove`, prefix "l" remains → "l" + "ove" = "love" ✓
- Typing "moev": triggers `oev → ove`, prefix "m" remains → "m" + "ove" = "move" ✓

**Validation Process:**

EntropPy validates each pattern by checking if the platform's matching mechanics would produce the correct result:

```python
# For LTR platforms (Espanso) - suffix patterns:
for each correction in pattern:
    remaining_prefix = full_typo[:-len(pattern_typo)]
    expected_result = remaining_prefix + pattern_correction
    
    if expected_result != full_word:
        reject_pattern()  # Would create garbage!

# For RTL platforms (QMK) - prefix patterns:
for each correction in pattern:
    remaining_suffix = full_typo[len(pattern_typo):]
    expected_result = pattern_correction + remaining_suffix
    
    if expected_result != full_word:
        reject_pattern()  # Would create garbage!
```

**Cross-Boundary Deduplication:**

Pattern generalization also performs cross-boundary deduplication to prevent disambiguation windows. If a pattern would create a correction with the same (typo, word) pair as an existing direct correction (even with a different boundary type), the pattern is rejected entirely.

```
Example - Pattern Rejection:
  Direct correction (Stage 3):
    - teh → the (no boundary)
  
  Pattern candidate (Stage 4):
    - teh(n,ir) → then,their (RIGHT boundary)
    - (ba,la)teh → bathe,lathe (LEFT boundary)
    - Would create: teh → the (NONE, LEFT, and RIGHT boundaries)
  
  Action: Reject pattern entirely
  Reason: Same (typo, word) pair exists with different boundary
  Result: Direct correction wins, pattern gets discarded
```

When a pattern is rejected for cross-boundary conflicts, all corrections it was meant to replace are restored to prevent data loss. This ensures:
- Only ONE correction per (typo, word) pair reaches final output
- No disambiguation windows appear in Espanso
- Direct corrections (Stage 3) always take priority over patterns (Stage 4)


### Substring Conflict Resolution

Espanso triggers on the first (shortest) match when processing text left-to-right. If one typo is a substring of another with the same boundary type, the longer typo might be unreachable.

**Safe Simplification Example:**
```
Corrections:
  - herre → here
  - wherre → where

Analysis for "wherre":
  - Typing triggers: herre → here
  - Remaining prefix: "w"
  - Result: "w" + "herre" = "where" ✓ Correct!
  
Action: Remove "wherre" (redundant)
```

**The algorithm validates each potential removal:**

```python
# For RIGHT boundaries (suffixes):
remaining = long_typo[:-len(short_typo)]
expected_result = remaining + short_word

# For LEFT/NONE/BOTH boundaries (prefixes):
remaining = long_typo[len(short_typo):]
expected_result = short_word + remaining

if expected_result == long_word:
    remove(long_typo)  # Safe - produces correct result
else:
    keep_both()  # Unsafe - would create garbage
```

### Viewing Optimization Results

Use the `--reports` flag to see detailed information about optimization decisions. Report structure varies by platform (see Generating Reports section above for full details).

**Common Reports** (all platforms):
- **`collisions.txt`**: Words that produce the same typo and their frequency ratios
- **`conflicts_*.txt`**: Corrections removed as redundant and the blocking pattern responsible
- **`patterns.txt`**: Which patterns were generalized and which were rejected (with reasons)
- **`statistics.csv`**: Machine-readable statistics for analysis and tracking
- **`summary.txt`**: Overall statistics showing patterns and conflicts found

**Platform-Specific Reports** provide additional insights:
- **Espanso**: RAM estimation, file size breakdown
- **QMK**: Cutoff analysis, filtering details, character set violations

These reports are invaluable for understanding platform-specific optimization decisions.

---

## Known Limitations

### Pattern Generation (QMK)

The current implementation of pattern generation for QMK's right-to-left matching detects some patterns but misses common ones:

**Missing Common Patterns:**
- `teh` → `the` (and variants: `tehn` → `then`, `bateh` → `bathe`)
- `toin` → `tion` (and variants: `-ation`, `-ntion`)

**Impact:**
- QMK dictionaries are not yet fully optimized for limited storage
- More corrections could be represented as patterns to save space
- This is an active development area

**Workarounds:**
- Use higher `--top-n` values to capture more words
- Manually review cutoff bubble in reports to identify missed patterns
- Direct corrections still work correctly, they just consume more space

### Platform Support

**QMK:**
- Pattern generation incomplete (see above)
- Output format complete but pattern optimization ongoing
- Suitable for testing but not yet production-ready

**General:**
- Pattern generalization only works for one boundary type per platform
- Large dictionaries (>20,000 entries) may take several minutes to generate

---

## Contributing

This project is in active development. Bug reports, feature requests, and pull requests are welcome!

Please check the [CHANGELOG.md](CHANGELOG.md) for planned features and known limitations.

---

## License

MIT License

Copyright © 2025 Adam Goldsmith

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.