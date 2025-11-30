# EntropPy: Complete Algorithm Documentation

This document explains how EntropPy works, from loading dictionaries to generating the final autocorrect output. Each stage is explained with clear examples to illustrate the concepts.

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

**Example:**
```
Source words: ["the", "because", "entropy", "example"]
```

### Validation Dictionary

The validation dictionary is built from:

- **English words database** (`english-words` package with web2 and gcide)
- **Include file words** (added to validation set)
- **Exclude file patterns** (removed from validation set)

**Example:**
```
Validation dictionary includes: "the", "because", "entropy", "example", "onto", "information"
Validation dictionary excludes: words matching patterns in exclude file
```

### Adjacent Key Mapping

If provided, this maps each key to its adjacent keys on the keyboard.

**Example:**
```
Adjacent key map:
  a -> s
  s -> ad
  e -> wrd
  l -> k;
```

This is used to generate realistic typos (e.g., `example` → `examplw` when you hit `w` instead of `e`).

### Exclusion Patterns

Exclusions can filter out:
- **Words** from the validation dictionary (e.g., `*teh*` removes words containing "teh")
- **Corrections** from being generated (e.g., `entroppy -> entropy` blocks that specific correction)

**Example:**
```
Exclude file:
  *teh*          # Remove words containing "teh" from validation
  entroppy -> entropy  # Block this specific correction
```

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

Swaps each pair of adjacent characters.

**Example with "the":**
```
Original: t h e
Position 0-1: h t e → "hte"
Position 1-2: t e h → "teh"
```

**Example with "because":**
```
Original: b e c a u s e
Position 0-1: e b c a u s e → "ebcause"
Position 1-2: b c e a u s e → "bceause"
Position 2-3: b e a c u s e → "beacuse"
Position 3-4: b e c u a s e → "becuase"
Position 4-5: b e c a s u e → "becasue"
Position 5-6: b e c a u e s → "becaues"
```

#### 2. Omissions

Removes each character (only for words with 4+ characters).

**Example with "because":**
```
Remove position 0: "ecause"
Remove position 1: "bcause"
Remove position 2: "beause"
Remove position 3: "becuse"
Remove position 4: "becase"
Remove position 5: "becaue"
Remove position 6: "becaus"
```

**Example with "the":**
```
Skipped (word has only 3 characters, minimum is 4)
```

#### 3. Duplications

Doubles each character.

**Example with "the":**
```
Double position 0: "tthe"
Double position 1: "thhe"
Double position 2: "thee"
```

**Example with "entropy":**
```
Double position 0: "eentropy"
Double position 1: "enntropy"
Double position 2: "enttropy"
Double position 3: "entrropy"
Double position 4: "entroopy"
Double position 5: "entropyy"
Double position 6: "entropyy"
```

#### 4. Replacements

Replaces each character with adjacent keys (requires adjacent key map).

**Example with "example" (adjacent map: e->wrd, x->zc, a->s, m->n, p->o, l->k):**
```
Replace position 0 (e): "wxample", "rxample", "dxample"
Replace position 1 (x): "ezample", "ecample"
Replace position 2 (a): "exsmple", "exsmple"
Replace position 3 (m): "exanple", "exanple"
Replace position 4 (p): "examole", "examole"
Replace position 5 (l): "exampke", "exampke"
```

#### 5. Insertions

Inserts adjacent keys before or after each character.

**Example with "example" (adjacent map: e->wrd):**
```
After position 0: "ewxample", "erxample", "edxample"
Before position 0: "wexample", "rexample", "dexample"
After position 1: "exwxample", "exrxample", "exdxample"
Before position 1: "ewxample", "erxample", "edxample"
... (continues for each position)
```

### Filtering Generated Typos

Not all generated typos are kept. Each typo is checked:

1. **Is it the original word?** → Skip (e.g., `the` → `the` is useless)
2. **Is it a source word?** → Skip (don't correct valid source words)
3. **Is it in the validation dictionary?** → Skip (don't correct valid words)
4. **Is it explicitly excluded?** → Skip (user said no)
5. **Does it exceed frequency threshold?** → Skip (too common, might be a real word)

**Example:**
```
Word: "the"
Generated typo: "teh"
  ✓ Not the original word
  ✓ Not a source word
  ✓ Not in validation dictionary (if "teh" was excluded)
  ✓ Not explicitly excluded
  ✓ Frequency check passes
  → KEPT

Word: "the"
Generated typo: "thee"
  ✓ Not the original word
  ✓ Not a source word
  ✗ "thee" IS in validation dictionary (archaic form of "the")
  → SKIPPED (it's a valid word)
```

### Boundary Detection

For each valid typo, EntropPy determines what **boundaries** are needed to prevent false triggers.

**Boundary Types:**
- **NONE**: No boundaries - triggers anywhere (e.g., `teh` → `the`)
- **LEFT**: Left boundary only - must be at word start (e.g., `:teh` → `the`)
- **RIGHT**: Right boundary only - must be at word end (e.g., `teh:` → `the`)
- **BOTH**: Both boundaries - standalone word only (e.g., `:teh:` → `the`)

**How Boundaries Are Determined:**

1. Check if typo appears as a substring in other words
2. Check if typo appears as a prefix in validation dictionary
3. Check if typo appears as a suffix in validation dictionary

**Example 1: "teh" → "the"**
```
"teh" appears in "onto" (as substring)
"teh" does NOT appear as prefix in validation dictionary
"teh" does NOT appear as suffix in validation dictionary
→ Boundary: NONE (can trigger anywhere, but won't trigger in "onto" because "onto" is valid)
```

**Example 2: "toin" → "tion"**
```
"toin" appears in "information" (as suffix)
"toin" does NOT appear as prefix
"toin" DOES appear as suffix (in "information")
→ Boundary: LEFT (must be at word start, so "information" won't trigger)
```

**Example 3: "nto" → "not"**
```
"nto" appears in "onto" (as substring)
"nto" DOES appear as prefix (words starting with "nto")
"nto" DOES appear as suffix (words ending with "nto")
→ Boundary: BOTH (must be standalone word only)
```

**Example 4: "wriet" → "write"**
```
"wriet" does NOT appear in any validation words
"wriet" does NOT appear as prefix
"wriet" does NOT appear as suffix
→ Boundary: NONE (safe to trigger anywhere)
```

### Output of Stage 2

After processing all words, we have a **typo map**:

```
typo_map = {
  "teh": [("the", NONE)],
  "becuse": [("because", NONE)],
  "entropy": [("entropy", NONE)],  # Wait, this is a duplication typo!
  "examplw": [("example", NONE)],
  "toin": [("ton", NONE), ("tion", RIGHT)],  # Collision!
  ...
}
```

Notice that some typos map to multiple words - this is a **collision** that needs resolution.

---

## Stage 3: Collision Resolution

### What Happens

When multiple words map to the same typo, EntropPy must decide which correction to use (or skip it entirely).

### Collision Types

#### Single Word (No Collision)

**Example:**
```
typo: "teh"
words: [("the", NONE)]
→ No collision, keep: ("teh", "the", NONE)
```

#### Multiple Words (Collision)

**Example:**
```
typo: "toin"
words: [("ton", NONE), ("tion", RIGHT)]
→ Collision! Need to resolve
```

### Resolution Algorithm

1. **Calculate word frequencies** using `wordfreq`
2. **Compare frequencies** - if one word is much more common, use it
3. **Check frequency ratio** - if ratio is too low, skip (ambiguous)
4. **Apply boundary** - choose strictest boundary from all candidates
5. **Validate** - check length, exclusions, etc.

**Example 1: Clear Winner**
```
typo: "toin"
words: [("ton", NONE), ("tion", RIGHT)]

Frequencies:
  "ton": 1.2e-5
  "tion": 8.5e-4  (much more common!)

Ratio: 8.5e-4 / 1.2e-5 = 70.8
Threshold: 10.0
→ 70.8 > 10.0, so use "tion"
→ Boundary: RIGHT (strictest)
→ Result: ("toin", "tion", RIGHT)
```

**Example 2: Ambiguous (Skipped)**
```
typo: "abc"
words: [("abc", NONE), ("ab", NONE)]  # Hypothetical

Frequencies:
  "abc": 2.3e-6
  "ab": 1.8e-6

Ratio: 2.3e-6 / 1.8e-6 = 1.28
Threshold: 10.0
→ 1.28 < 10.0, too ambiguous
→ SKIPPED
```

**Example 3: User Word Override**
```
typo: "custom"
words: [("custom", NONE), ("costume", NONE)]

"custom" is in user_words (from include file)
→ Always prefer user words
→ Result: ("custom", "custom", NONE)
```

### Boundary Selection

When multiple boundaries exist for the same word, choose the **strictest**:

```
Boundary priority (strictest to least strict):
  BOTH > LEFT = RIGHT > NONE
```

**Example:**
```
typo: "riet"
words: [("rite", NONE), ("rite", LEFT)]

Both map to "rite", but different boundaries
→ Choose LEFT (strictest)
→ Result: ("riet", "rite", LEFT)
```

### Output of Stage 3

After collision resolution:

```
corrections = [
  ("teh", "the", NONE),
  ("becuse", "because", NONE),
  ("toin", "tion", RIGHT),
  ("examplw", "example", NONE),
  ...
]

skipped_collisions = [
  ("abc", ["abc", "ab"], 1.28),  # Too ambiguous
  ...
]

excluded_corrections = [
  ("entroppy", "entropy", "entroppy -> entropy"),  # User excluded
  ...
]
```

---

## Stage 4: Pattern Generalization

### What Happens

EntropPy looks for common patterns in corrections to reduce dictionary size. Instead of storing many similar corrections, it stores one pattern that matches multiple cases.

### Pattern Types

Patterns are extracted from the **end** of words (suffix patterns) for Espanso, or from the **beginning** (prefix patterns) for QMK, depending on the platform's matching direction.

#### Suffix Patterns (Espanso - Left-to-Right Matching)

**Example: Finding "-tion" → "-tion" Pattern**

```
Corrections:
  ("toin", "tion", RIGHT)
  ("atoin", "ation", RIGHT)
  ("etoin", "etion", RIGHT)
  ("itoin", "ition", RIGHT)

Pattern extraction:
  Length 4: Extract last 4 characters
  "toin" → pattern "toin" → "tion"
  "atoin" → pattern "toin" → "tion"  (last 4 chars)
  "etoin" → pattern "toin" → "tion"  (last 4 chars)
  "itoin" → pattern "toin" → "tion"  (last 4 chars)

Found pattern: ("toin", "tion", RIGHT)
  Replaces: 4 corrections
  Remaining parts match: "a" + "tion" = "ation", "e" + "tion" = "etion", etc.
```

**Example: Finding "-ly" → "-ly" Pattern**

```
Corrections:
  ("quikly", "quickly", RIGHT)
  ("slowly", "slowly", RIGHT)  # Wait, this is identical, skip
  ("reallly", "really", RIGHT)

Pattern extraction:
  Length 2: Extract last 2 characters
  "quikly" → pattern "ly" → "ly"  (identical, skip)
  "reallly" → pattern "ly" → "ly"  (identical, skip)

No pattern found (patterns must be different from correction)
```

**Example: Finding "-ing" → "-ing" Pattern**

```
Corrections:
  ("goin", "going", RIGHT)
  ("comin", "coming", RIGHT)
  ("workin", "working", RIGHT)

Pattern extraction:
  Length 4: Extract last 4 characters
  "goin" → pattern "goin" → "going"
  "comin" → pattern "omin" → "oming"  (last 4: "omin")
  "workin" → pattern "rkin" → "rking"  (last 4: "rkin")

No common pattern found (different endings)

Length 3: Extract last 3 characters
  "goin" → pattern "oin" → "oing"
  "comin" → pattern "min" → "ming"
  "workin" → pattern "kin" → "king"

No common pattern found

Length 2: Extract last 2 characters
  "goin" → pattern "in" → "ing"
  "comin" → pattern "in" → "ing"
  "workin" → pattern "in" → "ing"

Found pattern: ("in", "ing", RIGHT)
  Replaces: 3 corrections
  Remaining parts: "go" + "ing" = "going", "com" + "ing" = "coming", etc.
```

#### Prefix Patterns (QMK - Right-to-Left Matching)

**Example: Finding "th" → "th" Pattern**

```
Corrections:
  ("teh", "the", LEFT)
  ("thier", "their", LEFT)
  ("thign", "thing", LEFT)

Pattern extraction:
  Length 2: Extract first 2 characters
  "teh" → pattern "te" → "th"  (first 2: "te")
  "thier" → pattern "th" → "th"  (identical, skip)
  "thign" → pattern "th" → "th"  (identical, skip)

No pattern found

Actually, let's check if "th" appears as prefix:
  "thier" starts with "th" → "th"
  "thign" starts with "th" → "th"
  But "teh" doesn't start with "th"

No common pattern found
```

### Pattern Validation

Not all patterns are valid. Each pattern must:

1. **Work for all occurrences** - The pattern must correctly transform all matching typos
2. **Meet minimum length** - Pattern must be at least `min_typo_length` characters
3. **Not conflict with existing corrections** - Pattern's (typo, word) pair shouldn't already exist

**Example: Valid Pattern**
```
Pattern: ("in", "ing", RIGHT)
Occurrences:
  "goin" → "going": "go" + "ing" = "going" ✓
  "comin" → "coming": "com" + "ing" = "coming" ✓
  "workin" → "working": "work" + "ing" = "working" ✓
→ VALID
```

**Example: Invalid Pattern (Doesn't Work for All)**
```
Pattern: ("tion", "tion", RIGHT)  # Hypothetical
Occurrences:
  "toin" → "tion": "" + "tion" = "tion" ✓
  "atoin" → "ation": "a" + "tion" = "ation" ✓
  "etoin" → "etion": "e" + "tion" = "etion" ✗ (should be "etion" but pattern gives "etion")
→ INVALID (pattern doesn't work correctly)
```

**Example: Pattern Too Short**
```
Pattern: ("n", "ng", RIGHT)
Length: 1 character
min_typo_length: 5
→ REJECTED (too short)
```

### Pattern Collision Resolution

Patterns can also have collisions (multiple words for same pattern typo). These are resolved the same way as regular collisions.

**Example:**
```
Pattern typo: "in"
Words: [("ing", RIGHT), ("in", RIGHT)]  # Hypothetical collision

Frequencies:
  "ing": 5.2e-3
  "in": 8.1e-3

Ratio: 8.1e-3 / 5.2e-3 = 1.56
Threshold: 10.0
→ Too ambiguous, pattern rejected
```

### Cross-Boundary Deduplication

If a pattern's (typo, word) pair already exists as a direct correction (even with different boundary), the pattern is rejected and the direct corrections are kept.

**Example:**
```
Direct correction: ("toin", "tion", NONE)
Pattern: ("toin", "tion", RIGHT)

Pattern conflicts with direct correction
→ Pattern REJECTED
→ Direct correction KEPT
```

### Output of Stage 4

After pattern generalization:

```
corrections = [
  ("teh", "the", NONE),  # Not generalized
  ("becuse", "because", NONE),  # Not generalized
  ("in", "ing", RIGHT),  # PATTERN - replaces 3 corrections
  ...
]

patterns = [
  ("in", "ing", RIGHT),
  ...
]

pattern_replacements = {
  ("in", "ing", RIGHT): [
    ("goin", "going", RIGHT),
    ("comin", "coming", RIGHT),
    ("workin", "working", RIGHT),
  ],
  ...
}

rejected_patterns = [
  ("n", "ng", RIGHT, "Too short"),
  ...
]
```

---

## Stage 5: Conflict Removal

### What Happens

EntropPy removes corrections where one typo is a substring of another **with the same boundary**. This prevents shorter corrections from blocking longer ones.

### Why Conflicts Matter

When a text expansion tool sees a typo, it triggers on the **first match** (shortest, leftmost). If a shorter typo matches first, a longer one becomes unreachable.

**Example 1: Substring Conflict (Same Boundary)**
```
Corrections:
  ("teh", "the", NONE)
  ("tehir", "their", NONE)

When typing "tehir":
  Tool sees "teh" first → corrects to "the"
  User continues typing "ir" → gets "their"
  The "tehir" correction is UNREACHABLE
→ Remove "tehir"
```

**Example 2: Different Boundaries (No Conflict)**
```
Corrections:
  ("toin", "ton", NONE)
  ("toin", "tion", RIGHT)

These have DIFFERENT boundaries:
  "toin" (NONE) matches standalone "toin"
  "toin" (RIGHT) matches as suffix in "*toin"
→ Both can coexist, NO CONFLICT
```

**Example 3: Suffix Conflict (Same Boundary)**
```
Corrections:
  ("toin", "tion", RIGHT)
  ("atoin", "ation", RIGHT)

When typing "*atoin":
  Tool sees "toin" (RIGHT) first at end → corrects to "*ation"
  The "atoin" correction is REDUNDANT
→ Remove "atoin"
```

### Conflict Detection Algorithm

1. **Group by boundary type** - Process each boundary separately
2. **Sort by typo length** (shortest first)
3. **For each typo**, check if it's a substring of any longer typo
4. **If conflict found**, remove the longer typo
5. **Keep the shorter typo** (it blocks the longer one)

**Example:**
```
Corrections (all NONE boundary):
  ("teh", "the", NONE)
  ("tehir", "their", NONE)
  ("becuse", "because", NONE)
  ("becaus", "because", NONE)

Processing:
  Check "teh" (length 3):
    Is "teh" substring of "tehir"? YES → Remove "tehir"
    Is "teh" substring of "becuse"? NO
    Is "teh" substring of "becaus"? NO
  
  Check "becuse" (length 6):
    Is "becuse" substring of "becaus"? NO (different endings)
  
  Check "becaus" (length 6):
    Is "becaus" substring of "becuse"? NO (different endings)

Result:
  KEPT: ("teh", "the", NONE), ("becuse", "because", NONE), ("becaus", "because", NONE)
  REMOVED: ("tehir", "their", NONE)
```

### Pattern Updates from Conflicts

When a shorter correction blocks a longer one, the shorter correction becomes a **pattern** (if it wasn't already).

**Example:**
```
Before conflict removal:
  ("teh", "the", NONE)
  ("tehir", "their", NONE)

After conflict removal:
  ("teh", "the", NONE)  # Blocks "tehir"
  
Pattern update:
  Add ("teh", "the", NONE) to patterns
  Add ("tehir", "their", NONE) to pattern_replacements[("teh", "the", NONE)]
```

### Output of Stage 5

After conflict removal:

```
corrections = [
  ("teh", "the", NONE),
  ("becuse", "because", NONE),
  ("in", "ing", RIGHT),  # Pattern from Stage 4
  ...
]

removed_corrections = [
  ("tehir", "their", "teh", "the", NONE),  # Blocked by "teh"
  ...
]
```

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

**1. Character Set Filtering**
```
Input: ("exampl3", "example", NONE)
Check: "exampl3" contains "3" (not a-z or ')
→ FILTERED OUT

Input: ("exampl'", "example", NONE)
Check: "exampl'" contains "'" (allowed)
→ KEPT
```

**2. Same Typo Text Conflicts**
```
Input:
  ("riet", "rite", NONE)
  ("riet", "rite", LEFT)

QMK doesn't support boundaries, so both map to same typo
→ Keep least restrictive (NONE)
→ Remove LEFT boundary version
```

**3. Suffix Conflicts (RTL Matching)**
```
Input:
  ("riet", "rite", NONE)
  ("wriet", "write", NONE)

QMK scans right-to-left:
  When typing "wriet", finds "riet" first → "w" + "rite" = "write"
  So "wriet" is redundant
→ Remove "wriet"
```

**4. Substring Conflicts (QMK Hard Constraint)**
```
Input:
  ("beej", "beef", NONE)
  ("beejn", "begin", NONE)

QMK's compiler rejects any case where one typo is a substring of another
  "beej" is substring of "beejn"
→ Remove "beejn"
```

#### Espanso Filtering

Espanso has minimal filtering (mostly handled in earlier stages). It may filter based on:
- **Entry limits per file** - Splits into multiple files if needed
- **Character encoding** - Ensures valid UTF-8

### Platform Ranking

Corrections are ranked by usefulness:

1. **User words first** - Words from include file get highest priority
2. **Patterns ranked by coverage** - Patterns that replace more corrections rank higher
3. **Frequency-based** - More common words rank higher
4. **Length-based** - Shorter typos rank higher (catch errors earlier)

**Example Ranking (QMK):**
```
Corrections:
  ("teh", "the", NONE)           # Very common word
  ("becuse", "because", NONE)     # Common word
  ("custom", "custom", NONE)      # User word (from include file)
  ("in", "ing", RIGHT)            # Pattern replacing 3 corrections

Ranking:
  1. ("custom", "custom", NONE)      # User word (highest priority)
  2. ("in", "ing", RIGHT)             # Pattern (high coverage)
  3. ("teh", "the", NONE)            # Very common
  4. ("becuse", "because", NONE)     # Common
```

### Output of Stage 6

After platform filtering and ranking:

```
ranked_corrections = [
  ("custom", "custom", NONE),      # Rank 1
  ("in", "ing", RIGHT),            # Rank 2
  ("teh", "the", NONE),            # Rank 3
  ...
]

filter_metadata = {
  "filtered_count": 150,
  "suffix_conflicts": [...],
  "substring_conflicts": [...],
  ...
}
```

---

## Stage 7: Final Selection and Output

### What Happens

The final stage applies platform limits and generates output files.

### Applying Limits

If the platform has a `max_corrections` limit, truncate the ranked list.

**Example (QMK with max_corrections=1500):**
```
ranked_corrections: 2000 corrections
max_corrections: 1500
→ Take first 1500
→ final_corrections: 1500 corrections
```

### Output Generation

#### Espanso Output

Generates YAML files with corrections:

```yaml
# corrections/autocorrect_000.yml
matches:
  - trigger: "teh"
    replace: "the"
  
  - trigger: ":becuse"
    replace: "because"
    word: true
  
  - trigger: "goin:"
    replace: "going"
    right_word: true
```

#### QMK Output

Generates a text file with corrections:

```
# corrections/autocorrect.txt
teh the
becuse because
goin going
```

### Report Generation

If `--reports` is specified, generates detailed reports:

- **summary.txt** - Overview of processing
- **collisions.txt** - All collision resolutions
- **patterns.txt** - All patterns found
- **conflicts_*.txt** - Conflicts removed at each stage
- **statistics.csv** - Detailed statistics
- **Platform-specific reports** - QMK ranking, Espanso RAM estimates, etc.

---

## Complete Example: Processing "the"

Let's trace a single word through the entire pipeline:

### Input
```
Source word: "the"
Configuration:
  - Adjacent key map: e->wrd, t->ry, h->gj
  - Validation dictionary: ["the", "thee", "then", "there", "other", "another"]
  - Exclusions: []
```

### Stage 2: Typo Generation

**Generated typos:**
```
Transpositions:
  "hte" (swap t-h)
  "teh" (swap h-e)

Omissions:
  (skipped - word has only 3 characters)

Duplications:
  "tthe" (double t)
  "thhe" (double h)
  "thee" (double e)

Replacements:
  "rhe" (replace t->r)
  "tye" (replace h->y)
  "thw" (replace e->w)
  "thr" (replace e->r)
  "thd" (replace e->d)

Insertions:
  "rthe", "ythe", "dthe" (before t)
  "trhe", "tyhe", "tdhe" (after t)
  "thre", "thye", "thde" (after h)
  "ther", "they", "thed" (after e)
  ... (many more)
```

**Filtering:**
```
"the" → Skip (original word)
"thee" → Skip (in validation dictionary)
"then" → Skip (not generated, but if it were, would skip)
"other" → Skip (not generated)
"another" → Skip (not generated)

Kept:
  "hte" → "the"
  "teh" → "the"
  "tthe" → "the"
  "thhe" → "the"
  "rhe" → "the"
  "tye" → "the"
  "thw" → "the"
  "thr" → "the"
  "thd" → "the"
  ... (insertions)
```

**Boundary Detection:**
```
For "teh":
  Check if "teh" is substring: YES (in "other", "another")
  Check if "teh" is prefix: NO
  Check if "teh" is suffix: NO
  → Boundary: NONE (safe, won't trigger in "other" because "other" is valid)

For "hte":
  Check if "hte" is substring: NO
  → Boundary: NONE

For "tthe":
  Check if "tthe" is substring: NO
  → Boundary: NONE
```

**Output:**
```
typo_map = {
  "teh": [("the", NONE)],
  "hte": [("the", NONE)],
  "tthe": [("the", NONE)],
  "thhe": [("the", NONE)],
  ...
}
```

### Stage 3: Collision Resolution

**Processing:**
```
"teh" → [("the", NONE)]
  → Single word, no collision
  → Keep: ("teh", "the", NONE)

"hte" → [("the", NONE)]
  → Single word, no collision
  → Keep: ("hte", "the", NONE)
```

**Output:**
```
corrections = [
  ("teh", "the", NONE),
  ("hte", "the", NONE),
  ("tthe", "the", NONE),
  ...
]
```

### Stage 4: Pattern Generalization

**Pattern Finding:**
```
Check for suffix patterns (Espanso):
  "teh" → No common suffix pattern
  "hte" → No common suffix pattern
  "tthe" → No common suffix pattern

No patterns found (each correction is unique)
```

**Output:**
```
corrections = [
  ("teh", "the", NONE),
  ("hte", "the", NONE),
  ("tthe", "the", NONE),
  ...
]
patterns = []
```

### Stage 5: Conflict Removal

**Conflict Detection:**
```
Group by boundary (all NONE):
  Check "teh" (length 3):
    Is substring of "hte"? NO
    Is substring of "tthe"? NO
    Is substring of "thhe"? NO
    → No conflicts
  
  Check "hte" (length 3):
    Is substring of "tthe"? NO
    Is substring of "thhe"? NO
    → No conflicts
  
  Check "tthe" (length 4):
    Is "teh" substring? NO
    Is "hte" substring? NO
    → No conflicts

No conflicts found
```

**Output:**
```
corrections = [
  ("teh", "the", NONE),
  ("hte", "the", NONE),
  ("tthe", "the", NONE),
  ...
]
```

### Stage 6: Platform Filtering and Ranking

**QMK Filtering:**
```
All corrections pass character check (all letters)
All corrections have NONE boundary (QMK ignores boundaries anyway)
No suffix conflicts
No substring conflicts

All corrections kept
```

**Ranking:**
```
"the" is very common word
All corrections rank similarly (same target word)
Ranked by typo length (shorter first):
  1. "teh" (length 3)
  2. "hte" (length 3)
  3. "tthe" (length 4)
  ...
```

**Output:**
```
ranked_corrections = [
  ("teh", "the", NONE),
  ("hte", "the", NONE),
  ("tthe", "the", NONE),
  ...
]
```

### Stage 7: Final Selection

**Applying Limits:**
```
If max_corrections = 1500:
  Take first 1500 from ranked list
  (all "the" corrections fit)
```

**Output Generation:**
```
# QMK output
teh the
hte the
tthe the
...

# Espanso output
matches:
  - trigger: "teh"
    replace: "the"
  - trigger: "hte"
    replace: "the"
  - trigger: "tthe"
    replace: "the"
  ...
```

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

