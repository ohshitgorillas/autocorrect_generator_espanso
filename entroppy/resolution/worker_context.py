"""Worker context and initialization for parallel collision resolution."""

from dataclasses import dataclass
import threading
from typing import TYPE_CHECKING

from entroppy.core.boundaries import BoundaryIndex

if TYPE_CHECKING:
    from entroppy.core import BoundaryType


@dataclass(frozen=True)
class CollisionResolutionContext:
    """Immutable context for collision resolution workers.

    This encapsulates all state that workers need for parallel collision resolution.
    The frozen dataclass ensures immutability and thread-safety.

    Attributes:
        validation_set: Set of validation words
        source_words: Set of source words
        freq_ratio: Minimum frequency ratio for collision resolution
        min_typo_length: Minimum typo length
        min_word_length: Minimum word length
        user_words: Set of user-provided words
        exclusion_set: Set of exclusion patterns (raw strings, not matcher)
        debug_words: Set of words to debug (exact matches)
        debug_typo_patterns: Set of debug typo patterns (raw strings, not matcher)
    """

    validation_set: frozenset[str]
    source_words: frozenset[str]
    freq_ratio: float
    min_typo_length: int
    min_word_length: int
    user_words: frozenset[str]
    exclusion_set: frozenset[str]
    debug_words: frozenset[str]
    debug_typo_patterns: frozenset[str]


# Thread-local storage for worker context and indexes
_worker_context = threading.local()
_worker_indexes = threading.local()


def init_collision_worker(context: CollisionResolutionContext) -> None:
    """Initialize worker process with context and build indexes eagerly.

    Args:
        context: CollisionResolutionContext to store in thread-local storage
    """
    _worker_context.value = context

    # Build indexes eagerly during initialization
    # This prevents the progress bar from freezing when workers start
    _worker_indexes.validation_index = BoundaryIndex(context.validation_set)
    _worker_indexes.source_index = BoundaryIndex(context.source_words)


def get_collision_worker_context() -> CollisionResolutionContext:
    """Get the current worker's context from thread-local storage.

    Returns:
        CollisionResolutionContext for this worker

    Raises:
        RuntimeError: If called before init_collision_worker
    """
    try:
        return _worker_context.value  # type: ignore[no-any-return]
    except AttributeError as e:
        raise RuntimeError(
            "Collision resolution worker context not initialized. Call init_collision_worker first."
        ) from e


def get_worker_indexes() -> tuple[BoundaryIndex, BoundaryIndex]:
    """Get boundary indexes from thread-local storage.

    Returns:
        Tuple of (validation_index, source_index)

    Raises:
        RuntimeError: If called before init_collision_worker
    """
    try:
        return _worker_indexes.validation_index, _worker_indexes.source_index
    except AttributeError as e:
        raise RuntimeError(
            "Collision resolution worker indexes not initialized. Call init_collision_worker first."
        ) from e


@dataclass(frozen=True)
class CandidateSelectionContext:
    """Immutable context for candidate selection workers.

    This encapsulates all state that workers need for parallel candidate selection.
    The frozen dataclass ensures immutability and thread-safety.

    Attributes:
        validation_set: Set of validation words
        source_words: Set of source words
        min_typo_length: Minimum typo length
        collision_threshold: Minimum frequency ratio for collision resolution
        exclusion_set: Set of exclusion patterns (raw strings, not matcher)
        covered_typos: Set of typos already covered by active corrections/patterns
        graveyard: Set of (typo, word, boundary) tuples in graveyard
    """

    validation_set: frozenset[str]
    source_words: frozenset[str]
    min_typo_length: int
    collision_threshold: float
    exclusion_set: frozenset[str]
    covered_typos: frozenset[str]
    graveyard: frozenset[tuple[str, str, "BoundaryType"]]  # type: ignore


# Thread-local storage for candidate selection worker context and indexes
_candidate_worker_context = threading.local()
_candidate_worker_indexes = threading.local()


def init_candidate_selection_worker(context: "CandidateSelectionContext") -> None:
    """Initialize worker process with context and build indexes eagerly.

    Args:
        context: CandidateSelectionContext to store in thread-local storage
    """
    _candidate_worker_context.value = context

    # Build indexes eagerly during initialization
    # This prevents the progress bar from freezing when workers start
    _candidate_worker_indexes.validation_index = BoundaryIndex(context.validation_set)
    _candidate_worker_indexes.source_index = BoundaryIndex(context.source_words)


def get_candidate_selection_worker_context() -> "CandidateSelectionContext":
    """Get the current worker's context from thread-local storage.

    Returns:
        CandidateSelectionContext for this worker

    Raises:
        RuntimeError: If called before init_candidate_selection_worker
    """
    try:
        return _candidate_worker_context.value  # type: ignore[no-any-return]
    except AttributeError as e:
        raise RuntimeError(
            "Candidate selection worker context not initialized. "
            "Call init_candidate_selection_worker first."
        ) from e


def get_candidate_worker_indexes() -> tuple[BoundaryIndex, BoundaryIndex]:
    """Get boundary indexes from thread-local storage.

    Returns:
        Tuple of (validation_index, source_index)

    Raises:
        RuntimeError: If called before init_candidate_selection_worker
    """
    try:
        return _candidate_worker_indexes.validation_index, _candidate_worker_indexes.source_index
    except AttributeError as e:
        raise RuntimeError(
            "Candidate selection worker indexes not initialized. "
            "Call init_candidate_selection_worker first."
        ) from e
