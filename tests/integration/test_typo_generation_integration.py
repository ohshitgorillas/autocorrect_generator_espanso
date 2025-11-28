"""Integration tests for typo generation with worker context."""

import pytest
import concurrent.futures

from entroppy.config import Config
from entroppy.stages.data_models import DictionaryData
from entroppy.stages.typo_generation import generate_typos


class TestTypoGenerationWithContext:
    """Integration tests verifying multiprocessing works with context."""

    @pytest.fixture
    def sample_dict_data(self):
        """Provide sample dictionary data for testing."""
        return DictionaryData(
            validation_set={"real", "word", "test"},
            filtered_validation_set={"real", "word", "test"},
            source_words=["hello", "world"],
            source_words_set={"hello", "world"},
            adjacent_letters_map={
                "h": ["g", "j"],
                "e": ["w", "r"],
                "l": ["k", "p"],
                "o": ["i", "p"],
                "w": ["q", "e"],
                "r": ["e", "t"],
                "d": ["s", "f"],
            },
            exclusions=set(),
        )

    @pytest.fixture
    def sample_config(self):
        """Provide sample config for testing."""
        config = Config()
        config.typo_freq_threshold = 0.0
        return config

    def test_single_threaded_generates_typos(self, sample_dict_data, sample_config):
        """Single-threaded mode should generate typos."""
        sample_config.jobs = 1

        result = generate_typos(sample_dict_data, sample_config, verbose=False)

        assert len(result.typo_map) > 0

    def test_multiprocessing_generates_typos(self, sample_dict_data, sample_config):
        """Multiprocessing mode should generate typos without globals."""
        sample_config.jobs = 2

        result = generate_typos(sample_dict_data, sample_config, verbose=False)

        assert len(result.typo_map) > 0

    def test_results_identical_single_vs_multi(self, sample_dict_data, sample_config):
        """Single and multi-threaded modes should produce identical results."""
        # Single-threaded
        sample_config.jobs = 1
        result_single = generate_typos(sample_dict_data, sample_config, verbose=False)

        # Multi-threaded
        sample_config.jobs = 2
        result_multi = generate_typos(sample_dict_data, sample_config, verbose=False)

        assert result_single.typo_map.keys() == result_multi.typo_map.keys()

    def test_multiprocessing_respects_config_threshold(self, sample_dict_data):
        """Workers should respect the frequency threshold from config."""
        config = Config()
        config.jobs = 2
        config.typo_freq_threshold = 0.0

        result_low = generate_typos(sample_dict_data, config, verbose=False)

        # Higher threshold should filter more
        config.typo_freq_threshold = 0.1
        result_high = generate_typos(sample_dict_data, config, verbose=False)

        # Behavior: higher threshold means fewer or equal typos
        assert len(result_high.typo_map) <= len(result_low.typo_map)


class TestConcurrentPipelineExecution:
    """Test that multiple pipelines can run concurrently without interference."""

    def test_concurrent_typo_generation_different_configs(self):
        """Multiple generate_typos calls with different configs should not interfere."""
        dict_data1 = DictionaryData(
            validation_set={"real"},
            filtered_validation_set={"real"},
            source_words=["hello"],
            source_words_set={"hello"},
            adjacent_letters_map={"h": ["g"], "e": ["w"], "l": ["k"], "o": ["i"]},
            exclusions=set(),
        )

        dict_data2 = DictionaryData(
            validation_set={"test"},
            filtered_validation_set={"test"},
            source_words=["world"],
            source_words_set={"world"},
            adjacent_letters_map={"w": ["q"], "o": ["i"], "r": ["e"], "l": ["k"], "d": ["s"]},
            exclusions=set(),
        )

        config1 = Config()
        config1.jobs = 2
        config1.typo_freq_threshold = 0.0

        config2 = Config()
        config2.jobs = 2
        config2.typo_freq_threshold = 0.0

        def run_pipeline1():
            return generate_typos(dict_data1, config1, verbose=False)

        def run_pipeline2():
            return generate_typos(dict_data2, config2, verbose=False)

        # Run both concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(run_pipeline1)
            future2 = executor.submit(run_pipeline2)

            result1 = future1.result()
            result2 = future2.result()

        # Behavior: both should complete successfully without interference
        assert len(result1.typo_map) > 0 and len(result2.typo_map) > 0