# EntropPy

**Version 0.1.5 (Beta)** | [Changelog](CHANGELOG.md)

A Python-based autocorrect dictionary generator for the [Espanso](https://espanso.org/) text expander.

It uses `english-words` and `wordfreq` to algorithmically "fuzz" lists of English words, generating thousands of typos mapped to their correct spellings.

It generates five types of typing errors:
* **Transpositions**: Swapped characters (e.g., `the` → `teh`).
* **Omissions**: Missing characters (e.g., `because` → `becuse`).
* **Duplications**: Doubled characters (e.g., `entropy` → `entroppy`). 
* **Replacements**: Wrong characters (e.g., `apple` → `applw`).
* **Insertions**: Additional characters (e.g., `food` → `foopd`).

## Inspiration / Why Espanso?
This project originated as a tool for [QMK Firmware](https://qmk.fm/) and still has a [sibling for generating QMK dictionaries](https://github.com/ohshitgorillas/qmk_userspace/tree/main/autocorrect/ac_generator). I was dissatisfied with existing autocorrect dictionaries, which were bloated with spelling mistakes caused by genuine lack of knowledge rather than mechanical typing errors (e.g., `definately` → `definitely`). I know how to spell, I just have fat fingers.

After manually entering my own mistakes for a while, I realized I didn't need a pre-existing dictionary. I could generate an arbitrarily large corpus of typos algorithmically, which led to the creation of this project.

However, keyboard microcontrollers have limited storage capacity. My personal QMK keyboard can only store about 1,100 corrections, whereas this script can produce hundreds of thousands of unique corrections in 10–20 minutes. It quickly became clear that this project was overkill for QMK, so I searched for another platform to process these typos.

I immediately found Espanso, and it's perfect. Espanso runs on any OS at the host level and supports arbitrarily large dictionaries, making it the ideal platform for this project.

## Features

* **Smart Boundary Detection**: Automatically assigns Espanso word boundaries (`word: true`, `left_word: true`, etc.) to prevent typos from triggering inside other valid words (e.g., prevents `no` → `on` from triggering inside the word `noon`).
* **Collision Resolution**: If a typo maps to multiple valid words (e.g., `thn` could be `then`, `than`, or `thin`), the script uses frequency analysis to pick the statistically likely correction or discards it if ambiguous. (`then` and `than` are far more frequent than `thin`, but themselves have a frequency ratio close to 1, so `thn` is considered ambiguous and skipped.)
* **Pattern Generalization**: Automatically detects repeated patterns (e.g., `-atoin` → `-ation` and `-ntoin` → `-ntion` are simplified to `-toin` → `-tion`) and creates generalized rules, reducing dictionary size.
* **Comprehensive Reporting**: Generate detailed reports showing collisions, pattern decisions, substring conflicts, and performance metrics—invaluable for understanding and tuning EntropPy.
* **Espanso Optimization**: Outputs alphabetically organized YAML files to keep sizes manageable and organization clean.
* **Highly Configurable**: Customize input lists, exclusion patterns, adjacent key mappings, and frequency thresholds.
* **Progress Tracking**: Real-time progress bars for word processing, pattern generalization, conflict removal, and YAML file writing.
* **Estimates RAM Usage**: Estimates the total RAM consumed by the dictionary in Espanso (~21,500 entries → 1.5MB).

---

## Setup Instructions

### 1. Install Espanso
Follow the instructions for your OS at [espanso.org/install](https://espanso.org/install/).

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

### 3. Directory Structure
```text
project_root/
├── entroppy/           <-- The package directory
│   ├── __init__.py
│   ├── __main__.py
│   └── ... (other .py files)
├── corrections/        <-- Optional location to write corrections to
│   ├── typos_able_to_anyone.yml
│   ├── typos_baby_to_battery.yml
│   └── ...
│   └── typos_z.yml
├── examples/           <-- Example files
│   ├── adjacent.txt
│   ├── config.json
│   ├── exclude.txt
│   └── include.txt
├── reports/            <-- Optional Timestamped reports
│   ├── 2025-11-25_14-30-15/
│   │   ├── collisions.txt
│   │   ├── summary.txt
│   │   ├── patterns.txt
│   │   └── ...
│   └── ...
├── settings/           <-- Optional location for personalization files
│   ├── adjacent.txt
│   ├── config.json
│   ├── exclude.txt
│   └── include.txt
└── CHANGELOG.md
├── README.md           <-- This file
└── requirements.txt    <-- Dependencies
```

---

## Usage

It's recommended to generate the dictionaries into the local `corrections` folder for manual review before importing them into Espanso. A quick once-over of the reports to check for garbage corrections is sufficient.

Once you're satisfied with the generated corrections, copy the files to your Espanso configuration directory and restart Espanso.

### Basic Generation
Generate transpositions, omissions, and duplications for the top 1,000 most common English words and output to a local folder:

```bash
python -m entroppy --top-n 1000 --output corrections
```

Once you've reviewed the reports for issues, move the YAML files to Espanso and restart:

```bash
mkdir ~/.config/espanso/match/autocorrect
mv corrections/*.yml ~/.config/espanso/match/autocorrect
espanso restart
```

### Generating Directly to Espanso
You can output directly to your Espanso `match` directory.

**Linux/macOS:**
```bash
mkdir ~/.config/espanso/match/autocorrect
python -m entroppy --top-n 5000 --output "~/.config/espanso/match/autocorrect"
```

**Windows (PowerShell):**
```powershell
mkdir "$env:APPDATA\espanso\match\autocorrect"
python -m entroppy --top-n 5000 --output "$env:APPDATA\espanso\match\autocorrect"
```

### Advanced Usage
Generate typos using a custom word list, a specific "fat finger" key map, and exclude specific patterns:

```bash
python -m entroppy \
    --verbose \
    --top-n 2000 \
    --include settings/my_custom_words.txt \
    --exclude settings/exclusions.txt \
    --typo-freq-threshold 1e-8 \
    --max-word-length 12 \
    --adjacent-letters settings/qwerty_map.txt \
    --output corrections
```

Using `--typo-freq-threshold` is recommended to catch conjugations and other transformations of words that may not otherwise occur in `english-words`. The word `juts`, for example, both a transposition of `just` *and* a conjugation of the verb `jut`, does not occur in `english-words` (only `jut`), but does occur in `wordfreq` with a frequency of ~2e-7. Without this option, the script would (incorrectly) generate the correction `juts` → `just`. Lower values catch less common words.

### Generating Reports

Generate detailed reports to analyze what EntropPy is doing:

```bash
python -m entroppy \
    --top-n 5000 \
    --output corrections \
    --reports reports \
    --verbose
```

This creates a timestamped directory (e.g., `reports/2025-11-25_14-30-15/`) with:
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

Reports are invaluable for understanding EntropPy's decisions and fine-tuning your configuration.

---

## Configuration Options

You can configure EntropPy via Command Line Arguments or a `config.json` file.

### Command Line Arguments

| Argument | Default | Description |
| :--- | :--- | :--- |
| `--output`, `-o` | `None` | Directory to output YAML files. (Prints to stdout if omitted). |
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
| `--verbose`, `-v` | `False` | Print statistics, RAM estimates, and dropped typos. |

### JSON Configuration
Instead of long CLI strings, you can use a `config.json`:

```json
{
  "top_n": 5000,
  "output": "corrections",
  "reports": "reports",
  "min_typo_length": 4,
  "exclude": "settings/exclusions.txt",
  "adjacent_letters": "settings/qwerty.txt",
  "verbose": true
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
thn -> thin

# Block typos starting with 'in' from correcting to 'ni'
in* -> ni

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

The script generates multiple YAML files, organized alphabetically by the corrected words they contain. This keeps individual files compact and manageable. Use `--max-entries-per-file` (up to 1000) to generate fewer, larger files if preferred.

**Example YAML Entry:**
```yaml
matches:
  - trigger: wrod
    replace: word
    right_word: true    # Must be at the word end or isolated
    propagate_case: true

  - trigger: becuse
    replace: because
    left_word: true     # Must be at word start or isolated
    propagate_case: true

  - trigger: teh
    replace: the
    word: true          # Must be an isolated word
    propagate_case: true
```

---

## Boundary Detection

EntropPy automatically determines which boundary constraints are needed:

- **`word: true`** - Typo must be standalone (e.g., `tht` → `that`, but not inside `aththe`)
- **`left_word: true`** - Typo must be at word start (e.g., `hte` → `the` at start only)
- **`right_word: true`** - Typo must be at word end (e.g., `teh` → `the` at end only)
- **No boundary** - Typo can trigger anywhere (e.g., `taht` → `that`)

This prevents false corrections like `no` → `on` triggering inside `noon`.

---

## Pattern Generalization & Conflict Resolution

EntropPy employs sophisticated algorithms to optimize the dictionary and prevent garbage corrections. These optimizations are critical for ensuring Espanso's left-to-right, greedy matching behavior produces correct results.

### Pattern Generalization

When multiple corrections share a common suffix pattern, EntropPy attempts to create a single generalized rule instead of multiple specific corrections.

**Example - Valid Generalization:**
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

EntropPy validates each pattern by checking if Espanso's mechanics would produce the correct result:

```python
for each correction in pattern:
    remaining_prefix = full_typo[:-len(pattern_typo)]
    expected_result = remaining_prefix + pattern_correction
    
    if expected_result != full_word:
        reject_pattern()  # Would create garbage!
```

<!-- **Example - Rejected Pattern:**
```

``` -->

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

**Unsafe Simplification Example:**
```
Corrections:
  - aer → are
  - aerly → early

Analysis for "aerly":
  - Typing would trigger: aer → are
  - Remaining suffix: "ly"
  - Result: "aer" + "ly" = "arely" ✗ Wrong! (expected "early")
  
Action: Keep both corrections (not redundant - simplification would create garbage)
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

Use the `--reports` flag to see detailed information about:
- **`collisions.txt`**: Words that produce the same typo and their frequency ratios
- **`conflicts_*.txt`**: Corrections removed as redundant and the blocking pattern responsible for each removal
- **`patterns.txt`**: Which patterns were generalized and which were rejected (with reasons)
- **`stats.csv`**: Machine-readable statistics in CSV format for analysis and tracking performance over time
- **`summary.txt`**: Overall statistics showing how many patterns and conflicts were found


These reports can be invaluable for understanding EntropPy's decisions and verifying corrections.

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