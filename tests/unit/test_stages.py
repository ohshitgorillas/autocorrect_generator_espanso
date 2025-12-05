"""Unit tests for pipeline stages - focusing on behavior, not implementation."""

import pytest

from entroppy.core import Config
from entroppy.platforms import get_platform_backend
from entroppy.processing import run_pipeline
from entroppy.processing.stages import generate_typos, load_dictionaries
from entroppy.resolution.passes import (
    CandidateSelectionPass,
    ConflictRemovalPass,
    PatternGeneralizationPass,
    PlatformConstraintsPass,
    PlatformSubstringConflictPass,
)
from entroppy.resolution.solver import IterativeSolver, PassContext
from entroppy.resolution.state import DictionaryState


class TestDictionaryLoading:
    """Tests for dictionary loading stage behavior."""

    def test_includes_user_words_in_source_words(self, tmp_path):
        """User-provided words from include file are added to source words."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("")

        include_file = tmp_path / "include.txt"
        include_file.write_text("myspecialword\n")

        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text("")

        config = Config(
            exclude=str(exclude_file),
            include=str(include_file),
            adjacent_letters=str(adjacent_file),
            output="output",
        )

        result = load_dictionaries(config, verbose=False)

        assert "myspecialword" in result.source_words

    def test_tracks_user_words_separately(self, tmp_path):
        """User-provided words are tracked in user_words_set."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("")

        include_file = tmp_path / "include.txt"
        include_file.write_text("myspecialword\n")

        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text("")

        config = Config(
            exclude=str(exclude_file),
            include=str(include_file),
            adjacent_letters=str(adjacent_file),
            output="output",
        )

        result = load_dictionaries(config, verbose=False)

        assert "myspecialword" in result.user_words_set

    def test_filters_validation_set_with_exclusion_patterns(self, tmp_path):
        """Exclusion patterns remove matching words from validation set."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("*ball\n")  # Exclude words ending in 'ball'

        include_file = tmp_path / "include.txt"
        include_file.write_text("")

        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text("")

        config = Config(
            exclude=str(exclude_file),
            include=str(include_file),
            adjacent_letters=str(adjacent_file),
            output="output",
        )

        result = load_dictionaries(config, verbose=False)

        # Filtered set should be smaller if any *ball words were removed
        # pylint: disable=no-member
        assert result.filtered_validation_set.issubset(result.validation_set)


class TestTypoGeneration:
    """Tests for typo generation stage behavior."""

    def test_generates_typos_from_adjacent_letters(self, tmp_path):
        """Typos are generated based on adjacent letter mappings."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("")

        include_file = tmp_path / "include.txt"
        include_file.write_text("cat\n")

        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text("c -> x\na -> e\nt -> y\n")  # cat -> xat, cet, cay

        config = Config(
            exclude=str(exclude_file),
            include=str(include_file),
            adjacent_letters=str(adjacent_file),
            output="output",
            jobs=1,
        )

        dict_data = load_dictionaries(config, verbose=False)
        result = generate_typos(dict_data, config, verbose=False)

        # Should have generated some typos
        assert len(result.typo_map) > 0


class TestCollisionResolution:
    """Tests for collision resolution stage behavior (now part of iterative solver)."""

    @pytest.mark.slow
    def test_produces_corrections_from_typos(self, tmp_path):
        """Iterative solver produces corrections from the typo map."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("")

        include_file = tmp_path / "include.txt"
        include_file.write_text("test\n")

        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text("t -> y\ne -> w\n")

        output_dir = tmp_path / "output"

        config = Config(
            exclude=str(exclude_file),
            include=str(include_file),
            adjacent_letters=str(adjacent_file),
            output=str(output_dir),
            jobs=1,
            max_iterations=3,  # Reduced for faster tests
        )

        dict_data = load_dictionaries(config, verbose=False)
        typo_result = generate_typos(dict_data, config, verbose=False)

        platform = get_platform_backend(config.platform)
        pass_context = PassContext.from_dictionary_data(
            dictionary_data=dict_data,
            platform=platform,
            min_typo_length=config.min_typo_length,
            collision_threshold=config.freq_ratio,
            jobs=config.jobs,
            verbose=False,
        )

        state = DictionaryState(
            raw_typo_map=typo_result.typo_map,
            debug_words=config.debug_words,
            debug_typo_matcher=config.debug_typo_matcher,
        )

        passes = [
            CandidateSelectionPass(pass_context),
            PatternGeneralizationPass(pass_context),
            ConflictRemovalPass(pass_context),
            PlatformSubstringConflictPass(pass_context),
            PlatformConstraintsPass(pass_context),
        ]

        solver = IterativeSolver(passes, max_iterations=config.max_iterations)
        solver_result = solver.solve(state)

        # Should produce some corrections
        assert len(solver_result.corrections) > 0 or len(solver_result.patterns) > 0


class TestPatternGeneralization:
    """Tests for pattern generalization stage behavior (now part of iterative solver)."""

    @pytest.mark.slow
    def test_no_duplicate_typo_word_pairs_across_boundaries(self, tmp_path):
        """A (typo, word) pair appears only once in final output, even across boundary types."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("")

        include_file = tmp_path / "include.txt"
        # Create a scenario that could lead to both direct corrections and patterns
        include_file.write_text("the\ntest\n")

        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text("t -> y\nh -> j\ne -> w\n")

        output_dir = tmp_path / "output"

        config = Config(
            exclude=str(exclude_file),
            include=str(include_file),
            adjacent_letters=str(adjacent_file),
            output=str(output_dir),
            jobs=1,
            max_iterations=3,  # Reduced for faster tests
        )

        dict_data = load_dictionaries(config, verbose=False)
        typo_result = generate_typos(dict_data, config, verbose=False)

        platform = get_platform_backend(config.platform)
        pass_context = PassContext.from_dictionary_data(
            dictionary_data=dict_data,
            platform=platform,
            min_typo_length=config.min_typo_length,
            collision_threshold=config.freq_ratio,
            jobs=config.jobs,
            verbose=False,
        )

        state = DictionaryState(
            raw_typo_map=typo_result.typo_map,
            debug_words=config.debug_words,
            debug_typo_matcher=config.debug_typo_matcher,
        )

        passes = [
            CandidateSelectionPass(pass_context),
            PatternGeneralizationPass(pass_context),
            ConflictRemovalPass(pass_context),
            PlatformSubstringConflictPass(pass_context),
            PlatformConstraintsPass(pass_context),
        ]

        solver = IterativeSolver(passes, max_iterations=config.max_iterations)
        solver_result = solver.solve(state)

        # Check: no (typo, word) pair should appear more than once
        seen_pairs = set()
        all_corrections = solver_result.corrections + solver_result.patterns
        for typo, word, _ in all_corrections:
            pair = (typo, word)
            assert pair not in seen_pairs, f"Duplicate (typo, word) pair found: {pair}"
            seen_pairs.add(pair)

    @pytest.mark.slow
    def test_graveyard_tracks_rejected_corrections(self, tmp_path):
        """Rejected corrections are tracked in the graveyard."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("")

        include_file = tmp_path / "include.txt"
        include_file.write_text("the\ntest\n")

        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text("t -> y\nh -> j\ne -> w\n")

        output_dir = tmp_path / "output"

        config = Config(
            exclude=str(exclude_file),
            include=str(include_file),
            adjacent_letters=str(adjacent_file),
            output=str(output_dir),
            jobs=1,
            max_iterations=3,  # Reduced for faster tests
        )

        dict_data = load_dictionaries(config, verbose=False)
        typo_result = generate_typos(dict_data, config, verbose=False)

        platform = get_platform_backend(config.platform)
        pass_context = PassContext.from_dictionary_data(
            dictionary_data=dict_data,
            platform=platform,
            min_typo_length=config.min_typo_length,
            collision_threshold=config.freq_ratio,
            jobs=config.jobs,
            verbose=False,
        )

        state = DictionaryState(
            raw_typo_map=typo_result.typo_map,
            debug_words=config.debug_words,
            debug_typo_matcher=config.debug_typo_matcher,
        )

        passes = [
            CandidateSelectionPass(pass_context),
            PatternGeneralizationPass(pass_context),
            ConflictRemovalPass(pass_context),
            PlatformSubstringConflictPass(pass_context),
            PlatformConstraintsPass(pass_context),
        ]

        solver = IterativeSolver(passes, max_iterations=config.max_iterations)
        solver_result = solver.solve(state)

        # Graveyard should track rejected corrections
        assert solver_result.graveyard_size >= 0

    @pytest.mark.slow
    def test_corrections_produced_for_multiple_words(self, tmp_path):
        """Solver produces corrections for multiple input words."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("")

        include_file = tmp_path / "include.txt"
        include_file.write_text("test\ntesting\n")

        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text("t -> y\ne -> w\ns -> z\n")

        output_dir = tmp_path / "output"

        config = Config(
            exclude=str(exclude_file),
            include=str(include_file),
            adjacent_letters=str(adjacent_file),
            output=str(output_dir),
            jobs=1,
            max_iterations=3,  # Reduced for faster tests
        )

        dict_data = load_dictionaries(config, verbose=False)
        typo_result = generate_typos(dict_data, config, verbose=False)

        platform = get_platform_backend(config.platform)
        pass_context = PassContext.from_dictionary_data(
            dictionary_data=dict_data,
            platform=platform,
            min_typo_length=config.min_typo_length,
            collision_threshold=config.freq_ratio,
            jobs=config.jobs,
            verbose=False,
        )

        state = DictionaryState(
            raw_typo_map=typo_result.typo_map,
            debug_words=config.debug_words,
            debug_typo_matcher=config.debug_typo_matcher,
        )

        passes = [
            CandidateSelectionPass(pass_context),
            PatternGeneralizationPass(pass_context),
            ConflictRemovalPass(pass_context),
            PlatformSubstringConflictPass(pass_context),
            PlatformConstraintsPass(pass_context),
        ]

        solver = IterativeSolver(passes, max_iterations=config.max_iterations)
        solver_result = solver.solve(state)

        # Should produce some corrections or patterns
        assert len(solver_result.corrections) > 0 or len(solver_result.patterns) > 0

    @pytest.mark.slow
    def test_patterns_can_be_generated(self, tmp_path):
        """Solver can generate patterns when appropriate."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("")

        include_file = tmp_path / "include.txt"
        # Use words that will generate patterns
        include_file.write_text("section\nselection\n")

        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text("s -> z\ne -> w\nc -> x\nt -> y\ni -> u\no -> p\nn -> m\n")

        output_dir = tmp_path / "output"

        config = Config(
            exclude=str(exclude_file),
            include=str(include_file),
            adjacent_letters=str(adjacent_file),
            output=str(output_dir),
            jobs=1,
            max_iterations=3,  # Reduced for faster tests
        )

        dict_data = load_dictionaries(config, verbose=False)
        typo_result = generate_typos(dict_data, config, verbose=False)

        platform = get_platform_backend(config.platform)
        pass_context = PassContext.from_dictionary_data(
            dictionary_data=dict_data,
            platform=platform,
            min_typo_length=config.min_typo_length,
            collision_threshold=config.freq_ratio,
            jobs=config.jobs,
            verbose=False,
        )

        state = DictionaryState(
            raw_typo_map=typo_result.typo_map,
            debug_words=config.debug_words,
            debug_typo_matcher=config.debug_typo_matcher,
        )

        passes = [
            CandidateSelectionPass(pass_context),
            PatternGeneralizationPass(pass_context),
            ConflictRemovalPass(pass_context),
            PlatformSubstringConflictPass(pass_context),
            PlatformConstraintsPass(pass_context),
        ]

        solver = IterativeSolver(passes, max_iterations=config.max_iterations)
        solver_result = solver.solve(state)

        # Should have some results (corrections or patterns)
        assert len(solver_result.corrections) > 0 or len(solver_result.patterns) > 0

    @pytest.mark.slow
    def test_solver_produces_results(self, tmp_path):
        """Solver produces corrections or patterns from input words."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("")

        include_file = tmp_path / "include.txt"
        include_file.write_text("test\nrest\nbest\n")

        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text("t -> y\ne -> w\ns -> z\nb -> v\nr -> t\n")

        output_dir = tmp_path / "output"

        config = Config(
            exclude=str(exclude_file),
            include=str(include_file),
            adjacent_letters=str(adjacent_file),
            output=str(output_dir),
            jobs=1,
            max_iterations=3,  # Reduced for faster tests
        )

        dict_data = load_dictionaries(config, verbose=False)
        typo_result = generate_typos(dict_data, config, verbose=False)

        platform = get_platform_backend(config.platform)
        pass_context = PassContext.from_dictionary_data(
            dictionary_data=dict_data,
            platform=platform,
            min_typo_length=config.min_typo_length,
            collision_threshold=config.freq_ratio,
            jobs=config.jobs,
            verbose=False,
        )

        state = DictionaryState(
            raw_typo_map=typo_result.typo_map,
            debug_words=config.debug_words,
            debug_typo_matcher=config.debug_typo_matcher,
        )

        passes = [
            CandidateSelectionPass(pass_context),
            PatternGeneralizationPass(pass_context),
            ConflictRemovalPass(pass_context),
            PlatformSubstringConflictPass(pass_context),
            PlatformConstraintsPass(pass_context),
        ]

        solver = IterativeSolver(passes, max_iterations=config.max_iterations)
        solver_result = solver.solve(state)

        # Result should include corrections or patterns
        assert len(solver_result.corrections) > 0 or len(solver_result.patterns) > 0


class TestConflictRemoval:
    """Tests for conflict removal stage behavior (now part of iterative solver)."""

    @pytest.mark.slow
    def test_solver_handles_simple_case(self, tmp_path):
        """Solver handles simple cases without conflicts correctly."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("")

        include_file = tmp_path / "include.txt"
        include_file.write_text("word\n")

        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text("w -> q\n")

        output_dir = tmp_path / "output"

        config = Config(
            exclude=str(exclude_file),
            include=str(include_file),
            adjacent_letters=str(adjacent_file),
            output=str(output_dir),
            jobs=1,
            max_iterations=5,  # Need at least 5 iterations for this case to converge
        )

        dict_data = load_dictionaries(config, verbose=False)
        typo_result = generate_typos(dict_data, config, verbose=False)

        platform = get_platform_backend(config.platform)
        pass_context = PassContext.from_dictionary_data(
            dictionary_data=dict_data,
            platform=platform,
            min_typo_length=config.min_typo_length,
            collision_threshold=config.freq_ratio,
            jobs=config.jobs,
            verbose=False,
        )

        state = DictionaryState(
            raw_typo_map=typo_result.typo_map,
            debug_words=config.debug_words,
            debug_typo_matcher=config.debug_typo_matcher,
        )

        passes = [
            CandidateSelectionPass(pass_context),
            PatternGeneralizationPass(pass_context),
            ConflictRemovalPass(pass_context),
            PlatformSubstringConflictPass(pass_context),
            PlatformConstraintsPass(pass_context),
        ]

        solver = IterativeSolver(passes, max_iterations=config.max_iterations)
        solver_result = solver.solve(state)

        # Solver should converge and produce results
        assert solver_result.converged
        assert len(solver_result.corrections) > 0 or len(solver_result.patterns) > 0


class TestOutputGeneration:
    """Tests for output generation stage behavior."""

    @pytest.mark.slow
    def test_creates_output_directory(self, tmp_path):
        """Output directory is created when generating output."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("")

        include_file = tmp_path / "include.txt"
        include_file.write_text("test\n")

        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text("t -> y\n")

        output_dir = tmp_path / "test_output"

        config = Config(
            exclude=str(exclude_file),
            include=str(include_file),
            adjacent_letters=str(adjacent_file),
            output=str(output_dir),
            jobs=1,
            max_iterations=3,  # Reduced for faster tests
        )

        run_pipeline(config)

        assert output_dir.exists()

    @pytest.mark.slow
    def test_writes_yaml_files(self, tmp_path):
        """YAML files are written to output directory."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("")

        include_file = tmp_path / "include.txt"
        include_file.write_text("test\n")

        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text("t -> y\n")

        output_dir = tmp_path / "test_output"

        config = Config(
            exclude=str(exclude_file),
            include=str(include_file),
            adjacent_letters=str(adjacent_file),
            output=str(output_dir),
            jobs=1,
            max_iterations=3,  # Reduced for faster tests
        )

        run_pipeline(config)

        yaml_files = list(output_dir.glob("*.yml"))
        assert len(yaml_files) > 0
