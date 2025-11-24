# Autocorrect Dictionary Generator for Espanso

This is a Python module which generates a personalized autocorrect dictionary for use with the [Espanso](https://espanso.org/) text expander.

It uses `english-words` and `wordfreq` to algorithmically "fuzz" lists of English words, generating thousands of common "fat finger" typing errors mapped them to their correct spellings.

It generates the following types of typos:
* **Transpositions**: Swaps adjacent characters (e.g., `word` -> `wrod`).
* **Deletions**: Removes single characters (e.g., `because` -> `becuse`).
* **Duplication**: Duplicates each letter in the word (e.g., `word` -> `worrd`). 
* **Replacements**: Replaces a character with an adjacent key (e.g., `apple` -> `applw` via `e->w` map).
* **Insertions**: Inserts adjacent keys before/after target letters (e.g., `apple` -> `applew` via `e->w`).

## Inspiration / Why Espanso?

This project originated as a tool for [QMK Firmware](https://qmk.fm/) and still has a [sibling for generating QMK dictionaries](https://github.com/ohshitgorillas/qmk_userspace/tree/main/autocorrect/ac_generator). I was dissatisfied with existing autocorrect dictionaries, which were bloated with spelling mistakes caused by genuine lack of knowledge rather than mechanical typing errors (e.g., `definately -> definitely`). I know how to spell, I just have fat fingers.

After manually entering my own mistakes for a while, I realized I didn't need a pre-existing dictionary—I could generate an arbitrarily large corpus of typos algorithmically. This insight led to the creation of this project.

However, keyboard microcontrollers have limited storage capacity. My personal QMK keyboard can only store about 1,100 corrections, while we can algorithmically generate 20,000+ corrections in minutes. Espanso runs on the host OS and supports arbitrarily large dictionaries, making it the perfect platform for this comprehensive dataset.

## Features

* **Smart Boundary Detection**: Automatically assigns Espanso word boundaries (`word: true`, `left_word: true`, etc.) to prevent typos from triggering inside other valid words (e.g., prevents `no` -> `on` from triggering inside the word `noon`).
* **Collision Resolution**: If a typo maps to multiple valid words (e.g., `thn` could be `then`, `than`, or `thin`), the script uses frequency analysis to pick the statistically likely correction or discards it if it is ambiguous (`then` and `than` are far more frequent than `thin`, but themselves have a frequency ratio close to 1, so `thn` is considered ambiguous and skipped.)
* **Espanso Optimization**: Outputs split YAML files (`typos_a.yml`, `typos_b.yml`, etc.) to keep file sizes manageable and organization clean.
* **Highly Configurable**: Customize input lists, exclusion patterns, adjacent key mappings, and frequency thresholds.
* **Estimates RAM Usage**: Estimates the total RAM consumed by putting the dictionary in Espanso (~21,500 entries → 1.5MB).

---

## Setup Instructions

### 1. Install Espanso
Follow the instructions for your OS at [espanso.org/install](https://espanso.org/install/).

### 2. Environment Setup
It is recommended to run this generator inside a virtual environment:

```bash
# Clone the repository
git clone https://github.com/ohshitgorillas/autocorrect_generator_espanso.git /path/to/project

# Set up the virtual environment
cd /path/to/project
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt # install dependencies
```

### 3. Directory Structure
```text
project_root/
└── autocorr_generator/ <-- The package directory
    ├── __init__.py
    ├── __main__.py
    ├── ... (other .py files)
└── corrections         <-- recommended location to write corrections to
    ├── typos_a.yml
    ├── typos_b.yml
    ├── ...
└── examples            <-- example files
    ├── adjacent.txt
    ├── config.json
    ├── exclude.txt
    ├── include.txt
└── settings            <-- recommended location for personalization files
    ├── adjacent.txt    (optional)
    ├── config.json     (optional)
    ├── exclude.txt     (optional)
    ├── include.txt     (optional)
└── README.md           <-- this file
└── requirements.txt    <-- dependencies
```

---

## Usage

Run the script using the Python module syntax (`-m`) from the project root. It's recommended to generate the dictionaries into the local `corrections` folder for manual review before importing them into Espanso. A quick once-over is sufficient—you don't need to check all 10,000+ entries.

Once you're satisfied with the generated corrections, copy the files to your Espanso configuration directory and restart Espanso.

### Basic Generation
Generate transpositions, deletions, and duplications for the top 1,000 most common English words and output to a local folder:

```bash
python -m autocorr_generator --top-n 1000 --output ./my_typos
```

### generating directly to Espanso
You can output directly to your Espanso `match` directory.

**Linux/macOS:**
```bash
python -m autocorr_generator --top-n 5000 --output "$HOME/.config/espanso/match/autocorrect"
```

**Windows (PowerShell):**
```powershell
python -m autocorr_generator --top-n 5000 --output "$env:APPDATA\espanso\match\autocorrect"
```

### Advanced Usage
Generate typos using a custom word list, a specific "fat finger" key map, and exclude specific patterns:

```bash
python -m autocorr_generator \
    --verbose \
    --top-n 2000 \
    --include my_custom_words.txt \
    --exclude exclusions.txt \
    --typo-freq-threshold 1e-8 \
    --max-word-length 12 \
    --adjacent-letters qwerty_map.txt \
    --output ./espanso_matches \
```

Using `--typo-freq-threshold` is recommended to catch conjugations and other transformations of words that may not otherwise occur in `english-words`. The word `juts` for example, both a transposition of `just` *and* a conjugation of the verb `jut`, does not occur in `english-words` (only `jut`), but does occur in `wordfreq` with a frequency of ~2e-7. Without this option, the script would (incorrectly) generate the correction `juts -> just`.

---

## Configuration Options

You can configure the generator via Command Line Arguments or a `config.json` file.

| Argument | Default | Description |
| :--- | :--- | :--- |
| `--output`, `-o` | `None` | Directory to output YAML files. (Prints to stdout if omitted). |
| `--jobs`, `-j` | CPU Count | Number of parallel worker processes. |
| `--top-n` | `None` | Process the top N most frequent English words. |
| `--include` | `None` | Path to a file containing specific words to process. |
| `--exclude` | `None` | File containing exclusion patterns (see below). |
| `--adjacent-letters` | `None` | File mapping keys to neighbors for replacement/insertion typos. |
| `--freq-ratio` | `10.0` | Minimum frequency ratio required to resolve a collision. |
| `--min-typo-length` | `4` | Minimum length of a generated typo to be included. |
| `--min-word-length` | `3` | Minimum word length to generate typos for. |
| `--max-word-length` | `10` | Maximum word length to generate typos for. |
| `--typo-freq-threshold` | `0.0` | Skip typos with a `wordfreq` frequency above this. |
| `--verbose`, `-v` | `False` | Print statistics, RAM estimates, and dropped typos. |

### JSON Configuration
Instead of long CLI strings, you can use a `config.json`:

```json
{
  "top_n": 5000,
  "output": "~/.config/espanso/match/autocorrect",
  "min_typo_length": 4,
  "exclude_file": "exclusions.txt",
  "adjacent_letters": "qwerty.txt",
  "verbose": true
}
```

Run with:
```bash
python -m autocorr_generator --config config.json
```

---

## File Formats

### Adjacent Letters (`--adjacent-letters`)
Defines which keys are next to each other to generate **Replacement** and **Insertion** typos.
Format: `key -> neighbors`

```text
# QWERTY examples
a -> s
s -> ad
e -> wrd
```
* **Replacement:** `e -> w` generates `wxample` and `examplw` for `example`.
* **Insertion:** `e -> w` generates `wexample`, `ewxample`, `examplwe`, and `examplew`.

### Include File
Allows the user to specify words for which typos should be generated.

```text
# words to generate typos and corrections for
espanso
software
mechanical
keyboard
```

### Exclusion File (`--exclude-file`)
The script will not generate autocorrect rules for these correctly spelled words. Supports wildcards (`*`) and spaces (`:`).

```text
# Exact word exclusion
football    # not a sports fan

# Wildcards (skip word families)
pre*        # Skip words starting with pre

# The following wildcard prevents chemistry terms like "allantoin" from blocking the correction *toin -> tion.
*toin

# Pattern exclusion (prevents specific mapping)
in: -> ing  # Don't auto-correct "fixin " to "fixing"
```

---

## Output Structure

The script generates multiple YAML files organized by the starting letter of the **correct** word. This ensures Espanso can load them efficiently and allows for easier manual debugging.

```text
output_dir/
├── typos_a.yml
├── typos_b.yml
...
├── typos_z.yml
└── typos_symbols.yml
```

**Example YAML Entry:**
```yaml
  - trigger: wrod
    replace: word
    word: true  # match must be an isolated word; will not match inside other strings
```

## License

MIT License

Copyright © 2025 Adam Goldsmith