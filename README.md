# EntropPy

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Version 0.6.0 (Beta)** | [Changelog](CHANGELOG.md)

A Python-based autocorrect dictionary generator for text expansion platforms. Algorithmically generates typos from English words and maps them to correct spellings, focusing on mechanical typing errors rather than spelling mistakes made from a lack of knowledge.

It uses `english-words` and `wordfreq` to algorithmically "fuzz" lists of English words, generating typos mapped to their correct spellings.

It generates five types of typing errors:
* **Transpositions**: Swapped characters (e.g., `the` → `teh`).
* **Omissions**: Missing characters (e.g., `because` → `becuse`).
* **Duplications**: Doubled characters (e.g., `entropy` → `entroppy`).
* **Replacements**: Wrong characters (e.g., `apple` → `applw`).
* **Insertions**: Additional characters (e.g., `thewre` → `there`).

## Inspiration
This project originated as a tool for [QMK Firmware](https://qmk.fm/)'s Autocorrect feature. I was dissatisfied with existing autocorrect dictionaries, which were bloated with spelling mistakes caused by genuine lack of knowledge rather than mechanical typing errors (e.g., `definately` → `definitely`). I know how to spell, I just have fat fingers.

After manually entering my own mistakes for a while, I realized I didn't need a pre-existing dictionary. I could generate an arbitrarily large corpus of typos algorithmically! This realization led to EntropPy, which is capable of generating an arbitrary number of autocorrect entries.

However, different platforms have different constraints. Keyboard firmware like QMK has limited storage to work with (my QMK keyboard stores ~1,100 corrections), while host-level tools like Espanso can handle hundreds of thousands of entries without lag. EntropPy generates corrections for multiple platforms, optimizing output for each platform's capabilities and constraints.

## Features

* **Multi-Platform Support**: Espanso, QMK, and extensible backend system
* **Smart Boundary Detection**: Prevents false triggers (e.g., `nto` → `not` won't trigger inside `onto` and produce `onot`)
* **Collision Resolution**: Frequency-based resolution of ambiguous typos
* **Pattern Generalization**: Reduces dictionary size by detecting repeated patterns
* **Platform-Specific Optimization**: Tailored output for each platform's constraints
* **Comprehensive Reports**: Detailed analysis of decisions and optimizations

## Documentation

For a complete explanation of EntropPy's algorithms and logic, from dictionary loading to final selection, see **[Algorithms](ALGORITHMS.md)**. This document provides detailed explanations with examples of how each stage of the pipeline works.

For information about processing efficiency, computational complexity, and optimizations, see **[Efficiency](EFFICIENCY.md)**. This document explains the big-O complexity of each processing stage and the optimizations applied to reduce processing time.


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
git clone https://github.com/ohshitgorillas/entroppy.git /path/to/entroppy

# Set up directories (optional)
mkdir corrections settings reports

# Set up the virtual environment
cd /path/to/entroppy
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install EntropPy
pip install -e .
```

---

## Usage

### Basic: Espanso

**Usage:**
```bash
entroppy --platform espanso --top-n 5000 --output corrections
```

**Strategy:**
- **Corrections**: Go wild—Espanso can handle hundreds of thousands. Processing time is your main constraint.
- **Top-N**: How much time do you have? Start with 5,000 and scale up as needed.
- **Adjacent Keys**: Use a comprehensive map including symbols and numbers. Espanso supports full Unicode.

**Deployment:**
```bash
# Linux/macOS
mkdir ~/.config/espanso/match/autocorrect
cp corrections/*.yml ~/.config/espanso/match/autocorrect/
espanso restart

# Windows (PowerShell)
mkdir "$env:APPDATA\espanso\match\autocorrect"
Copy-Item corrections\*.yml "$env:APPDATA\espanso\match\autocorrect\"
espanso restart
```

#### Basic: QMK

**Usage:**
```bash
entroppy --platform qmk --top-n 1000 --output corrections/autocorrect.txt --max-corrections 1500
```

**Strategy:**
- **Corrections**: Conservative—limited by flash memory.
- **Top-N**: Only need enough words to capture common patterns. Start with 500–1,000.
- **Adjacent Keys**: Be targeted—focus on letters and apostrophe only. QMK is limited to alphas + apostrophe.

**Deployment:**
Use the QMK CLI to generate the C file:

```bash
qmk generate-autocorrect-data corrections/autocorrect.txt
```
This will send the C file to your default keymap directory.

### Advanced

```bash
entroppy \
    --platform espanso \
    --top-n 5000 \
    --include settings/my_words.txt \
    --exclude settings/exclusions.txt \
    --adjacent-letters settings/qwerty_map.txt \
    --typo-freq-threshold 1e-8 \
    --output corrections \
    --reports reports \
    --verbose
```

**Note on `--typo-freq-threshold`**: This setting is tricky to use effectively. While it can help filter out rare legitimate words (like verb conjugations not in `english-words`), common typos often appear in `wordfreq` at similar frequencies to rare legitimate words:

**Common typos in wordfreq:**
- `teh` → `the`: 1.10e-06
- `thes` → `these`: 3.31e-07
- `adn` → `and`: 2.63e-07
- `taht` → `that`: 1.62e-07
- `recieve` → `receive`: 5.62e-07

**Rare legitimate words in wordfreq:**
- `juts` (conjugation of `jut`): 2.29e-07
- `jut`: 3.47e-07
- `jutted`: 6.31e-08
- `jutting`: 3.98e-07

Since common typos and rare legitimate words overlap in frequency (both around 1e-7 to 1e-6), setting a threshold too high will filter out valid typos you want to correct, while setting it too low won't filter out the rare words you want to exclude. Use this setting carefully and consider using exclusion patterns instead for more precise control.

### Logging
- **Default**: Warnings and errors only
- **`--verbose`**: Progress and statistics (recommended)
- **`--debug`**: Detailed debug info

### Debug Tracing

Trace specific words or typos through the pipeline (requires `--debug --verbose`):

```bash
# Trace specific words
entroppy --platform qmk --max-corrections 1000 --debug --verbose --debug-words "there,other" --top-n 1000 --output corrections/autocorrect.txt

# Trace typos with pattern matching
entroppy --platform qmk --max-corrections 1000 --debug --verbose --debug-typos "tehr,*toin:,abc*" --top-n 1000 --output corrections/autocorrect.txt
```

**Pattern syntax for `--debug-typos`:**
- `teh` - exact match
- `*tion` - wildcards (matches typos ending in "tion")
- `:teh` - left boundary only
- `teh:` - right boundary only
- `:teh:` - both boundaries

**Example output:**

Debug words show processing at each stage:
```
[DEBUG WORD: 'there'] [Stage 1] Included from wordfreq (rank: 34, zipf freq: 6.31)
[DEBUG WORD: 'there'] [Stage 2] Generated typo: htere → there
[DEBUG WORD: 'there'] [Stage 6] Ranked at position 1299/23648 (tier 2: direct corrections, score: 2.04e-03)
[DEBUG WORD: 'there'] [Stage 6] Cut off by max_corrections limit: position 1299 (limit: 1000)
```

Debug typos show ranking and selection:
```
[DEBUG TYPO: 'tehr' (matched: tehr)] [Stage 6] Ranked at position 220/23648 (tier 1: patterns, score: 2.16e-03)
[DEBUG TYPO: 'tehr' (matched: tehr)] [Stage 6] Made the cut: position 220 (within limit of 1000)
```

**Key fields:**
- **Tier 1**: Patterns (ranked first)
- **Tier 2**: Direct corrections (ranked second)
- **Position**: Overall rank (e.g., `220/23648`)
- **Made the cut**: Included in final output (within `--max-corrections` limit)

### Reports

Generate detailed reports:

```bash
entroppy --platform espanso --top-n 5000 --output corrections --reports reports --verbose
```

Creates timestamped directory with:
- **Universal**: `summary.txt`, `collisions.txt`, `patterns.txt`, `conflicts_*.txt`, `statistics.csv`
- **Platform-Specific**: RAM estimates (Espanso), cutoff analysis (QMK), filtering details

---

## Configuration

### Command Line Arguments

| Argument | Default | Description |
| :--- | :--- | :--- |
| `--platform` | `None` | Target platform |
| `--output`, `-o` | `None` | Output directory (stdout if omitted) |
| `--reports` | `None` | Reports directory |
| `--top-n` | `None` | Process top N most frequent words |
| `--include` | `None` | File with words to process |
| `--exclude` | `None` | Exclusion patterns file |
| `--adjacent-letters` | `None` | Adjacent key mappings |
| `--freq-ratio` | `10.0` | Min frequency ratio for collision resolution |
| `--min-typo-length` | `5` | Minimum typo length |
| `--min-word-length` | `3` | Minimum word length |
| `--max-word-length` | `10` | Maximum word length |
| `--typo-freq-threshold` | `0.0` | Skip typos above this frequency |
| `--max-entries-per-file` | `500` | Max corrections per YAML file |
| `--verbose`, `-v` | `False` | Verbose output |
| `--debug`, `-d` | `False` | Debug logging |

### JSON Configuration

```json
{
  "platform": "espanso",
  "top_n": 5000,
  "output": "corrections",
  "reports": "reports",
  "min_typo_length": 4,
  "exclude": "settings/exclusions.txt",
  "adjacent_letters": "settings/qwerty.txt",
  "verbose": true
}
```

Run with: `entroppy --config settings/config.json`

The JSON file supports all configuration options: convert `-` into `_`; e.g., `--typo-freq-threshold 1e-8` → `"typo_freq_threshold": 1e-8`.

---

## File Formats

### Adjacent Letters (`--adjacent-letters`)

Maps keys to neighbors for replacement/insertion typos:

```text
# The character you wanted -> the character you got
a -> s
s -> ad
e -> wrd
l -> k;
p -> o[0
```

This option is required to generate replacement and insertion typos.

- **Replacement**: `e -> w` generates `wxample`, `examplw` for `example`
- **Insertion**: `e -> w` generates `wexample`, `ewxample`, `examplwe`, `examplew`

Note that only Espanso currently supports numbers and non-apostrophe symbols; QMK is limited to letters and apostrophes only.

### Include File (`--include`)

One word per line:

```text
# Words to generate typos and corrections for; these can bypass the max length requirement
espanso
autocorrect
mechanical
keyboard
firmware
supercalifragilisticexpialidocious
```

### Exclusion File (`--exclude`)
Provides control over what corrections are generated and what words are considered valid. The file supports two types of rules:

**1. Word exclusions** (removes from validation dictionary):
```text
# Exclude words containing "teh" from the dictionary, allowing it to be a typo for "the".
*teh*

# Exclude any word ending in "ball".
*ball

# prevents chemistry terms like "cotoin" from blocking the generalization of "-toin" as a typo for "-tion".
*toin
```

**Tip**: When using both QMK and Espanso, use the autocorrect dictionary generated by EntropPy for QMK as an exclusion file for Espanso to prevent duplicate corrections.

#### 2. Correction Filtering
For fine-grained control, you can block specific `(typo, correction)` pairs using the `->` syntax. This supports wildcards and a special colon (`:`) syntax for word boundary requirements.

```text
entroppy -> entropy       # Exact match
xy* -> yz                 # Wildcards
*in: -> *ing              # With boundary: right boundary required
:in* -> ni*               # Left boundary required
:teh: -> the              # Both boundaries required
```

## Contributing

Bug reports, feature requests, and pull requests are welcome! See [CHANGELOG.md](CHANGELOG.md) for planned features.

---

## License

MIT License

Copyright © 2025 Adam Goldsmith
