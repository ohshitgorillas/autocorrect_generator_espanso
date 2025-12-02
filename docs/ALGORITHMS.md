# EntropPy Algorithms and Architecture

## Overview

EntropPy uses a sophisticated pipeline to generate typo corrections that work reliably across different text expansion platforms. As of version 0.6.0, the core optimization engine uses an **Iterative Solver Architecture** that can backtrack and self-heal when conflicts arise.

## Pipeline Architecture

### Stages 1-2: Data Preparation

#### Stage 1: Dictionary Loading
- Loads validation dictionaries, source words, and exclusion patterns
- Builds boundary detection indices for efficient lookups
- Prepares adjacent letter mappings for typo generation

#### Stage 2: Typo Generation
- Generates candidate typos using various error simulation methods:
  - Character transpositions (adjacent swaps)
  - Character substitutions (using QWERTY keyboard proximity)
  - Character deletions
  - Character insertions
- Produces a "raw typo map": `typo -> [possible_words]`

### Stages 3-6: Iterative Solver (New in v0.6.0)

The iterative solver replaces the linear stages 3-6 with a convergence-based approach that can backtrack and retry alternatives when conflicts arise.

#### Core Concept

Instead of making irrevocable decisions in early stages, the solver treats dictionary optimization as a **convergence problem**. If a correction is rejected by a later stage (e.g., due to conflicts), earlier stages can propose alternative versions (e.g., using stricter boundaries) in the next iteration.

#### Architecture Components

##### 1. DictionaryState

The centralized "Source of Truth" that manages:

- **Raw Typo Map**: The input from Stage 2 (`typo -> [possible_words]`)
- **Active Corrections**: Current set of valid `(typo, word, boundary)` tuples
- **Active Patterns**: Generalized pattern rules
- **The Graveyard**: Registry of rejected corrections
  - Key: `(typo, word, boundary)`
  - Value: `RejectionReason` and blocker information
  - **Critical**: Prevents infinite loops by remembering failed attempts

##### 2. IterativeSolver

The orchestrator that runs passes in sequence until convergence:

```python
iteration = 0
while state.is_dirty and iteration < MAX_ITERATIONS:
    state.start_iteration()

    for pass in passes:
        pass.run(state)

    iteration += 1
```

Convergence occurs when no changes are made in a complete iteration.

##### 3. The Passes

###### A. CandidateSelectionPass (Refactored Stage 3)

**Role**: Promotes raw typos to active corrections

**Logic**:
1. Iterate through all raw typos
2. Skip typos already covered by active corrections or patterns
3. Attempt to resolve collisions (frequency-based)
4. Determine valid boundaries (ordered: NONE → LEFT/RIGHT → BOTH)
5. **Crucial Step**: Check the Graveyard
   - If `(typo, word, NONE)` is in graveyard, try `(typo, word, LEFT/RIGHT)`
   - This implements **backtracking/self-healing**
6. Add valid correction to active set

**Self-Healing Example**:
```
Iteration 1:
  - "teh" → "the" added with NONE boundary
  - "tehir" → "their" attempted with NONE boundary
  - Added to active corrections

Next pass (Conflict Removal):
  - Detects "tehir" conflicts with "teh"
  - Removes "tehir", adds to graveyard with reason "blocked_by_conflict"

Iteration 2:
  - CandidateSelectionPass sees "tehir" is not covered
  - Checks graveyard: (tehir, their, NONE) is dead
  - Tries (tehir, their, LEFT) instead
  - Succeeds! No conflict with LEFT boundary
```

###### B. PatternGeneralizationPass (Refactored Stage 4)

**Role**: Compresses specific corrections into general patterns

**Logic**:
1. Scan active corrections for repeated patterns
2. Identify prefix/suffix patterns (e.g., `*er → *re`)
3. Validate patterns against validation set
4. Check graveyard (don't retry failed patterns)
5. **Action**: Add pattern to active set, remove specific corrections

**Example**:
```
Corrections:
  aer → are
  ehr → her
  oer → ore

Pattern detected:
  *er → *re

Result:
  Pattern added: *er → *re
  Specific corrections removed
```

###### C. ConflictRemovalPass (Refactored Stage 5)

**Role**: Enforces substring/overlap rules

**Logic**:
1. Group corrections by boundary type
2. For each group, detect conflicts:
   - **LEFT/NONE/BOTH**: Longer typos starting with shorter typos
   - **RIGHT**: Longer typos ending with shorter typos
3. **Action**: Remove conflicting correction, add to graveyard with blocker info
4. **Self-Healing Trigger**: By removing and recording the blocker, this signals CandidateSelectionPass to try a stricter boundary in the next iteration

**Conflict Detection**:
```
Corrections:
  teh → the (NONE)
  tehir → their (NONE)

Conflict check:
  - "tehir" starts with "teh"?  Yes
  - "teh" + "ir" = "their"?     Yes
  - Conflict!

Action:
  - Remove (tehir, their, NONE)
  - Add to graveyard with blocker="teh"
```

###### D. PlatformConstraintsPass (Refactored Stage 6)

**Role**: Enforces hard platform limits

**Logic**:
1. Check character set constraints (e.g., QMK: a-z and apostrophe only)
2. Check length limits for typos and words
3. Check boundary support
4. **Action**: Remove invalid items, add to graveyard with reason

**Example Constraints**:
```
QMK Platform:
  - Max corrections: 6000
  - Allowed chars: a-z, '
  - Boundary support: Yes

Action:
  - Remove: café → cafe (invalid chars)
  - Add to graveyard: platform_constraint
```

#### Data Flow

```
Raw Typo Map
    ↓
DictionaryState ←→ CandidateSelection
    ↓                    ↓
PatternGeneralization ← ← ←
    ↓
ConflictRemoval (adds to graveyard)
    ↓
PlatformConstraints (adds to graveyard)
    ↓
Converged? → YES: Final corrections
           → NO:  Start next iteration
```

### Stage 7: Platform-Specific Ranking and Filtering

- Apply additional platform-specific filtering
- Rank corrections by usefulness/frequency
- Prioritize user-specified words
- Apply max corrections limit

### Stage 8: Output Generation

- Generate platform-specific output format
- YAML for Espanso
- C array for QMK

### Stage 9: Report Generation (Optional)

- Generate detailed reports
- Show statistics for each stage
- List rejected patterns and conflicts
- Debug trace for specified words/typos

## Boundary Types

Boundary markers control when corrections trigger:

- **NONE**: Triggers anywhere (e.g., "teh" in "atheist" → "atheist")
- **LEFT**: Must be at word start (e.g., `:teh` matches "teh" but not "ateh")
- **RIGHT**: Must be at word end (e.g., `teh:` matches "teh" but not "tehn")
- **BOTH**: Standalone word only (e.g., `:teh:` matches "teh" but not in "teh" or "ateh")

## Conflict Resolution

### Substring Conflicts

When one typo is a substring of another, the shorter one takes precedence:

```
Example (LEFT boundary):
  teh → the
  tehir → their

When typing "tehir":
  1. Platform sees "teh" first
  2. Triggers: "the" + "ir" = "their" ✓
  3. Result: "tehir" correction is redundant
```

### Collision Resolution

When multiple words compete for the same typo:

```
Example:
  nto → not (freq: 1000)
  nto → into (freq: 100)

Frequency ratio: 1000/100 = 10.0
Threshold: 2.0

Result: Choose "not" (clear winner)
```

If ratio ≤ threshold: ambiguous collision, skip both.

## Pattern Generalization

### Pattern Types

- **Suffix patterns**: `*typo → *word` (e.g., `*er → *re`)
- **Prefix patterns**: `typo* → word*` (e.g., `th* → the*`)

### Pattern Validation

Patterns must:
1. Apply to at least 2 corrections
2. Not create false positives
3. Not violate platform constraints

### Pattern Efficiency

A pattern is worth it if:
```
Savings = (corrections_replaced * correction_cost) - pattern_cost > 0
```

## Self-Healing Architecture Benefits

### 1. Automatic Backtracking

No need for upfront planning. The solver automatically retries with stricter boundaries when conflicts arise.

### 2. Convergence Guarantees

The graveyard prevents infinite loops. Each correction can only be tried once per boundary type.

### 3. Robustness

If one approach fails, the solver automatically tries alternatives. This leads to more comprehensive coverage.

### 4. Debuggability

The trace log shows exactly why each decision was made, making it easy to understand and debug the optimization process.

## Performance Characteristics

### Time Complexity

- **CandidateSelection**: O(n) per iteration
- **ConflictRemoval**: O(n²) worst case, O(n log n) average with indexing
- **PatternGeneralization**: O(n)
- **Total**: O(n² * i) where i = number of iterations (typically 2-3)

### Space Complexity

- **DictionaryState**: O(n) for corrections + O(g) for graveyard
- **Passes**: O(1) (stateless)
- **Total**: O(n + g) where g = graveyard size (typically < n)

## Future Enhancements

### Possible Improvements

1. **Parallel Pass Execution**: Some passes could run in parallel
2. **Incremental Updates**: Only reprocess changed items
3. **Heuristic Ordering**: Order passes based on expected impact
4. **Adaptive Thresholds**: Adjust collision threshold based on feedback

### Extension Points

The Pass interface makes it easy to add new passes:
- Grammar-aware corrections
- Context-sensitive rules
- Machine learning-based ranking
- Custom platform-specific optimizations
