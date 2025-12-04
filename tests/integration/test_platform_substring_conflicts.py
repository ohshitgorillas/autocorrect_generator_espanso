"""Integration tests for platform substring conflict resolution behavior.

These tests verify that cross-boundary substring conflicts are correctly detected
and resolved, particularly for QMK where boundary markers create substring relationships.
"""

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


class TestPlatformSubstringConflicts:
    """Tests for platform substring conflict detection and resolution behavior."""

    @pytest.mark.slow
    def test_qmk_detects_colon_prefix_substring_conflict(self, tmp_path):
        """QMK detects substring conflict between 'aemr' and ':aemr'."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("")

        include_file = tmp_path / "include.txt"
        include_file.write_text("america\namerican\namericana\n")

        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text("a -> s\ne -> w\nm -> n\nr -> t\n")

        output_dir = tmp_path / "output"

        config = Config(
            exclude=str(exclude_file),
            include=str(include_file),
            adjacent_letters=str(adjacent_file),
            output=str(output_dir),
            platform="qmk",
            max_corrections=1000,
            jobs=1,
            max_iterations=10,
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
        solver.solve(state)  # Side effect: generates output file

        # Read the output file
        output_file = list(output_dir.glob("*.txt"))[0]
        output_content = output_file.read_text()

        # Should not contain both 'aemr' and ':aemr'
        has_aemr = "aemr ->" in output_content or "aemr\t" in output_content
        has_colon_aemr = ":aemr ->" in output_content or ":aemr\t" in output_content

        assert not (
            has_aemr and has_colon_aemr
        ), "Output should not contain both 'aemr' and ':aemr'"

    @pytest.mark.slow
    def test_qmk_prefers_less_restrictive_boundary_when_safe(self, tmp_path):
        """QMK prefers NONE boundary over LEFT when NONE doesn't cause false triggers."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("")

        include_file = tmp_path / "include.txt"
        include_file.write_text("america\namerican\namericana\n")

        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text("a -> s\ne -> w\nm -> n\nr -> t\n")

        output_dir = tmp_path / "output"

        config = Config(
            exclude=str(exclude_file),
            include=str(include_file),
            adjacent_letters=str(adjacent_file),
            output=str(output_dir),
            platform="qmk",
            max_corrections=1000,
            jobs=1,
            max_iterations=10,
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
        solver.solve(state)  # Side effect: generates output file

        # Read the output file
        output_file = list(output_dir.glob("*.txt"))[0]
        output_content = output_file.read_text()

        # Should contain 'aemr' (NONE boundary) but not ':aemr' (LEFT boundary)
        has_aemr = "aemr ->" in output_content or "aemr\t" in output_content

        assert has_aemr, "Output should contain 'aemr' with NONE boundary when it's safe"

    @pytest.mark.slow
    def test_qmk_removes_colon_prefix_when_core_typo_is_safe(self, tmp_path):
        """QMK removes ':aemr' when 'aemr' with NONE boundary is safe."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("")

        include_file = tmp_path / "include.txt"
        include_file.write_text("america\namerican\namericana\n")

        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text("a -> s\ne -> w\nm -> n\nr -> t\n")

        output_dir = tmp_path / "output"

        config = Config(
            exclude=str(exclude_file),
            include=str(include_file),
            adjacent_letters=str(adjacent_file),
            output=str(output_dir),
            platform="qmk",
            max_corrections=1000,
            jobs=1,
            max_iterations=10,
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
        solver.solve(state)  # Side effect: generates output file

        # Read the output file
        output_file = list(output_dir.glob("*.txt"))[0]
        output_content = output_file.read_text()

        # Should not contain ':aemr'
        has_colon_aemr = ":aemr ->" in output_content or ":aemr\t" in output_content

        assert not has_colon_aemr, "Output should not contain ':aemr' when 'aemr' with NONE is safe"

    @pytest.mark.slow
    def test_qmk_output_compiles_without_substring_errors(self, tmp_path):
        """QMK output should not contain substring conflicts that cause compilation errors."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("")

        include_file = tmp_path / "include.txt"
        include_file.write_text("america\namerican\namericana\n")

        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text("a -> s\ne -> w\nm -> n\nr -> t\n")

        output_dir = tmp_path / "output"

        config = Config(
            exclude=str(exclude_file),
            include=str(include_file),
            adjacent_letters=str(adjacent_file),
            output=str(output_dir),
            platform="qmk",
            max_corrections=1000,
            jobs=1,
            max_iterations=10,
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
        solver.solve(state)  # Side effect: generates output file

        # Read the output file
        output_file = list(output_dir.glob("*.txt"))[0]
        output_lines = output_file.read_text().strip().split("\n")

        # Extract all formatted typos (left side of -> or tab)
        formatted_typos = []
        for line in output_lines:
            if "->" in line:
                formatted_typo = line.split("->")[0].strip()
            elif "\t" in line:
                formatted_typo = line.split("\t")[0].strip()
            else:
                continue
            if formatted_typo:
                formatted_typos.append(formatted_typo)

        # Check that no formatted typo is a substring of another
        for i, typo1 in enumerate(formatted_typos):
            for typo2 in formatted_typos[i + 1 :]:
                # Skip if they're identical
                if typo1 == typo2:
                    continue
                # Check if one is a substring of the other
                shorter, longer = (typo1, typo2) if len(typo1) < len(typo2) else (typo2, typo1)
                if shorter in longer and shorter != longer:
                    assert False, (
                        f"Substring conflict found: '{shorter}' is substring of '{longer}'"
                    )

    @pytest.mark.slow
    def test_qmk_handles_suffix_boundary_conflicts(self, tmp_path):
        """QMK detects substring conflicts with suffix boundaries (e.g., 'typo' vs 'typo:')."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("")

        include_file = tmp_path / "include.txt"
        include_file.write_text("test\nbest\nrest\n")

        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text("t -> y\ne -> w\ns -> a\nb -> v\nr -> t\n")

        output_dir = tmp_path / "output"

        config = Config(
            exclude=str(exclude_file),
            include=str(include_file),
            adjacent_letters=str(adjacent_file),
            output=str(output_dir),
            platform="qmk",
            max_corrections=1000,
            jobs=1,
            max_iterations=10,
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
        solver.solve(state)  # Side effect: generates output file

        # Read the output file
        output_file = list(output_dir.glob("*.txt"))[0]
        output_lines = output_file.read_text().strip().split("\n")

        # Extract all formatted typos
        formatted_typos = []
        for line in output_lines:
            if "->" in line:
                formatted_typo = line.split("->")[0].strip()
            elif "\t" in line:
                formatted_typo = line.split("\t")[0].strip()
            else:
                continue
            if formatted_typo:
                formatted_typos.append(formatted_typo)

        # Check that no typo ending with ':' is a substring of a typo without ':'
        # (e.g., 'test' should not coexist with 'test:')
        for typo1 in formatted_typos:
            for typo2 in formatted_typos:
                if typo1 == typo2:
                    continue
                # If one ends with ':' and the other doesn't, check substring relationship
                if typo1.endswith(":") and not typo2.endswith(":"):
                    core1 = typo1[:-1]  # Remove trailing ':'
                    if core1 == typo2:
                        assert False, (
                            f"Substring conflict: '{typo2}' and '{typo1}' should not both exist"
                        )

    @pytest.mark.slow
    def test_qmk_handles_both_boundary_conflicts(self, tmp_path):
        """QMK detects substring conflicts with BOTH boundaries (e.g., 'typo' vs ':typo:')."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("")

        include_file = tmp_path / "include.txt"
        include_file.write_text("word\n")

        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text("w -> q\no -> i\nr -> t\nd -> s\n")

        output_dir = tmp_path / "output"

        config = Config(
            exclude=str(exclude_file),
            include=str(include_file),
            adjacent_letters=str(adjacent_file),
            output=str(output_dir),
            platform="qmk",
            max_corrections=1000,
            jobs=1,
            max_iterations=10,
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
        solver.solve(state)  # Side effect: generates output file

        # Read the output file
        output_file = list(output_dir.glob("*.txt"))[0]
        output_lines = output_file.read_text().strip().split("\n")

        # Extract all formatted typos
        formatted_typos = []
        for line in output_lines:
            if "->" in line:
                formatted_typo = line.split("->")[0].strip()
            elif "\t" in line:
                formatted_typo = line.split("\t")[0].strip()
            else:
                continue
            if formatted_typo:
                formatted_typos.append(formatted_typo)

        # Check that no typo with ':typo:' is a substring of a typo without boundaries
        for typo1 in formatted_typos:
            for typo2 in formatted_typos:
                if typo1 == typo2:
                    continue
                # If one has both boundaries and the other has none, check substring relationship
                has_both_boundaries = typo1.startswith(":") and typo1.endswith(":")
                has_no_boundaries = not (typo2.startswith(":") or typo2.endswith(":"))
                if has_both_boundaries and has_no_boundaries:
                    core1 = typo1.strip(":")  # Remove both colons
                    if core1 == typo2:
                        assert False, (
                            f"Substring conflict: '{typo2}' and '{typo1}' should not both exist"
                        )
