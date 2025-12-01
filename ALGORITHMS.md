# EntropPy: Complete Algorithm Documentation

This document explains how EntropPy works, from loading dictionaries to generating the final autocorrect output.

---

## Overview: The Complete Pipeline

EntropPy processes words through seven main stages:

1. **Dictionary Loading** - Loads source words and validation dictionaries
2. **Typo Generation** - Creates typos from each word using five error types
3. **Collision Resolution** - Resolves when multiple words map to the same typo
4. **Pattern Generalization** - Finds common patterns to reduce dictionary size
5. **Conflict Removal** - Removes corrections that would interfere with each other
6. **Platform Filtering** - Applies platform-specific constraints
7. **Final Selection** - Ranks and selects the best corrections

Let's walk through each stage in detail.

---

## Stage 1: Dictionary Loading

### What Happens

EntropPy loads three types of data:

1. **Source Words** - The words to generate typos from
2. **Validation Dictionary** - Words that are considered "valid" (typos shouldn't match these)
3. **Configuration** - Adjacent key mappings, exclusions, etc.

### Source Words

Source words come from two places:

- **Top-N from wordfreq**: The most common English words (e.g., `--top-n 5000`)
- **Include file**: Custom words you specify (e.g., `--include my_words.txt`)

### Validation Dictionary

The validation dictionary is built from:

- **English words database** (`english-words` package with web2 and gcide)
- **Include file words** (added to validation set)
- **Exclude file patterns** (removed from validation set)

### Adjacent Key Mapping

If provided, this maps each key to its adjacent keys on the keyboard. This is used to generate realistic typos based on keyboard layout.

### Exclusion Patterns

Exclusions can filter out:
- **Words** from the validation dictionary (using wildcard patterns like `*teh*`)
- **Corrections** from being generated (using `typo -> word` syntax)

---

## Stage 2: Typo Generation

### What Happens

For each source word, EntropPy generates typos using five algorithms:

1. **Transpositions** - Swapped adjacent characters
2. **Omissions** - Missing characters
3. **Duplications** - Doubled characters
4. **Replacements** - Wrong characters (requires adjacent key map)
5. **Insertions** - Extra characters (requires adjacent key map)

### Algorithm Details

#### 1. Transpositions

Swaps each pair of adjacent characters. For a word of length n, generates n-1 typos.

#### 2. Omissions

Removes each character (only for words with 4+ characters). For a word of length n, generates n typos.

#### 3. Duplications

Doubles each character. For a word of length n, generates n typos.

#### 4. Replacements

Replaces each character with adjacent keys (requires adjacent key map). For each character that has adjacent keys mapped, generates one typo per adjacent key.

#### 5. Insertions

Inserts adjacent keys before or after each character (requires adjacent key map). For each character that has adjacent keys mapped, generates two typos per adjacent key (one before, one after).

### Filtering Generated Typos

Not all generated typos are kept. Each typo is checked:

1. **Is it the original word?** → Skip
2. **Is it a source word?** → Skip
3. **Is it in the validation dictionary?** → Skip
4. **Is it explicitly excluded?** → Skip
5. **Does it exceed frequency threshold?** → Skip (too common, might be a real word)

### Boundary Detection

For each valid typo, EntropPy determines what **boundaries** are needed to prevent false triggers.

**Boundary Types:**
- **NONE**: No boundaries - triggers anywhere
- **LEFT**: Left boundary only - must be at word start
- **RIGHT**: Right boundary only - must be at word end
- **BOTH**: Both boundaries - standalone word only

**How Boundaries Are Determined:**

1. Check if typo appears as a substring in validation or source words
2. If not a substring → **NONE** (safe anywhere)
3. If a substring:
   - Check if typo appears as prefix (word starts with typo)
   - Check if typo appears as suffix (word ends with typo)
   - Prefix only → **RIGHT** boundary
   - Suffix only → **LEFT** boundary
   - Both prefix and suffix → **BOTH** boundaries
   - Neither (middle only) → **BOTH** boundaries

Notice that some typos map to multiple words - this is a **collision** that needs resolution in the next stage.

---

## Stage 3: Collision Resolution

### What Happens

When multiple words map to the same typo, EntropPy must decide which correction to use (or skip it entirely).

### Collision Types

#### Single Word (No Collision)

When only one word maps to a typo, that correction is kept.

#### Multiple Words (Collision)

When multiple words map to the same typo, collision resolution is needed.

### Resolution Algorithm

1. **Calculate word frequencies** using `wordfreq`
2. **Compare frequencies** - if one word is much more common, use it
3. **Check frequency ratio** - if ratio is too low, skip (ambiguous)
4. **Apply boundary** - choose strictest boundary from all candidates
5. **Validate** - check length, exclusions, etc.

User words (from include file) always take priority over frequency-based selection.

### Boundary Selection

When multiple boundaries exist for the same word, choose the **strictest**:

Boundary priority (strictest to least strict):
  BOTH > LEFT = RIGHT > NONE

---

## Stage 4: Pattern Generalization

### What Happens

EntropPy looks for common patterns in corrections to reduce dictionary size. Instead of storing many similar corrections, it stores one pattern that matches multiple cases.

### Pattern Types

Patterns are extracted from the **end** of words (suffix patterns) for Espanso, or from the **beginning** (prefix patterns) for QMK, depending on the platform's matching direction.

#### Suffix Patterns (Espanso - Left-to-Right Matching)

Patterns are extracted from the end of words. The algorithm tries different suffix lengths, starting from the longest possible and working down. A pattern is found when multiple corrections share the same typo suffix and word suffix, and their remaining parts match.

#### Prefix Patterns (QMK - Right-to-Left Matching)

Prefix patterns work similarly but extract from the beginning of words. They're less common because typos at word starts are rarer.

### Pattern Validation

Not all patterns are valid. Each pattern must:

1. **Work for all occurrences** - The pattern must correctly transform all matching typos
2. **Meet minimum length** - Pattern must be at least `min_typo_length` characters
3. **Not conflict with existing corrections** - Pattern's (typo, word) pair shouldn't already exist

### Pattern Collision Resolution

Patterns can also have collisions (multiple words for same pattern typo). These are resolved the same way as regular collisions using frequency ratios.

### Cross-Boundary Deduplication

If a pattern's (typo, word) pair already exists as a direct correction (even with different boundary), the pattern is rejected and the direct corrections are kept.

---

## Stage 5: Conflict Removal

### What Happens

EntropPy removes corrections where one typo is a substring of another **with the same boundary**. This prevents shorter corrections from blocking longer ones.

### Why Conflicts Matter

When a text expansion tool sees a typo, it triggers on the **first match** (shortest, leftmost). If a shorter typo matches first, a longer one becomes unreachable. Conflicts only occur when corrections share the same boundary type.

### Conflict Detection Algorithm

1. **Group by boundary type** - Process each boundary separately
2. **Sort by typo length** (shortest first)
3. **For each typo**, check if it's a substring of any longer typo
4. **If conflict found**, remove the longer typo
5. **Keep the shorter typo** (it blocks the longer one)

### Pattern Updates from Conflicts

When a shorter correction blocks a longer one, the shorter correction becomes a **pattern** (if it wasn't already), and the blocked correction is added to its replacements.

---

## Stage 6: Platform-Specific Filtering and Ranking

### What Happens

Each platform (Espanso, QMK) has different constraints and capabilities. This stage applies platform-specific filtering and ranks corrections by usefulness.

### Platform Constraints

#### Espanso Constraints
- **No character limits** - Supports full Unicode
- **No correction limits** - Can handle hundreds of thousands
- **Supports boundaries** - LEFT, RIGHT, BOTH, NONE
- **Left-to-right matching** - Matches from start of word

#### QMK Constraints
- **Character limits** - Only letters (a-z) and apostrophe (')
- **Correction limits** - Limited by flash memory (typically ~1,100)
- **No boundaries** - QMK doesn't support boundary constraints
- **Right-to-left matching** - Matches from end of word

### Platform Filtering

#### QMK Filtering

**1. Character Set Filtering** - Removes corrections containing characters other than a-z and apostrophe.

**2. Same Typo Text Conflicts** - When the same typo text appears with different boundaries, keeps the least restrictive (NONE) since QMK doesn't support boundaries.

**3. Suffix Conflicts (RTL Matching)** - QMK scans right-to-left, so shorter suffix typos make longer ones redundant.

**4. Substring Conflicts (QMK Hard Constraint)** - QMK's compiler rejects any case where one typo is a substring of another, regardless of position.

#### Espanso Filtering

Espanso has minimal filtering (mostly handled in earlier stages). It splits corrections into multiple YAML files if they exceed the `max_entries_per_file` limit.

### Platform Ranking

Corrections are ranked by usefulness:

1. **User words first** - Words from include file get highest priority
2. **Patterns ranked by coverage** - Patterns that replace more corrections rank higher
3. **Frequency-based** - More common words rank higher
4. **Length-based** - Shorter typos rank higher (catch errors earlier)


---

## Stage 7: Final Selection and Output

### What Happens

The final stage applies platform limits and generates output files.

### Applying Limits

If the platform has a `max_corrections` limit, truncate the ranked list to that limit.

### Output Generation

#### Espanso Output

Generates YAML files with corrections, including boundary markers (`:` for boundaries) and splitting into multiple files if needed.

#### QMK Output

Generates a text file with corrections in the format `typo word`, one per line.

### Report Generation

If `--reports` is specified, generates detailed reports including summaries, collision resolutions, patterns, conflicts, statistics, and platform-specific analysis.

---

## Key Algorithms Summary

### Typo Generation Algorithms

1. **Transpositions**: `O(n)` - Swap each adjacent pair
2. **Omissions**: `O(n)` - Remove each character (n≥4)
3. **Duplications**: `O(n)` - Double each character
4. **Replacements**: `O(n×k)` - Replace with k adjacent keys
5. **Insertions**: `O(n×k)` - Insert k adjacent keys at each position

**Total complexity per word**: `O(n×k)` where n=word length, k=avg adjacent keys

### Collision Resolution

**Algorithm**: Frequency-based selection with ratio threshold
- **Time**: `O(m log m)` where m=number of competing words
- **Space**: `O(m)`

### Pattern Generalization

**Algorithm**: Sliding window pattern extraction
- **Time**: `O(n×m)` where n=corrections, m=avg word length
- **Space**: `O(n×m)`

### Conflict Removal

**Algorithm**: Substring matching with boundary grouping
- **Time**: `O(n²×m)` where n=corrections, m=avg typo length
- **Space**: `O(n)`

---

## Conclusion

EntropPy's pipeline transforms a list of words into an optimized autocorrect dictionary through seven carefully designed stages. Each stage addresses specific challenges:

- **Stage 2** generates realistic typos
- **Stage 3** resolves ambiguities
- **Stage 4** reduces dictionary size
- **Stage 5** prevents interference
- **Stage 6** optimizes for platform constraints
- **Stage 7** produces final output

The result is a high-quality autocorrect dictionary tailored to your platform's capabilities and constraints.

