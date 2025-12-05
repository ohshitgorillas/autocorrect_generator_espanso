"""Debug word lifecycle report generation."""

from pathlib import Path
import re
from typing import TextIO

from entroppy.core import format_boundary_display
from entroppy.reports.helpers import write_report_header
from entroppy.resolution.state import DebugTraceEntry
from entroppy.utils.helpers import write_file_safely


def _sanitize_filename(word: str) -> str:
    """Sanitize word for use in filename.

    Args:
        word: The word to sanitize

    Returns:
        Safe filename string
    """
    # Replace invalid filename characters with underscores
    sanitized = re.sub(r'[<>:"/\\|?*]', "_", word)
    # Limit length to avoid filesystem issues
    if len(sanitized) > 100:
        sanitized = sanitized[:100]
    return sanitized


def generate_debug_words_report(
    debug_messages: list[str],
    debug_trace: list[DebugTraceEntry],
    report_dir: Path,
) -> None:
    """Generate debug word lifecycle reports (one file per word).

    Args:
        debug_messages: Stage 2 debug messages
        debug_trace: Debug trace entries from solver
        report_dir: Directory to write reports to
    """
    # Extract word-specific events from debug messages
    word_events: dict[str, list[str]] = {}
    for message in debug_messages:
        if "[DEBUG WORD:" in message:
            # Extract word from message like "[DEBUG WORD: 'word'] [Stage 2] message"
            try:
                start = message.index("[DEBUG WORD: '") + len("[DEBUG WORD: '")
                end = message.index("']", start)
                word = message[start:end]
                if word not in word_events:
                    word_events[word] = []
                word_events[word].append(message)
            except (ValueError, IndexError):
                continue

    # Extract solver events for debug words
    word_solver_events: dict[str, list[DebugTraceEntry]] = {}
    for entry in debug_trace:
        if entry.word in word_events:
            if entry.word not in word_solver_events:
                word_solver_events[entry.word] = []
            word_solver_events[entry.word].append(entry)

    # Get all unique words
    all_words = sorted(set(list(word_events.keys()) + list(word_solver_events.keys())))

    if not all_words:
        return

    # Generate one report file per word
    for word in all_words:
        sanitized_word = _sanitize_filename(word)
        filepath = report_dir / f"debug_word_{sanitized_word}.txt"

        def write_content(f: TextIO) -> None:
            write_report_header(f, f"DEBUG WORD LIFECYCLE REPORT: {word}")

            f.write(f'Word: "{word}"\n\n')

            # Stage 2 events
            if word in word_events:
                f.write("Stage 2: Typo Generation\n")
                f.write("-" * 70 + "\n")
                for message in word_events[word]:
                    # Extract just the message part after the word marker
                    if "[Stage 2]" in message:
                        msg_part = message.split("[Stage 2]", 1)[1].strip()
                        f.write(f"  {msg_part}\n")
                    else:
                        f.write(f"  {message}\n")
                f.write("\n")

            # Solver events
            if word in word_solver_events:
                f.write("Solver Lifecycle:\n")
                f.write("-" * 70 + "\n")
                for entry in sorted(
                    word_solver_events[word], key=lambda e: (e.iteration, e.pass_name)
                ):
                    boundary_str = format_boundary_display(entry.boundary)
                    f.write(
                        f"  Iter {entry.iteration} [{entry.pass_name}] {entry.action}: "
                        f"{entry.typo} -> {entry.word} ({boundary_str})\n"
                    )
                    if entry.reason:
                        f.write(f"    Reason: {entry.reason}\n")
                f.write("\n")
            else:
                f.write("Solver Lifecycle: No events tracked\n\n")

        write_file_safely(filepath, write_content, f"writing debug word report for {word}")
