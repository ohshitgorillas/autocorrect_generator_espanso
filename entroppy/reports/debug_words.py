"""Debug word lifecycle report generation using structured data."""

from pathlib import Path
from typing import TYPE_CHECKING

from entroppy.core import format_boundary_display
from entroppy.core.patterns.data_models import (
    IterationData,
    TypoAcceptedEvent,
    TypoGeneratedEvent,
    WordProcessingEvent,
)
from entroppy.reports.debug_report_writers import (
    write_iteration_section,
    write_ranking_section,
)
from entroppy.reports.helpers import (
    write_report_header,
    write_section_header,
)
from entroppy.resolution.state import DebugTraceEntry
from entroppy.utils.helpers import write_file_safely

if TYPE_CHECKING:
    from entroppy.resolution.state import DictionaryState


def _get_solver_events_for_word(
    word: str, debug_trace: list[DebugTraceEntry]
) -> list[DebugTraceEntry]:
    """Get solver events for a specific word.

    Args:
        word: The word to filter events for
        debug_trace: All debug trace entries

    Returns:
        List of debug trace entries for this word
    """
    return [e for e in debug_trace if e.word == word]


def _add_word_if_debugged(word: str, debug_words: set[str], words: set[str]) -> None:
    """Add word to set if it's in debug_words.

    Args:
        word: Word to check
        debug_words: Set of words to debug
        words: Set to add word to if it matches
    """
    if word in debug_words:
        words.add(word)


def _add_stage2_events_to_iteration(
    word_stage2_events: list[WordProcessingEvent], iteration_data: IterationData, word: str
) -> None:
    """Add Stage 2 events to iteration data, generating messages from structured data.

    Args:
        word_stage2_events: List of Stage 2 events for the word
        iteration_data: IterationData to add messages to
        word: The word being processed
    """
    for event in word_stage2_events:
        if event.event_type == "processing_start":
            iteration_data.other_messages.append("[Stage 2] Generating typos for debug word")
        elif event.event_type == "typo_generated":
            if isinstance(event, TypoGeneratedEvent):
                if event.matched_patterns:
                    patterns_str = ", ".join(event.matched_patterns)
                    iteration_data.other_messages.append(
                        f"[Stage 2] Generated typo: {event.typo} (matched: {patterns_str})"
                    )
                else:
                    iteration_data.other_messages.append(f"[Stage 2] Generated typo: {event.typo}")
        elif event.event_type == "typo_accepted":
            if isinstance(event, TypoAcceptedEvent):
                iteration_data.other_messages.append(
                    f"[Stage 2] Generated typo: {event.typo} → {word}"
                )


def _get_or_create_iteration(
    iterations_map: dict[int, IterationData], iteration: int
) -> IterationData:
    """Get or create IterationData for an iteration.

    Args:
        iterations_map: Map of iteration to IterationData
        iteration: Iteration number

    Returns:
        IterationData for the iteration
    """
    if iteration not in iterations_map:
        iterations_map[iteration] = IterationData(iteration=iteration)
    return iterations_map[iteration]


def _add_extractions_to_iterations(
    word: str, extractions: list, iterations_map: dict[int, IterationData]
) -> None:
    """Add pattern extractions to iterations map.

    Args:
        word: Word to filter extractions for
        extractions: List of pattern extractions
        iterations_map: Map to add to
    """
    for extraction in extractions:
        if any(word == w for _, w, _ in extraction.occurrences):
            iteration = extraction.iteration or 0
            iteration_data = _get_or_create_iteration(iterations_map, iteration)
            iteration_data.pattern_extractions.append(extraction)


def _add_validations_to_iterations(
    word: str, validations: list, iterations_map: dict[int, IterationData]
) -> None:
    """Add pattern validations to iterations map.

    Args:
        word: Word to filter validations for
        validations: List of pattern validations
        iterations_map: Map to add to
    """
    for validation in validations:
        if validation.replaces and any(word == w for _, w in validation.replaces):
            iteration = validation.iteration or 0
            iteration_data = _get_or_create_iteration(iterations_map, iteration)
            iteration_data.pattern_validations.append(validation)


def _add_conflicts_to_iterations(
    word: str, conflicts: list, iterations_map: dict[int, IterationData]
) -> None:
    """Add platform conflicts to iterations map.

    Args:
        word: Word to filter conflicts for
        conflicts: List of platform conflicts
        iterations_map: Map to add to
    """
    for conflict in conflicts:
        if conflict.word == word:
            iteration = conflict.iteration or 0
            iteration_data = _get_or_create_iteration(iterations_map, iteration)
            iteration_data.platform_conflicts.append(conflict)


def _collect_words_from_state(
    state: "DictionaryState", debug_trace: list[DebugTraceEntry], debug_words: set[str]
) -> set[str]:
    """Collect all unique words from structured data.

    Args:
        state: Dictionary state with structured debug data
        debug_trace: Debug trace entries from solver
        debug_words: Set of words to debug

    Returns:
        Set of unique words to generate reports for
    """
    words: set[str] = set()

    # Collect from stage2_word_events
    for event in state.stage2_word_events:
        _add_word_if_debugged(event.word, debug_words, words)

    # Collect from debug_trace
    for entry in debug_trace:
        _add_word_if_debugged(entry.word, debug_words, words)

    # Collect from pattern extractions
    for extraction in state.pattern_extractions:
        for _, word, _ in extraction.occurrences:
            _add_word_if_debugged(word, debug_words, words)

    # Collect from pattern validations
    for validation in state.pattern_validations:
        if validation.replaces:
            for _, word in validation.replaces:
                _add_word_if_debugged(word, debug_words, words)

    # Collect from platform conflicts
    for conflict in state.platform_conflicts:
        _add_word_if_debugged(conflict.word, debug_words, words)

    # Collect from ranking info
    for ranking in state.ranking_info:
        _add_word_if_debugged(ranking.word, debug_words, words)

    return words


def _build_word_lifecycle_from_state(
    word: str,
    state: "DictionaryState",
    debug_trace: list[DebugTraceEntry],
) -> dict[int, IterationData]:
    """Build word lifecycle data from structured state.

    Args:
        word: The word to build lifecycle for
        state: Dictionary state with structured debug data
        debug_trace: Debug trace entries from solver

    Returns:
        Dictionary mapping iteration -> IterationData
    """
    iterations_map: dict[int, IterationData] = {}

    # Add Stage 2 events (iteration 0)
    word_stage2_events = [e for e in state.stage2_word_events if e.word == word]
    if word_stage2_events:
        if 0 not in iterations_map:
            iterations_map[0] = IterationData(iteration=0)
        _add_stage2_events_to_iteration(word_stage2_events, iterations_map[0], word)

    # Add solver events
    word_solver_events = _get_solver_events_for_word(word, debug_trace)
    for entry in word_solver_events:
        iteration = entry.iteration
        if iteration not in iterations_map:
            iterations_map[iteration] = IterationData(iteration=iteration)
        iterations_map[iteration].solver_events.append(entry)

    # Add pattern extractions that involve this word
    _add_extractions_to_iterations(word, state.pattern_extractions, iterations_map)

    # Add pattern validations that involve this word
    _add_validations_to_iterations(word, state.pattern_validations, iterations_map)

    # Add platform conflicts for this word
    _add_conflicts_to_iterations(word, state.platform_conflicts, iterations_map)

    return iterations_map


def _generate_word_report(
    word: str,
    state: "DictionaryState",
    debug_trace: list[DebugTraceEntry],
    report_dir: Path,
) -> None:
    """Generate a single word lifecycle report.

    Args:
        word: The word to generate report for
        state: Dictionary state with structured debug data
        debug_trace: Debug trace entries from solver
        report_dir: Directory to write report to
    """
    # Sanitize filename
    sanitized_word = "".join(c if c.isalnum() or c in "._-" else "_" for c in word)
    if len(sanitized_word) > 100:
        sanitized_word = sanitized_word[:100]
    filepath = report_dir / f"debug_word_{sanitized_word}.txt"

    def write_content(f) -> None:
        write_report_header(f, f"DEBUG WORD LIFECYCLE REPORT: {word}")
        f.write(f'Word: "{word}"\n\n')

        # Build lifecycle from structured data
        iterations_map = _build_word_lifecycle_from_state(word, state, debug_trace)

        # Write Stage 2 separately (pre-iteration)
        if 0 in iterations_map:
            iter_data = iterations_map[0]
            if iter_data.other_messages:
                write_section_header(f, "STAGE 2: TYPO GENERATION")
                for message in iter_data.other_messages:
                    f.write(f"  {message}\n")
                f.write("\n")

        # Write iterations
        for iteration in sorted(iterations_map.keys()):
            if iteration == 0:
                continue

            iter_data = iterations_map[iteration]
            write_iteration_section(iter_data, iteration, f, include_conflict_details=False)

        # Write ranking info
        word_ranking_info = [r for r in state.ranking_info if r.word == word]
        if word_ranking_info:
            write_section_header(f, "STAGE 7: RANKING")
            for ranking in word_ranking_info:
                write_ranking_section(ranking, f, include_header=False)

        # Final summary
        write_section_header(f, "FINAL SUMMARY")
        word_solver_events = _get_solver_events_for_word(word, debug_trace)
        if word_solver_events:
            final_events = sorted(word_solver_events, key=lambda e: (e.iteration, e.pass_name))
            corrections = [e for e in final_events if e.action in ("added", "removed")]
            patterns = [
                e
                for e in final_events
                if e.action in ("promoted_to_pattern", "pattern_added", "pattern_removed")
            ]

            if corrections:
                f.write("Corrections:\n")
                for entry in corrections:
                    boundary_str = format_boundary_display(entry.boundary)
                    f.write(f"  {entry.action}: {entry.typo} -> {entry.word} ({boundary_str})\n")
                f.write("\n")

            if patterns:
                f.write("Patterns:\n")
                for entry in patterns:
                    boundary_str = format_boundary_display(entry.boundary)
                    f.write(f"  {entry.action}: {entry.typo} -> {entry.word} ({boundary_str})\n")
                f.write("\n")

            if iterations_map:
                f.write(f"Total Iterations: {max(iterations_map.keys())}\n")

    write_file_safely(filepath, write_content, f"writing debug word report for {word}")


def generate_debug_words_report(
    debug_trace: list[DebugTraceEntry],
    report_dir: Path,
    debug_words: set[str],
    state: "DictionaryState | None" = None,
) -> None:
    """Generate debug word lifecycle reports (one file per word) using structured data.

    Args:
        debug_trace: Debug trace entries from solver
        report_dir: Directory to write reports to
        debug_words: Set of words to debug
        state: Dictionary state with structured debug data (required)
    """
    if not state:
        return  # Cannot generate reports without structured data

    # Collect all words from structured data
    all_words = _collect_words_from_state(state, debug_trace, debug_words)

    if not all_words:
        return

    # Generate one report file per word
    for word in sorted(all_words):
        _generate_word_report(word, state, debug_trace, report_dir)
