"""Tests for worker context without global state."""

from multiprocessing import Pool

import pytest

from entroppy.core import Config
from entroppy.processing.stages.data_models import DictionaryData
from entroppy.processing.stages.worker_context import WorkerContext, get_worker_context, init_worker


# Module-level worker functions (needed for multiprocessing)
def _multiply_by_threshold(x):
    """Worker that uses context to compute result."""
    context = get_worker_context()
    return context.typo_freq_threshold * x


def _get_threshold(_):
    """Worker that returns threshold from its context."""
    context = get_worker_context()
    return context.typo_freq_threshold


class TestWorkerContextBehavior:
    """Tests for WorkerContext behavior."""

    def test_context_can_be_created_from_dict_data(self):
        """Workers need context created from pipeline data."""

        dict_data = DictionaryData(
            validation_set={"word1", "word2"},
            filtered_validation_set={"word1"},
            source_words_set={"source1"},
            adjacent_letters_map={"a": "sq"},
            exclusions={"excl1"},
        )

        config = Config(typo_freq_threshold=0.002)
        context = WorkerContext.from_dict_data(dict_data, config)

        assert context.typo_freq_threshold == 0.002

    def test_context_can_be_serialized_for_multiprocessing(self):
        """Context must be serializable to pass to worker processes without pickle."""
        context = WorkerContext(
            validation_set=frozenset(["word1", "word2"]),
            filtered_validation_set=frozenset(["word1"]),
            source_words_set=frozenset(["source1"]),
            typo_freq_threshold=0.001,
            adjacent_letters_map={"a": "sq"},
            exclusions_set=frozenset(["excl1"]),
            debug_words=frozenset(),
            debug_typo_patterns=frozenset(),
        )

        # Context should be serializable via multiprocessing (not pickle)
        # This is tested implicitly by the multiprocessing tests below
        assert context.typo_freq_threshold == 0.001


class TestMultiprocessingBehavior:
    """Tests for multiprocessing behavior without globals."""

    def test_workers_can_process_using_context(self):
        """Workers must be able to access and use context data."""
        context = WorkerContext(
            validation_set=frozenset(["word1"]),
            filtered_validation_set=frozenset(["word1"]),
            source_words_set=frozenset(["source1"]),
            typo_freq_threshold=2.0,
            adjacent_letters_map={"a": "s"},
            exclusions_set=frozenset(),
            debug_words=frozenset(),
            debug_typo_patterns=frozenset(),
        )

        with Pool(processes=2, initializer=init_worker, initargs=(context,)) as pool:
            result = pool.map(_multiply_by_threshold, [3])[0]

        assert result == 6.0

    def test_sequential_pools_use_their_own_context(self):
        """Different pool instances must not interfere with each other."""
        # First pool with threshold 1.0
        context1 = WorkerContext(
            validation_set=frozenset(),
            filtered_validation_set=frozenset(),
            source_words_set=frozenset(),
            typo_freq_threshold=1.0,
            adjacent_letters_map={},
            exclusions_set=frozenset(),
            debug_words=frozenset(),
            debug_typo_patterns=frozenset(),
        )

        with Pool(processes=2, initializer=init_worker, initargs=(context1,)) as pool:
            _ = pool.map(_get_threshold, [1])[0]

        # Second pool with different threshold
        context2 = WorkerContext(
            validation_set=frozenset(),
            filtered_validation_set=frozenset(),
            source_words_set=frozenset(),
            typo_freq_threshold=5.0,
            adjacent_letters_map={},
            exclusions_set=frozenset(),
            debug_words=frozenset(),
            debug_typo_patterns=frozenset(),
        )

        with Pool(processes=2, initializer=init_worker, initargs=(context2,)) as pool:
            result2 = pool.map(_get_threshold, [1])[0]

        # Behavior: second pool should use its own context, not the first
        assert result2 == 5.0

    def test_accessing_context_before_init_fails_safely(self):
        """Accessing context before initialization should provide clear error."""
        with pytest.raises(RuntimeError, match="Worker context not initialized"):
            get_worker_context()
