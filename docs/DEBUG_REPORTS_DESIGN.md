# Debug Reports Design Document

## Overview

This document outlines the design for implementing three debug report flags:
- `--debug-graveyard`: Comprehensive report of all graveyard entries with iteration/pass context
- `--debug-patterns`: Comprehensive report of all pattern lifecycle events
- `--debug-corrections`: Comprehensive report of all correction lifecycle events

## Current State Analysis

### Existing Tracking Mechanisms

1. **Graveyard Tracking** (`DictionaryState.graveyard` in `entroppy/resolution/state.py`):
   - Already stores `GraveyardEntry` objects with:
     - `typo`, `word`, `boundary`
     - `reason` (RejectionReason enum)
     - `blocker` (optional string)
     - `iteration` (already tracked!)
   - Key limitation: Only tracks final state, not the pass that added it

2. **Pattern Tracking** (`DictionaryState.active_patterns` in `entroppy/resolution/state.py`):
   - Simple set of `(typo, word, boundary)` tuples
   - No history tracking
   - Methods: `DictionaryState.add_pattern()`, `DictionaryState.remove_pattern()`

3. **Correction Tracking** (`DictionaryState.active_corrections` in `entroppy/resolution/state.py`):
   - Simple set of `(typo, word, boundary)` tuples
   - No history tracking
   - Methods: `DictionaryState.add_correction()`, `DictionaryState.remove_correction()`

4. **Debug Trace** (`DictionaryState.debug_trace` in `entroppy/resolution/state.py`):
   - Only tracks changes for specific debug targets (words/typos)
   - Uses `DebugTraceEntry` with iteration, pass_name, action, reason
   - Not comprehensive - only for selected items

### Pass Structure

The solver runs passes in this order (in `entroppy/resolution/passes/`):
1. `CandidateSelectionPass` - Adds corrections from raw typo map
2. `PatternGeneralizationPass` - Creates patterns, removes covered corrections
3. `ConflictRemovalPass` - Removes conflicting corrections
4. `PlatformSubstringConflictPass` - Removes platform-specific conflicts
5. `PlatformConstraintsPass` - Applies platform limits

Each pass calls state methods with `pass_name` parameter, which is perfect for tracking.

## Design Proposal

### Core Principle: Comprehensive History Tracking

Instead of only tracking debug targets, we'll track **all** changes to graveyard, patterns, and corrections. This is acceptable because:
- Memory overhead is minimal (just metadata per entry)
- File size is not a concern (user explicitly requested comprehensive reports)
- Provides complete audit trail

### Data Structures

#### 1. Enhanced History Tracking in DictionaryState

**File**: `entroppy/resolution/state.py`
**Class**: `DictionaryState`

Add three new attributes to `DictionaryState`:

```python
# History tracking (only populated if debug flags enabled)
self.graveyard_history: list[GraveyardHistoryEntry] = []
self.pattern_history: list[PatternHistoryEntry] = []
self.correction_history: list[CorrectionHistoryEntry] = []
```

#### 2. History Entry Data Classes

**File**: `entroppy/resolution/state.py`

```python
@dataclass
class GraveyardHistoryEntry:
    """Complete history of a graveyard entry."""
    iteration: int
    pass_name: str
    typo: str
    word: str
    boundary: BoundaryType
    reason: RejectionReason
    blocker: str | None
    timestamp: float  # For ordering within same iteration/pass

@dataclass
class PatternHistoryEntry:
    """Complete history of pattern lifecycle."""
    iteration: int
    pass_name: str
    action: str  # "added", "removed"
    typo: str
    word: str
    boundary: BoundaryType
    reason: str | None  # For removals
    timestamp: float

@dataclass
class CorrectionHistoryEntry:
    """Complete history of correction lifecycle."""
    iteration: int
    pass_name: str
    action: str  # "added", "removed"
    typo: str
    word: str
    boundary: BoundaryType
    reason: str | None  # For removals
    timestamp: float
```

### Implementation Strategy

#### Phase 1: Add History Tracking to DictionaryState

**File**: `entroppy/resolution/state.py`
**Class**: `DictionaryState`

Modify `DictionaryState` methods to append to history lists when debug flags are enabled:

```python
def __init__(self, ..., debug_graveyard=False, debug_patterns=False, debug_corrections=False):
    # ... existing init ...
    self.debug_graveyard = debug_graveyard
    self.debug_patterns = debug_patterns
    self.debug_corrections = debug_corrections
    # Initialize history lists

def add_to_graveyard(self, ..., pass_name: str):
    # ... existing logic ...
    if self.debug_graveyard:
        self.graveyard_history.append(
            GraveyardHistoryEntry(
                iteration=self.current_iteration,
                pass_name=pass_name,  # Need to pass this!
                # ... other fields ...
                timestamp=time.time()
            )
        )
```

**Challenge**: `DictionaryState.add_to_graveyard()` doesn't currently receive `pass_name`. Need to:
- Add `pass_name` parameter to `DictionaryState.add_to_graveyard()`
- Update all call sites (about 10-15 locations)

#### Phase 2: Update All State Method Calls

**Files**: All files in `entroppy/resolution/passes/`

All passes call state methods. We need to ensure they pass `pass_name`:

```python
# In each pass:
state.add_to_graveyard(typo, word, boundary, reason, blocker, pass_name=self.name)
state.add_correction(typo, word, boundary, pass_name=self.name)
state.remove_correction(typo, word, boundary, pass_name=self.name, reason=reason)
```

**Methods to update**:
- `DictionaryState.add_to_graveyard()` - add `pass_name` parameter
- `DictionaryState.add_correction()` - add `pass_name` parameter
- `DictionaryState.remove_correction()` - add `pass_name` parameter
- `DictionaryState.add_pattern()` - add `pass_name` parameter
- `DictionaryState.remove_pattern()` - add `pass_name` parameter

#### Phase 3: Report Generation

**Directory**: `entroppy/reports/`

Create three new report generators:

1. **File**: `entroppy/reports/debug_graveyard.py`
   **Function**: `generate_graveyard_debug_report(state: DictionaryState) -> str`

2. **File**: `entroppy/reports/debug_patterns.py`
   **Function**: `generate_patterns_debug_report(state: DictionaryState) -> str`

3. **File**: `entroppy/reports/debug_corrections.py`
   **Function**: `generate_corrections_debug_report(state: DictionaryState) -> str`

Each report should:
- Group by iteration
- Within iteration, group by pass
- Show chronological order within pass
- Include all relevant context (reason, blocker, etc.)

#### Phase 4: CLI Integration

**File**: `entroppy/cli/parser.py`

Add flags to CLI parser:

```python
parser.add_argument(
    "--debug-graveyard",
    action="store_true",
    help="Generate comprehensive graveyard debug report"
)
parser.add_argument(
    "--debug-patterns",
    action="store_true",
    help="Generate comprehensive patterns debug report"
)
parser.add_argument(
    "--debug-corrections",
    action="store_true",
    help="Generate comprehensive corrections debug report"
)
```

**File**: `entroppy/core/config.py`
**Class**: `Config`

Add to `Config` class:

```python
debug_graveyard: bool = False
debug_patterns: bool = False
debug_corrections: bool = False
```

**File**: `entroppy/processing/pipeline.py`

Pass flags to `DictionaryState.__init__()` in pipeline.

### Report Format Design

#### Graveyard Report Structure

```
================================================================================
GRAVEYARD DEBUG REPORT
================================================================================
Generated: 2025-12-04 10:28:47

Total graveyard entries: 13,067

--- Iteration 1 ---
  [CandidateSelection]
    typo: "teh" → word: "the" (boundary: NONE)
      Reason: too_short
      Added at: 2025-12-04 10:28:15.123

    typo: "adn" → word: "and" (boundary: LEFT)
      Reason: excluded_by_pattern
      Blocker: exclusion rule "adn"
      Added at: 2025-12-04 10:28:15.456

  [ConflictRemoval]
    typo: "nto" → word: "not" (boundary: BOTH)
      Reason: blocked_by_conflict
      Blocker: "nto" → "into" (BOTH)
      Added at: 2025-12-04 10:28:27.789

--- Iteration 2 ---
  [PlatformSubstringConflicts]
    typo: "aemr" → word: "ream" (boundary: LEFT)
      Reason: platform_constraint
      Blocker: "aemr" → "ream" (NONE) - substring conflict
      Added at: 2025-12-04 10:28:39.012

[... continues for all iterations ...]
```

#### Patterns Report Structure

```
================================================================================
PATTERNS DEBUG REPORT
================================================================================
Generated: 2025-12-04 10:28:47

Total pattern events: 1,234

--- Iteration 1 ---
  [PatternGeneralization]
    ADDED: "tion" → "tion" (boundary: SUFFIX)
      Added at: 2025-12-04 10:28:27.123
      Replaces 15 corrections:
        - "action" → "action"
        - "lection" → "lection"
        - ...

--- Iteration 2 ---
  [PlatformSubstringConflicts]
    REMOVED: "tion" → "tion" (boundary: SUFFIX)
      Reason: Platform substring conflict with "tion" → "tion" (NONE)
      Removed at: 2025-12-04 10:28:39.456

[... continues ...]
```

#### Corrections Report Structure

```
================================================================================
CORRECTIONS DEBUG REPORT
================================================================================
Generated: 2025-12-04 10:28:47

Total correction events: 45,234

--- Iteration 1 ---
  [CandidateSelection]
    ADDED: "teh" → "the" (boundary: NONE)
      Added at: 2025-12-04 10:28:15.123

    ADDED: "adn" → "and" (boundary: LEFT)
      Added at: 2025-12-04 10:28:15.456

  [PatternGeneralization]
    REMOVED: "action" → "action" (boundary: SUFFIX)
      Reason: Covered by pattern "tion" → "tion"
      Removed at: 2025-12-04 10:28:27.789

--- Iteration 2 ---
  [ConflictRemoval]
    REMOVED: "nto" → "not" (boundary: BOTH)
      Reason: Blocked by conflict with "nto" → "into"
      Removed at: 2025-12-04 10:28:39.012

[... continues ...]
```

### Performance Considerations

1. **Memory**: History lists grow during execution. For 13K graveyard entries, this is ~1-2MB, acceptable.

2. **Time**: Appending to lists is O(1), minimal overhead. Report generation is O(n) where n is number of entries.

3. **File Size**: Reports could be large (10-100MB for full runs), but user explicitly said "do not be concerned about ultimate file size".

### Implementation Steps

1. **Add history data classes** to `entroppy/resolution/state.py`
   - `GraveyardHistoryEntry`
   - `PatternHistoryEntry`
   - `CorrectionHistoryEntry`

2. **Add debug flags** to `Config` (`entroppy/core/config.py`) and CLI parser (`entroppy/cli/parser.py`)
   - `debug_graveyard: bool`
   - `debug_patterns: bool`
   - `debug_corrections: bool`

3. **Modify DictionaryState** (`entroppy/resolution/state.py`) to accept flags and track history
   - Add `graveyard_history`, `pattern_history`, `correction_history` attributes
   - Update `DictionaryState.__init__()` to accept debug flags

4. **Update `DictionaryState.add_to_graveyard()` signature** to accept `pass_name`
   - Add `pass_name: str` parameter

5. **Update all call sites** of state methods to pass `pass_name`
   - Search for: `state.add_to_graveyard(`
   - Search for: `state.add_correction(`
   - Search for: `state.remove_correction(`
   - Search for: `state.add_pattern(`
   - Search for: `state.remove_pattern(`

6. **Create report generators** in `entroppy/reports/`
   - `debug_graveyard.py` with `generate_graveyard_debug_report()`
   - `debug_patterns.py` with `generate_patterns_debug_report()`
   - `debug_corrections.py` with `generate_corrections_debug_report()`

7. **Integrate report generation** into `generate_reports()` function
   - **File**: `entroppy/platforms/espanso/reports.py` or similar
   - Call report generators when flags are enabled

8. **Test with sample runs** to verify completeness

### Edge Cases

1. **Parallel workers**: Some passes use parallel workers that call state methods indirectly. Need to ensure `pass_name` propagates correctly.
   - **Files to check**: `entroppy/resolution/pattern_validation_worker.py`, `entroppy/resolution/worker_context.py`

2. **Pattern replacements**: When patterns replace corrections, we should show which corrections were replaced in the pattern report.
   - **File**: `entroppy/reports/debug_patterns.py`
   - **Function**: `generate_patterns_debug_report()`

3. **Graveyard duplicates**: If same correction is added to graveyard multiple times (shouldn't happen, but defensive), show all attempts.
   - **File**: `entroppy/reports/debug_graveyard.py`

4. **Empty reports**: If no changes occurred, still generate report with header explaining no changes.
   - **Files**: All three debug report generators

### Testing Strategy

1. Run with all three flags enabled on a small dataset
2. Verify all entries are captured
3. Verify chronological ordering
4. Verify iteration/pass grouping
5. Verify reasons and blockers are accurate
6. Test with larger dataset to check performance

## Alternative Approaches Considered

### Alternative 1: Post-Process Existing State

**Approach**: Don't track during execution, instead reconstruct history from final state.

**Rejected because**:
- Can't determine which pass added/removed items
- Can't determine chronological order
- Missing context (reasons, blockers) for removed items

### Alternative 2: Only Track When Flags Enabled

**Approach**: Only populate history lists when corresponding flag is True.

**Accepted**: This is our approach - conditional tracking based on flags.

### Alternative 3: Use Existing Debug Trace

**Approach**: Extend `DictionaryState.debug_trace` to track all items, not just debug targets.

**Rejected because**:
- `DictionaryState.debug_trace` is specifically for selected debug targets
- Mixing concerns would make code less clear
- Separate history lists are cleaner

## Conclusion

This design provides:
- ✅ Complete audit trail of all changes
- ✅ Iteration and pass context for every change
- ✅ Minimal performance overhead (only when flags enabled)
- ✅ Clean separation of concerns
- ✅ Comprehensive reports as requested

The implementation is straightforward and follows existing patterns in the codebase.
