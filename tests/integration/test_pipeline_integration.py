"""Integration tests for the refactored pipeline stages."""

import pytest
import yaml

from entroppy.core import Config
from entroppy.processing import run_pipeline


class TestPipelineIntegration:
    """Integration tests verifying the complete pipeline behavior."""

    @pytest.mark.slow
    def test_pipeline_produces_yaml_output(self, tmp_path):
        """Complete pipeline run produces YAML output files."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("")

        include_file = tmp_path / "include.txt"
        include_file.write_text("hello\nworld\n")

        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text("h -> g\ne -> w\nl -> k\no -> i\n")

        output_dir = tmp_path / "output"

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

    @pytest.mark.slow
    def test_pipeline_with_reports(self, tmp_path):
        """Pipeline generates reports when enabled."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("")

        include_file = tmp_path / "include.txt"
        include_file.write_text("test\n")

        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text("t -> y\n")

        output_dir = tmp_path / "output"
        reports_dir = tmp_path / "reports"

        config = Config(
            exclude=str(exclude_file),
            include=str(include_file),
            adjacent_letters=str(adjacent_file),
            output=str(output_dir),
            reports=str(reports_dir),
            jobs=1,
            max_iterations=3,  # Reduced for faster tests
        )

        run_pipeline(config)

        # Check reports directory was created
        assert reports_dir.exists()

    @pytest.mark.slow
    def test_pipeline_yaml_has_matches_field(self, tmp_path):
        """Generated YAML files contain the 'matches' field."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("")

        include_file = tmp_path / "include.txt"
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

        run_pipeline(config)

        yaml_files = list(output_dir.glob("*.yml"))
        # Read first YAML file and check structure
        with open(yaml_files[0], encoding="utf-8") as f:
            data = yaml.safe_load(f)
            assert "matches" in data

    @pytest.mark.slow
    def test_pipeline_with_multiprocessing(self, tmp_path):
        """Pipeline works correctly with multiple worker processes."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("")

        include_file = tmp_path / "include.txt"
        include_file.write_text("test\ndata\nwork\n")

        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text("t -> y\ne -> w\nd -> s\na -> e\nw -> q\no -> i\nr -> t\nk -> l\n")

        output_dir = tmp_path / "output"

        config = Config(
            exclude=str(exclude_file),
            include=str(include_file),
            adjacent_letters=str(adjacent_file),
            output=str(output_dir),
            jobs=2,  # Use 2 workers
            max_iterations=3,  # Reduced for faster tests
        )

        run_pipeline(config)

        yaml_files = list(output_dir.glob("*.yml"))
        assert len(yaml_files) > 0

    @pytest.mark.slow
    def test_pipeline_with_exclusion_patterns_completes(self, tmp_path):
        """Pipeline completes successfully when exclusion patterns are used."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("test\n")  # Exclude "test"

        include_file = tmp_path / "include.txt"
        include_file.write_text("best\n")  # Include "best"

        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text("b -> v\ne -> w\ns -> a\nt -> y\n")

        output_dir = tmp_path / "output"

        config = Config(
            exclude=str(exclude_file),
            include=str(include_file),
            adjacent_letters=str(adjacent_file),
            output=str(output_dir),
            jobs=1,
            max_iterations=3,  # Reduced for faster tests
        )

        run_pipeline(config)

        # Pipeline should complete and produce output
        yaml_files = list(output_dir.glob("*.yml"))
        assert len(yaml_files) > 0

    @pytest.mark.slow
    def test_pipeline_with_min_typo_length_completes(self, tmp_path):
        """Pipeline completes successfully with minimum typo length constraint."""
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
            min_typo_length=5,  # Very high minimum
            jobs=1,
            max_iterations=3,  # Reduced for faster tests
        )

        run_pipeline(config)

        # Pipeline should complete (may have no output due to high minimum)
        assert output_dir.exists()
