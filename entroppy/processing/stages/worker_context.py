"""Worker context for multiprocessing without global state."""

import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from entroppy.utils.debug import DebugTypoMatcher


@dataclass(frozen=True)
class WorkerContext:
    """Immutable context for multiprocessing workers.

    This encapsulates all state that workers need, eliminating the need
    for global variables. The frozen dataclass ensures immutability and
    thread-safety.

    Attributes:
        validation_set: Full validation dictionary (for checking if typo is a real word)
        filtered_validation_set: Filtered validation set (for boundary detection,
            excludes exclusion patterns)
        source_words_set: Set of source words from includes file
        typo_freq_threshold: Frequency threshold for filtering typos
        adjacent_letters_map: Adjacent letters map for insertions/replacements
        exclusions_set: Set of exclusion patterns
        debug_words: Set of words to trace through pipeline (exact matches)
        debug_typo_matcher: Matcher for debug typos (with wildcard/boundary support)
    """

    validation_set: frozenset[str]
    filtered_validation_set: frozenset[str]
    source_words_set: frozenset[str]
    typo_freq_threshold: float
    adjacent_letters_map: dict[str, list[str]]
    exclusions_set: frozenset[str]
    debug_words: frozenset[str]
    debug_typo_matcher: "DebugTypoMatcher | None"

    @classmethod
    def from_dict_data(cls, dict_data, config) -> "WorkerContext":
        """Create WorkerContext from DictionaryData and config.

        Args:
            dict_data: DictionaryData from dictionary loading stage
            config: Config object containing threshold and debug settings

        Returns:
            New WorkerContext instance
        """
        return cls(
            validation_set=frozenset(dict_data.validation_set),
            filtered_validation_set=frozenset(dict_data.filtered_validation_set),
            source_words_set=frozenset(dict_data.source_words_set),
            typo_freq_threshold=config.typo_freq_threshold,
            adjacent_letters_map=dict_data.adjacent_letters_map,
            exclusions_set=frozenset(dict_data.exclusions),
            debug_words=frozenset(config.debug_words),
            debug_typo_matcher=config.debug_typo_matcher,
        )


# Thread-local storage for worker context
_worker_context = threading.local()


def init_worker(context: WorkerContext) -> None:
    """Initialize worker process with context in thread-local storage.

    Args:
        context: WorkerContext to store in thread-local storage
    """
    _worker_context.value = context


def get_worker_context() -> WorkerContext:
    """Get the current worker's context from thread-local storage.

    Returns:
        WorkerContext for this worker

    Raises:
        RuntimeError: If called before init_worker
    """
    try:
        return _worker_context.value
    except AttributeError as e:
        raise RuntimeError("Worker context not initialized. Call init_worker first.") from e
