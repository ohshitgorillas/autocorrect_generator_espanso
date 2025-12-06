"""Reporting data extraction from pipeline state."""

from entroppy.reports import ReportData
from entroppy.resolution.solver import PassContext
from entroppy.resolution.state import DictionaryState, GraveyardEntry, RejectionReason
from entroppy.utils.helpers import cached_word_frequency


def extract_collision_data(
    entry: GraveyardEntry, state: DictionaryState, report_data: ReportData
) -> None:
    """Extract collision data from graveyard entry.

    Args:
        entry: Graveyard entry
        state: Dictionary state
        report_data: Report data to populate
    """
    words = state.raw_typo_map.get(entry.typo, [])
    if words:
        # Calculate frequency ratio for collision
        word_freqs = [cached_word_frequency(w, "en") for w in words]
        if len(word_freqs) > 1:
            word_freqs.sort(reverse=True)
            ratio = word_freqs[0] / word_freqs[1] if word_freqs[1] > 0 else float("inf")
            report_data.skipped_collisions.append((entry.typo, words, ratio, entry.boundary))


def find_blocking_word(blocking_typo: str, state: DictionaryState) -> str | None:
    """Find the word for a blocking typo.

    Args:
        blocking_typo: The blocking typo string
        state: Dictionary state

    Returns:
        The blocking word if found, None otherwise
    """
    # Try to find the blocking correction in active corrections
    for correction in state.active_corrections:
        corr_typo, corr_word, _ = correction
        if corr_typo == blocking_typo:
            return corr_word

    # Check graveyard
    for grave_entry in state.graveyard.values():
        if grave_entry.typo == blocking_typo:
            return grave_entry.word

    return None


def extract_conflict_data(
    entry: GraveyardEntry, state: DictionaryState, report_data: ReportData
) -> None:
    """Extract conflict data from graveyard entry.

    Args:
        entry: Graveyard entry
        state: Dictionary state
        report_data: Report data to populate
    """
    if entry.blocker:
        blocking_word = find_blocking_word(entry.blocker, state)
        if blocking_word:
            report_data.removed_conflicts.append(
                (entry.typo, entry.word, entry.blocker, blocking_word, entry.boundary)
            )


def _extract_rejection_data(
    entry: GraveyardEntry,
    state: DictionaryState,
    report_data: ReportData,
    pass_context: PassContext,
) -> None:
    """Extract data for a single graveyard entry based on rejection reason."""
    if entry.reason == RejectionReason.COLLISION_AMBIGUOUS:
        extract_collision_data(entry, state, report_data)
    elif entry.reason == RejectionReason.BLOCKED_BY_CONFLICT:
        extract_conflict_data(entry, state, report_data)
    elif entry.reason == RejectionReason.EXCLUDED_BY_PATTERN:
        report_data.excluded_corrections.append(
            (entry.typo, entry.word, entry.blocker or "exclusion pattern")
        )
    elif entry.reason == RejectionReason.TOO_SHORT:
        min_length = pass_context.min_typo_length
        report_data.skipped_short.append((entry.typo, entry.word, min_length))
    elif entry.reason == RejectionReason.PATTERN_VALIDATION_FAILED:
        report_data.rejected_patterns.append(
            (
                entry.typo,
                entry.word,
                entry.boundary,
                entry.blocker or "validation failed",
            )
        )


def extract_graveyard_data_for_reporting(
    state: DictionaryState, report_data: ReportData, pass_context: PassContext
) -> None:
    """Extract data from graveyard for reporting.

    Args:
        state: Dictionary state containing graveyard
        report_data: Report data to populate
        pass_context: Pass context for accessing configuration
    """
    for entry in state.graveyard.values():
        _extract_rejection_data(entry, state, report_data, pass_context)

    # Extract pattern data
    for pattern in state.active_patterns:
        typo, word, boundary = pattern
        replacements = state.pattern_replacements.get(pattern, [])
        report_data.generalized_patterns.append((typo, word, boundary, len(replacements)))
        if replacements:
            report_data.pattern_replacements[pattern] = replacements

    # Track corrections counts at different stages
    # Before generalization: all corrections that were ever active
    # We approximate this as active corrections + patterns (since patterns replace corrections)
    report_data.corrections_before_generalization = (
        len(state.active_corrections) + len(state.active_patterns) + len(state.pattern_replacements)
    )
    report_data.corrections_after_generalization = len(state.active_corrections) + len(
        state.active_patterns
    )
    # After conflicts: same as after generalization (conflicts are removed during solver)
    report_data.corrections_after_conflicts = report_data.corrections_after_generalization
