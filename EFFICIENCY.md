# EntropPy Processing Efficiency

This document describes the computational complexity and optimizations applied throughout EntropPy's processing pipeline. It provides big-O complexity analysis for each stage and explains the optimizations that reduce processing time.

## Pipeline Overview

EntropPy processes words through nine main stages:

1. **Dictionary Loading** - Loads source words and validation dictionaries
2. **Typo Generation** - Creates typos from each word using five error types
3. **Candidate Selection** - Promotes raw typos to active corrections with boundary detection
4. **Pattern Generalization** - Finds common patterns to reduce dictionary size
5. **Conflict Removal** - Removes corrections that would interfere with each other
6. **Platform Substring Conflicts** - Detects cross-boundary substring conflicts
7. **Platform Constraints** - Applies platform-specific constraints
8. **Platform Ranking** - Ranks and filters corrections
9. **Output Generation** - Generates platform-specific output files

Stages 3-6 use an **Iterative Solver Architecture** that runs passes in sequence until convergence (no changes in a full iteration) or maximum iterations reached.

---

## Stage 1: Dictionary Loading

**Time Complexity**: O(W) where W = number of words in dictionaries

**Operations**:
- Load validation dictionary from `english-words` package: O(W)
- Load source words from `wordfreq` (top-N): O(N) where N = top-N value
- Load user words from include file: O(U) where U = user words
- Build exclusion matcher: O(E) where E = exclusion patterns

**Optimizations**:
- **Set-based lookups**: Validation and source words stored as sets for O(1) membership testing

**Note**: `BoundaryIndex` is not built during this stage; it's built later during iterative solver initialization (Stage 3-6 setup) to provide O(1) prefix/suffix/substring lookups.

**Total**: O(W + N + U + E) - linear in input size

---

## Stage 2: Typo Generation

**Time Complexity**: O(W × L × K) where:
- W = number of source words
- L = average word length
- K = average number of adjacent keys per character

**Operations per word**:
1. **Transpositions**: O(L) - Swap each adjacent pair
2. **Omissions**: O(L) - Remove each character (for words ≥ 4 chars)
3. **Duplications**: O(L) - Double each character
4. **Replacements**: O(L × K) - Replace with K adjacent keys at each position
5. **Insertions**: O(L × K) - Insert K adjacent keys at each position

**Total complexity per word**: O(L × K)

**Optimizations**:
- **Multiprocessing**: When `jobs > 1`, words are processed in parallel using `multiprocessing.Pool`
  - Linear speedup proportional to CPU cores
  - Worker context pre-initialized to avoid repeated setup overhead
- **Early validation**: Typos are validated against validation set immediately to avoid generating invalid candidates
- **Frequency threshold filtering**: Typos above `typo_freq_threshold` are skipped to avoid generating corrections for valid words

**Note**: BoundaryIndex is not built during this stage; it's built later during iterative solver initialization.

**Total**: O(W × L × K) with parallel speedup factor of P (number of CPU cores)

---

## Stage 3-6: Iterative Solver

The iterative solver runs multiple passes in sequence until convergence. Each pass can modify the state, and the solver continues until no changes occur in a full iteration.

**Convergence**: Typically 1-3 iterations for most datasets

**Passes** (run in order each iteration):
1. CandidateSelectionPass
2. PatternGeneralizationPass
3. ConflictRemovalPass
4. PlatformSubstringConflictPass
5. PlatformConstraintsPass

---

### Pass 1: Candidate Selection

**Time Complexity**: O(T × B) where:
- T = number of unique typos in raw typo map
- B = average number of boundary attempts per typo (typically 1-4)

**Operations**:
- Iterate through raw typos: O(T)
- For each typo:
  - Collision resolution (if multiple words): O(M log M) where M = number of competing words
  - Boundary determination: O(1) using pre-built `BoundaryIndex`
  - False trigger check: O(1) using `BoundaryIndex` lookups
  - Try boundaries in order (NONE → LEFT/RIGHT → BOTH): O(B)

**Optimizations**:
- **Multiprocessing**: When `jobs > 1` and number of uncovered typos > 100, typos are processed in parallel
  - Chunks are created (4 chunks per worker for load balancing)
  - Worker context pre-initialized with coverage and graveyard sets
- **Boundary index**: Pre-built `BoundaryIndex` provides O(1) lookups for:
  - Substring checks: `typo in index.substring_set`
  - Prefix checks: `typo in index.prefix_index`
  - Suffix checks: `typo in index.suffix_index`
- **Graveyard tracking**: Failed corrections stored in graveyard to prevent infinite retry loops
- **Coverage checking**: Typos already covered by active corrections/patterns are skipped

**Total**: O(T × B) with parallel speedup, typically O(T) since B ≈ 1-2 for most typos

---

### Pass 2: Pattern Generalization

**Time Complexity**: O(C × P) where:
- C = number of active corrections
- P = average number of pattern lengths to check per correction

**Operations**:
- Extract patterns from each correction: O(P) per correction
  - Try pattern lengths from max down to minimum (typically 2-5 lengths)
  - For each length, extract prefix/suffix patterns
- Group patterns by (typo_pattern, word_pattern, boundary): O(C)
- Find patterns with 2+ occurrences: O(C)
- Validate patterns against validation set: O(V) where V = patterns to validate

**Optimizations**:
- **Pattern extraction cache**: Results cached across iterations to avoid re-extraction
  - Cache key: `(typo, word, boundary, is_suffix)`
  - Cache hit rate: High in later iterations when corrections stabilize
- **Multiprocessing for validation**: Pattern validation uses parallel workers when `jobs > 1` and number of patterns to validate > 10
- **Source word index**: `SourceWordIndex` pre-built for O(1) corruption checks
  - RTL patterns: indexes prefixes at word boundaries
  - LTR patterns: indexes suffixes at word boundaries
- **Correction index**: `CorrectionIndex` provides O(1) lookups for pattern conflicts
  - Uses `startswith`/`endswith` checks (O(n) where n = correction count, but n << all substrings)

**Total**: O(C × P + V) with caching reducing work in later iterations

---

### Pass 3: Conflict Removal

**Time Complexity**: O(N log N + N × K) where:
- N = number of active corrections + patterns
- K = average number of substring checks per typo (typically small, < 10)

**Operations**:
- Group corrections by boundary type: O(N)
- For each boundary group:
  - Sort typos by length: O(N log N)
  - Build character-based index: O(N)
  - For each typo (in length order):
    - Check against shorter typos using index: O(K) where K = candidates sharing index character
    - Substring check: O(M) where M = typo length (Python's `in` operator)

**Optimizations**:
- **Character-based indexing**: Uses `candidates_by_char` dict for O(1) lookups instead of O(N) linear search
  - Prefix conflicts: index by first character
  - Suffix conflicts: index by last character
- **Multiprocessing**: When `jobs > 1` and `N >= 100`, boundary groups are processed in parallel
  - Large groups (>1000 corrections) are sharded by first character for better parallelization
- **Length-based sorting**: Process shorter typos first to enable early termination
- **Conflict detector abstraction**: Different detectors for different boundary types optimize substring checks

**Total**: O(N log N + N × K) per boundary group with parallel speedup

---

### Pass 4: Platform Substring Conflicts

**Time Complexity**: O(N log N + N × K) where:
- N = number of active corrections + patterns
- K = average number of substring checks per formatted typo

**Operations**:
- Format corrections with platform-specific boundary markers: O(N)
- Sort formatted typos by length: O(N log N)
- For each longer formatted typo:
  - Check against all shorter formatted typos: O(K) where K = number of shorter typos
  - Substring check: O(M) where M = formatted typo length

**Optimizations**:
- **TypoIndex-style algorithm**: Processes typos in length order with dict-based tracking
  - Maintains `shorter_formatted` dict for O(1) lookup of shorter typos
  - Single pass through sorted typos instead of nested loops
- **Multiprocessing**: Formatting phase parallelized when `jobs > 1` and `N >= 100`
  - **Note**: Conflict detection phase cannot be parallelized due to sequential data dependencies
  - Each longer typo depends on all shorter typos being processed first
  - See `PLATFORM_SUBSTRING_CONFLICTS_PARALLELIZATION.md` for detailed explanation
- **Cached formatting results**: Formatted typos stored to avoid redundant formatting calls
- **Conflict pair storage**: Conflict pairs stored during detection to eliminate O(N²) debug logging phase

**Total**: O(N log N + N × K) - improved from previous O(N²) implementation

---

### Pass 5: Platform Constraints

**Time Complexity**: O(N) where N = number of active corrections + patterns

**Operations**:
- Iterate through corrections: O(N)
- For each correction:
  - Character set validation: O(L) where L = typo/word length
  - Length constraint checks: O(1)
  - Boundary support checks: O(1)

**Optimizations**:
- **Single pass**: All constraint checks performed in one iteration
- **Early termination**: Invalid corrections removed immediately

**Total**: O(N × L) where L is typically small (average word length ~5-10)

---

## Stage 7: Platform Ranking

**Time Complexity**: O(N log N) where N = number of corrections to rank

**Operations**:
- Separate corrections by type (user words, patterns, direct): O(N)
- Score patterns: O(P) where P = number of patterns
  - Sum word frequencies for pattern replacements: O(R) where R = total replacements
- Score direct corrections: O(D) where D = number of direct corrections
  - Word frequency lookup: O(1) using pre-computed cache
- Sort by score: O(N log N)

**Optimizations**:
- **Word frequency cache**: Pre-computed cache provides O(1) lookups instead of O(1) API calls with overhead
- **Lazy pattern scoring**: Patterns scored only when needed, not all at once
- **Separate tier sorting**: Corrections sorted within tiers (user words, patterns, direct) for better ranking
- **Cached pattern sets**: Pattern typo sets and replacement sets cached to avoid repeated computation

**Total**: O(N log N) - dominated by sorting step

---

## Stage 8: Output Generation

**Time Complexity**: O(N) where N = number of final corrections

**Operations**:
- Iterate through final corrections: O(N)
- Format each correction for platform: O(L) where L = average correction length
- Write to output file(s): O(N)

**Optimizations**:
- **Batch writing**: Corrections written in batches to reduce I/O overhead
- **Platform-specific formatting**: Efficient formatting logic per platform

**Total**: O(N × L) where L is typically small

---

## Stage 9: Report Generation

**Time Complexity**: O(N + C + P) where:
- N = number of corrections
- C = number of collisions
- P = number of patterns

**Operations**:
- Extract data from solver state: O(N)
- Generate collision reports: O(C)
- Generate pattern reports: O(P)
- Write report files: O(N + C + P)

**Total**: O(N + C + P) - linear in output size

---

## Overall Complexity

**Worst-case time complexity**: O(W × L × K + T × B + C × P + N log N)

Where:
- W = number of source words
- L = average word length
- K = average adjacent keys per character
- T = number of unique typos
- B = average boundary attempts
- C = number of corrections
- P = average pattern lengths
- N = final correction count

**Typical case**: Most stages are linear or near-linear, with sorting operations (O(N log N)) being the main non-linear component.

**Space complexity**: O(W + T + C + P) - dominated by storing words, typos, corrections, and patterns

---

## Key Optimizations Summary

1. **Multiprocessing**: Stages 2, 3, 4, 5, and 6 use parallel processing when `jobs > 1` and thresholds are met
   - Stage 2 (Typo Generation): Always uses multiprocessing when `jobs > 1`
   - Stage 3 (Candidate Selection): Uses multiprocessing when uncovered typos > 100
   - Stage 4 (Pattern Generalization): Uses multiprocessing for validation when patterns > 10
   - Stage 5 (Conflict Removal): Uses multiprocessing when corrections >= 100
   - Stage 6 (Platform Substring Conflicts): Only formatting phase uses multiprocessing when corrections >= 100
     - Conflict detection phase cannot be parallelized due to sequential data dependencies
     - See `PLATFORM_SUBSTRING_CONFLICTS_PARALLELIZATION.md` for detailed explanation
   - Linear speedup proportional to CPU cores
   - Worker context pre-initialized to minimize overhead

2. **Indexing Structures**:
   - `BoundaryIndex`: O(1) prefix/suffix/substring lookups
   - `SourceWordIndex`: O(1) source word corruption checks
   - `CorrectionIndex`: O(1) pattern conflict checks
   - Character-based indexes: O(1) conflict candidate lookups

3. **Caching**:
   - Pattern extraction cache: Avoids re-extraction across iterations
   - Word frequency cache: O(1) lookups instead of API calls
   - Formatted typo cache: Eliminates redundant formatting

4. **Algorithmic Improvements**:
   - TypoIndex-style conflict detection: O(N log N) instead of O(N²)
   - Length-based sorting: Enables early termination
   - Single-pass algorithms: Reduce multiple iterations

5. **Early Termination**:
   - Coverage checking: Skip already-covered typos
   - Graveyard tracking: Prevent infinite retry loops
   - Invalid correction filtering: Remove early to reduce work

---

## Notes

- Complexity analysis assumes typical English word lengths (3-10 characters)
- Adjacent key mappings typically have 2-5 keys per character
- Most typos resolve with 1-2 boundary attempts
- Pattern extraction typically finds 2-5 valid pattern lengths per correction
- Conflict detection typically checks 1-10 candidates per typo (due to character-based indexing)
