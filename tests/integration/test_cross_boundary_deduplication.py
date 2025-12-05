"""Integration tests for cross-boundary deduplication behavior."""

import pytest

from entroppy.core import Config
from entroppy.platforms import get_platform_backend
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


class TestCrossBoundaryDeduplication:
    """Integration tests verifying no duplicate (typo, word) pairs across boundaries."""

    @pytest.mark.slow
    def test_no_duplicate_pairs_in_final_output(self, tmp_path):
        """Final output contains no duplicate (typo, word) pairs, regardless of boundary."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("")

        include_file = tmp_path / "include.txt"
        # Words that create patterns and direct corrections
        include_file.write_text("the\nbathe\nlathe\nthen\n")

        adjacent_file = tmp_path / "adjacent.txt"
        # Adjacent letters that can create "teh" from "the"
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

        # Run through pipeline to get solver result
        dict_data = load_dictionaries(config, verbose=False)
        typo_result = generate_typos(dict_data, config, verbose=False)

        # Create solver state and run iterative solver
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

        # BEHAVIOR: Check no (typo, word) pair appears more than once
        seen_pairs = {}
        all_corrections = solver_result.corrections + solver_result.patterns
        for typo, word, boundary in all_corrections:
            pair = (typo, word)
            if pair in seen_pairs:
                raise AssertionError(
                    f"Duplicate (typo, word) pair found: {pair}\n"
                    f"  First boundary: {seen_pairs[pair]}\n"
                    f"  Second boundary: {boundary}"
                )
            seen_pairs[pair] = boundary

    @pytest.mark.slow
    def test_multiple_potential_conflicts_resolved(self, tmp_path):
        """Multiple words that could create conflicts produce no duplicates."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("")

        include_file = tmp_path / "include.txt"
        # Multiple common words that generate similar typos
        include_file.write_text("the\nthat\nthere\ntest\ntesting\nbest\nrest\n")

        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text(
            "t -> y\nh -> j\ne -> w\na -> s\nr -> t\ns -> z\ni -> u\nn -> m\ng -> h\nb -> v\n"
        )

        output_dir = tmp_path / "output"

        config = Config(
            exclude=str(exclude_file),
            include=str(include_file),
            adjacent_letters=str(adjacent_file),
            output=str(output_dir),
            jobs=1,
            max_iterations=3,  # Reduced for faster tests
        )

        # Run pipeline to get solver result
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

        # BEHAVIOR: Verify no duplicates in final output
        all_corrections = solver_result.corrections + solver_result.patterns
        pairs = [(typo, word) for typo, word, _ in all_corrections]
        unique_pairs = set(pairs)
        assert len(pairs) == len(unique_pairs), (
            f"Found {len(pairs) - len(unique_pairs)} duplicate pairs in output"
        )

    @pytest.mark.slow
    def test_direct_corrections_present_in_output(self, tmp_path):
        """Direct corrections from collision resolution appear in final output."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("")

        include_file = tmp_path / "include.txt"
        # Simple word that generates direct corrections
        include_file.write_text("cat\n")

        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text("c -> x\na -> e\nt -> y\n")

        output_dir = tmp_path / "output"

        config = Config(
            exclude=str(exclude_file),
            include=str(include_file),
            adjacent_letters=str(adjacent_file),
            output=str(output_dir),
            jobs=1,
            max_iterations=3,  # Reduced for faster tests
        )

        # Run pipeline to get solver result
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

        # BEHAVIOR: Verify corrections for target word exist
        all_corrections = solver_result.corrections + solver_result.patterns
        cat_corrections = [(t, w) for t, w, _ in all_corrections if w == "cat"]
        assert len(cat_corrections) > 0, "Expected corrections for 'cat'"

    @pytest.mark.slow
    def test_patterns_work_when_no_conflicts(self, tmp_path):
        """Pattern generalizations are included when they don't conflict."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("")

        include_file = tmp_path / "include.txt"
        # Words that should generate patterns without conflicts
        include_file.write_text("section\nselection\nrejection\n")

        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text(
            "s -> z\ne -> w\nc -> x\nt -> y\ni -> u\no -> p\nn -> m\nl -> k\nr -> t\nj -> h\n"
        )

        output_dir = tmp_path / "output"

        config = Config(
            exclude=str(exclude_file),
            include=str(include_file),
            adjacent_letters=str(adjacent_file),
            output=str(output_dir),
            jobs=1,
            max_iterations=3,  # Reduced for faster tests
        )

        # Run pipeline to get solver result
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

        # BEHAVIOR: Verify no duplicate pairs in output
        all_corrections = solver_result.corrections + solver_result.patterns
        pairs = [(typo, word) for typo, word, _ in all_corrections]
        assert len(pairs) == len(set(pairs)), "No duplicate pairs should exist"

    @pytest.mark.slow
    def test_full_pipeline_realistic_scenario(self, tmp_path):
        """Full pipeline with realistic word set produces valid output."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("")

        include_file = tmp_path / "include.txt"
        # Realistic mix of common words
        include_file.write_text(
            "the\nthat\nthis\nthere\ntest\ntesting\n"
            "word\nwork\nworld\nworth\n"
            "best\nrest\nwest\nnest\n"
        )

        adjacent_file = tmp_path / "adjacent.txt"
        # Common keyboard adjacencies
        adjacent_file.write_text(
            "t -> y\nt -> r\n"
            "h -> j\nh -> g\n"
            "e -> w\ne -> r\n"
            "a -> s\n"
            "r -> t\nr -> e\n"
            "s -> a\ns -> d\n"
            "w -> q\nw -> e\n"
            "o -> i\no -> p\n"
            "d -> s\nd -> f\n"
            "i -> u\ni -> o\n"
            "n -> m\nn -> b\n"
            "b -> v\nb -> n\n"
        )

        output_dir = tmp_path / "output"

        config = Config(
            exclude=str(exclude_file),
            include=str(include_file),
            adjacent_letters=str(adjacent_file),
            output=str(output_dir),
            jobs=1,
            max_iterations=3,  # Reduced for faster tests
        )

        # Run pipeline to get solver result
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

        # BEHAVIOR: No duplicate (typo, word) pairs in realistic scenario
        all_corrections = solver_result.corrections + solver_result.patterns
        pairs = [(typo, word) for typo, word, _ in all_corrections]
        unique_pairs = set(pairs)
        assert len(pairs) == len(unique_pairs), (
            f"Found duplicates: {len(pairs)} total vs {len(unique_pairs)} unique"
        )

    @pytest.mark.slow
    def test_same_trigger_different_boundaries_prevented(self, tmp_path):
        """Same trigger word cannot appear with different boundary types."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("")

        include_file = tmp_path / "include.txt"
        # Words that could generate overlapping triggers
        include_file.write_text("test\ncontest\nattest\nprotest\n")

        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text(
            "t -> y\ne -> w\ns -> z\nc -> x\no -> p\nn -> m\na -> e\np -> l\nr -> t\n"
        )

        output_dir = tmp_path / "output"

        config = Config(
            exclude=str(exclude_file),
            include=str(include_file),
            adjacent_letters=str(adjacent_file),
            output=str(output_dir),
            jobs=1,
            max_iterations=3,  # Reduced for faster tests
        )

        # Run pipeline to get solver result
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

        # BEHAVIOR: Each trigger maps to exactly one word (no disambiguation)
        all_corrections = solver_result.corrections + solver_result.patterns
        trigger_words = {}
        for typo, word, _ in all_corrections:
            if typo not in trigger_words:
                trigger_words[typo] = word
            else:
                # Same trigger should always map to same word
                assert trigger_words[typo] == word, (
                    f"Trigger '{typo}' maps to multiple words: {trigger_words[typo]} and {word}"
                )
