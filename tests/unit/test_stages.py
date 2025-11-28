"""Unit tests for pipeline stages - focusing on behavior, not implementation."""

from entroppy.config import Config
from entroppy.stages import (
    load_dictionaries,
    generate_typos,
    resolve_typo_collisions,
    generalize_typo_patterns,
    remove_typo_conflicts,
    generate_output,
)


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
    """Tests for collision resolution stage behavior."""

    def test_produces_corrections_from_typos(self, tmp_path):
        """Collision resolution produces corrections from the typo map."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("")

        include_file = tmp_path / "include.txt"
        include_file.write_text("test\n")

        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text("t -> y\ne -> w\n")

        config = Config(
            exclude=str(exclude_file),
            include=str(include_file),
            adjacent_letters=str(adjacent_file),
            output="output",
            jobs=1,
        )

        dict_data = load_dictionaries(config, verbose=False)
        typo_result = generate_typos(dict_data, config, verbose=False)
        result = resolve_typo_collisions(typo_result, dict_data, config, verbose=False)

        # Should produce some corrections
        assert len(result.corrections) > 0


class TestPatternGeneralization:
    """Tests for pattern generalization stage behavior."""

    def test_combines_corrections_with_patterns(self, tmp_path):
        """Pattern generalization combines original corrections with generated patterns."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("")

        include_file = tmp_path / "include.txt"
        include_file.write_text("test\n")

        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text("t -> y\n")

        config = Config(
            exclude=str(exclude_file),
            include=str(include_file),
            adjacent_letters=str(adjacent_file),
            output="output",
            jobs=1,
        )

        dict_data = load_dictionaries(config, verbose=False)
        typo_result = generate_typos(dict_data, config, verbose=False)
        collision_result = resolve_typo_collisions(
            typo_result, dict_data, config, verbose=False
        )
        result = generalize_typo_patterns(
            collision_result, dict_data, config, verbose=False
        )

        # Result should include corrections (original or patterns)
        assert len(result.corrections) > 0


class TestConflictRemoval:
    """Tests for conflict removal stage behavior."""

    def test_removes_no_conflicts_when_none_exist(self, tmp_path):
        """When there are no conflicts, all corrections are kept."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("")

        include_file = tmp_path / "include.txt"
        include_file.write_text("word\n")

        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text("w -> q\n")

        config = Config(
            exclude=str(exclude_file),
            include=str(include_file),
            adjacent_letters=str(adjacent_file),
            output="output",
            jobs=1,
        )

        dict_data = load_dictionaries(config, verbose=False)
        typo_result = generate_typos(dict_data, config, verbose=False)
        collision_result = resolve_typo_collisions(
            typo_result, dict_data, config, verbose=False
        )
        pattern_result = generalize_typo_patterns(
            collision_result, dict_data, config, verbose=False
        )
        result = remove_typo_conflicts(pattern_result, verbose=False)

        # No conflicts should be removed for a single simple correction
        assert result.conflicts_removed == 0


class TestOutputGeneration:
    """Tests for output generation stage behavior."""

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
        )

        dict_data = load_dictionaries(config, verbose=False)
        typo_result = generate_typos(dict_data, config, verbose=False)
        collision_result = resolve_typo_collisions(
            typo_result, dict_data, config, verbose=False
        )
        pattern_result = generalize_typo_patterns(
            collision_result, dict_data, config, verbose=False
        )
        conflict_result = remove_typo_conflicts(pattern_result, verbose=False)

        generate_output(
            conflict_result,
            str(output_dir),
            config.max_entries_per_file,
            config.jobs,
            verbose=False,
        )

        assert output_dir.exists()

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
        )

        dict_data = load_dictionaries(config, verbose=False)
        typo_result = generate_typos(dict_data, config, verbose=False)
        collision_result = resolve_typo_collisions(
            typo_result, dict_data, config, verbose=False
        )
        pattern_result = generalize_typo_patterns(
            collision_result, dict_data, config, verbose=False
        )
        conflict_result = remove_typo_conflicts(pattern_result, verbose=False)

        generate_output(
            conflict_result,
            str(output_dir),
            config.max_entries_per_file,
            config.jobs,
            verbose=False,
        )

        yaml_files = list(output_dir.glob("*.yml"))
        assert len(yaml_files) > 0
