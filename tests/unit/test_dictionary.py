"""Unit tests for dictionary loading behavior.

Tests verify dictionary and word list loading functions. Each test has a single
assertion and focuses on behavior.
"""

from unittest.mock import MagicMock, patch

import pytest

from entroppy.core import Config
from entroppy.data.dictionary import (
    load_adjacent_letters_map,
    load_exclusions,
    load_source_words,
    load_validation_dictionary,
    load_word_list,
)


class TestLoadValidationDictionary:
    """Test load_validation_dictionary behavior."""

    @patch("entroppy.data.dictionary.get_english_words_set")
    def test_loads_english_words_from_library(self, mock_get_words: MagicMock) -> None:
        """When called, loads English words from english-words library."""
        mock_get_words.return_value = {"test", "word", "example"}
        result = load_validation_dictionary(None, None, verbose=False)
        assert "test" in result

    @patch("entroppy.data.dictionary.get_english_words_set")
    def test_adds_custom_words_from_include_file(self, mock_get_words: MagicMock, tmp_path) -> None:
        """When include file provided, adds custom words to validation set."""
        mock_get_words.return_value = {"test"}
        include_file = tmp_path / "include.txt"
        include_file.write_text("customword\n")
        result = load_validation_dictionary(None, str(include_file), verbose=False)
        assert "customword" in result

    @patch("entroppy.data.dictionary.get_english_words_set")
    def test_filters_words_matching_exact_exclusion(
        self, mock_get_words: MagicMock, tmp_path
    ) -> None:
        """When exact exclusion provided, removes matching words from validation set."""
        mock_get_words.return_value = {"test", "word", "example"}
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("word\n")
        result = load_validation_dictionary(str(exclude_file), None, verbose=False)
        assert "word" not in result

    @patch("entroppy.data.dictionary.get_english_words_set")
    def test_filters_words_matching_wildcard_exclusion(
        self, mock_get_words: MagicMock, tmp_path
    ) -> None:
        """When wildcard exclusion provided, removes matching words from validation set."""
        mock_get_words.return_value = {"test", "testing", "word"}
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("test*\n")
        result = load_validation_dictionary(str(exclude_file), None, verbose=False)
        assert "test" not in result

    @patch("entroppy.data.dictionary.get_english_words_set")
    def test_ignores_typo_word_mapping_exclusions(
        self, mock_get_words: MagicMock, tmp_path
    ) -> None:
        """When exclusion contains typo->word mapping, ignores it for word filtering."""
        mock_get_words.return_value = {"test", "word"}
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("tset->test\n")
        result = load_validation_dictionary(str(exclude_file), None, verbose=False)
        assert "test" in result

    @patch("entroppy.data.dictionary.get_english_words_set")
    def test_raises_runtime_error_when_library_fails(self, mock_get_words: MagicMock) -> None:
        """When english-words library fails, raises RuntimeError."""
        mock_get_words.side_effect = Exception("Library error")
        with pytest.raises(RuntimeError, match="Failed to load validation dictionary"):
            load_validation_dictionary(None, None, verbose=False)

    @patch("entroppy.data.dictionary.get_english_words_set")
    def test_returns_all_words_when_no_exclusions(self, mock_get_words: MagicMock) -> None:
        """When no exclusions provided, returns all loaded words."""
        mock_get_words.return_value = {"test", "word", "example"}
        result = load_validation_dictionary(None, None, verbose=False)
        assert len(result) == 3


class TestLoadWordList:
    """Test load_word_list behavior."""

    def test_returns_empty_list_when_filepath_is_none(self) -> None:
        """When filepath is None, returns empty list."""
        result = load_word_list(None, verbose=False)
        assert result == []

    def test_loads_words_from_file(self, tmp_path) -> None:
        """When valid file provided, loads words from file."""
        word_file = tmp_path / "words.txt"
        word_file.write_text("test\nword\nexample\n")
        result = load_word_list(str(word_file), verbose=False)
        assert "test" in result

    def test_skips_comment_lines(self, tmp_path) -> None:
        """When file contains comment lines, skips them."""
        word_file = tmp_path / "words.txt"
        word_file.write_text("# comment\nword\n# another comment\n")
        result = load_word_list(str(word_file), verbose=False)
        assert "# comment" not in result

    def test_skips_empty_lines(self, tmp_path) -> None:
        """When file contains empty lines, skips them."""
        word_file = tmp_path / "words.txt"
        word_file.write_text("word\n\n\nanother\n")
        result = load_word_list(str(word_file), verbose=False)
        assert "" not in result

    def test_converts_words_to_lowercase(self, tmp_path) -> None:
        """When file contains uppercase words, converts them to lowercase."""
        word_file = tmp_path / "words.txt"
        word_file.write_text("TEST\nWord\n")
        result = load_word_list(str(word_file), verbose=False)
        assert "test" in result

    def test_skips_words_with_newline_characters(self, tmp_path) -> None:
        """When word contains newline character, skips it."""
        word_file = tmp_path / "words.txt"
        word_file.write_text("word\nvalid\nword\nwith\nnewline\n")
        result = load_word_list(str(word_file), verbose=False)
        assert "word\nwith\nnewline" not in result

    def test_skips_words_with_carriage_return_characters(self, tmp_path) -> None:
        """When word contains carriage return character, skips it."""
        word_file = tmp_path / "words.txt"
        word_file.write_text("word\rvalid\n")
        result = load_word_list(str(word_file), verbose=False)
        assert "word\r" not in result

    def test_skips_words_with_tab_characters(self, tmp_path) -> None:
        """When word contains tab character, skips it."""
        word_file = tmp_path / "words.txt"
        word_file.write_text("word\tvalid\n")
        result = load_word_list(str(word_file), verbose=False)
        assert "word\t" not in result

    def test_skips_words_with_backslash_characters(self, tmp_path) -> None:
        """When word contains backslash character, skips it."""
        word_file = tmp_path / "words.txt"
        word_file.write_text("word\\valid\n")
        result = load_word_list(str(word_file), verbose=False)
        assert "word\\" not in result

    def test_raises_file_not_found_error_when_file_missing(self) -> None:
        """When file does not exist, raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_word_list("/nonexistent/file.txt", verbose=False)

    def test_handles_utf8_encoding(self, tmp_path) -> None:
        """When file contains UTF-8 characters, loads them correctly."""
        word_file = tmp_path / "words.txt"
        word_file.write_text("café\nnaïve\n", encoding="utf-8")
        result = load_word_list(str(word_file), verbose=False)
        assert "café" in result


class TestLoadExclusions:
    """Test load_exclusions behavior."""

    def test_returns_empty_set_when_filepath_is_none(self) -> None:
        """When filepath is None, returns empty set."""
        result = load_exclusions(None, verbose=False)
        assert result == set()

    def test_loads_exclusion_patterns_from_file(self, tmp_path) -> None:
        """When valid file provided, loads exclusion patterns."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("test\nword*\n")
        result = load_exclusions(str(exclude_file), verbose=False)
        assert "test" in result

    def test_skips_comment_lines(self, tmp_path) -> None:
        """When file contains comment lines, skips them."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("# comment\ntest\n")
        result = load_exclusions(str(exclude_file), verbose=False)
        assert "# comment" not in result

    def test_skips_empty_lines(self, tmp_path) -> None:
        """When file contains empty lines, skips them."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("test\n\npattern\n")
        result = load_exclusions(str(exclude_file), verbose=False)
        assert "" not in result

    def test_preserves_pattern_case(self, tmp_path) -> None:
        """When file contains patterns, preserves their case."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("Test\nWORD*\n")
        result = load_exclusions(str(exclude_file), verbose=False)
        assert "Test" in result

    def test_raises_file_not_found_error_when_file_missing(self) -> None:
        """When file does not exist, raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_exclusions("/nonexistent/file.txt", verbose=False)

    def test_handles_typo_word_mapping_patterns(self, tmp_path) -> None:
        """When file contains typo->word mappings, loads them."""
        exclude_file = tmp_path / "exclude.txt"
        exclude_file.write_text("tset->test\n")
        result = load_exclusions(str(exclude_file), verbose=False)
        assert "tset->test" in result


class TestLoadAdjacentLettersMap:
    """Test load_adjacent_letters_map behavior."""

    def test_returns_none_when_filepath_is_none(self) -> None:
        """When filepath is None, returns None."""
        result = load_adjacent_letters_map(None, verbose=False)
        assert result is None

    def test_loads_adjacency_mappings_from_file(self, tmp_path) -> None:
        """When valid file provided, loads adjacency mappings."""
        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text("a -> e\no -> u\n")
        result = load_adjacent_letters_map(str(adjacent_file), verbose=False)
        assert "a" in result

    def test_parses_key_value_pairs_correctly(self, tmp_path) -> None:
        """When file contains key->value pairs, parses them correctly."""
        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text("a -> e\no -> u\n")
        result = load_adjacent_letters_map(str(adjacent_file), verbose=False)
        assert result["a"] == "e"

    def test_strips_whitespace_from_keys_and_values(self, tmp_path) -> None:
        """When file contains whitespace, strips it from keys and values."""
        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text(" a ->  e \n")
        result = load_adjacent_letters_map(str(adjacent_file), verbose=False)
        assert result["a"] == "e"

    def test_skips_comment_lines(self, tmp_path) -> None:
        """When file contains comment lines, skips them."""
        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text("# comment\na -> e\n")
        result = load_adjacent_letters_map(str(adjacent_file), verbose=False)
        assert "a" in result

    def test_skips_empty_lines(self, tmp_path) -> None:
        """When file contains empty lines, skips them."""
        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text("a -> e\n\nb -> f\n")
        result = load_adjacent_letters_map(str(adjacent_file), verbose=False)
        assert "a" in result

    def test_skips_malformed_lines(self, tmp_path) -> None:
        """When file contains malformed lines, skips them."""
        adjacent_file = tmp_path / "adjacent.txt"
        adjacent_file.write_text("a -> e\nmalformed\nb -> f\n")
        result = load_adjacent_letters_map(str(adjacent_file), verbose=False)
        assert "malformed" not in result

    def test_raises_file_not_found_error_when_file_missing(self) -> None:
        """When file does not exist, raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_adjacent_letters_map("/nonexistent/file.txt", verbose=False)


class TestLoadSourceWords:
    """Test load_source_words behavior."""

    def test_returns_empty_list_when_top_n_is_none(self) -> None:
        """When top_n is None, returns empty list."""
        config = Config(top_n=None)
        result = load_source_words(config, verbose=False)
        assert result == []

    @patch("entroppy.data.dictionary.top_n_list")
    def test_loads_words_from_wordfreq(self, mock_top_n: MagicMock) -> None:
        """When top_n is set, loads words from wordfreq."""
        mock_top_n.return_value = ["test", "word", "example"]
        config = Config(top_n=3)
        result = load_source_words(config, verbose=False)
        assert "test" in result

    @patch("entroppy.data.dictionary.top_n_list")
    def test_respects_top_n_limit(self, mock_top_n: MagicMock) -> None:
        """When top_n is set, returns only top N words."""
        mock_top_n.return_value = ["test", "word", "example", "extra", "more"]
        config = Config(top_n=3)
        result = load_source_words(config, verbose=False)
        assert len(result) == 3

    @patch("entroppy.data.dictionary.top_n_list")
    def test_filters_words_below_min_length(self, mock_top_n: MagicMock) -> None:
        """When words are below min_word_length, filters them out."""
        mock_top_n.return_value = ["ab", "test", "word"]
        config = Config(top_n=10, min_word_length=3)
        result = load_source_words(config, verbose=False)
        assert "ab" not in result

    @patch("entroppy.data.dictionary.top_n_list")
    def test_filters_words_above_max_length(self, mock_top_n: MagicMock) -> None:
        """When words are above max_word_length, filters them out."""
        mock_top_n.return_value = ["test", "verylongword", "word"]
        config = Config(top_n=10, max_word_length=5)
        result = load_source_words(config, verbose=False)
        assert "verylongword" not in result

    @patch("entroppy.data.dictionary.top_n_list")
    def test_filters_words_with_invalid_characters(self, mock_top_n: MagicMock) -> None:
        """When words contain invalid characters, filters them out."""
        mock_top_n.return_value = ["test", "word\n", "example"]
        config = Config(top_n=10)
        result = load_source_words(config, verbose=False)
        assert "word\n" not in result

    @patch("entroppy.data.dictionary.top_n_list")
    def test_converts_words_to_lowercase(self, mock_top_n: MagicMock) -> None:
        """When words are uppercase, converts them to lowercase."""
        mock_top_n.return_value = ["TEST", "Word"]
        config = Config(top_n=10)
        result = load_source_words(config, verbose=False)
        assert "test" in result

    @patch("entroppy.data.dictionary.top_n_list")
    def test_respects_min_length_boundary(self, mock_top_n: MagicMock) -> None:
        """When word length equals min_word_length, includes it."""
        mock_top_n.return_value = ["abc", "test"]
        config = Config(top_n=10, min_word_length=3)
        result = load_source_words(config, verbose=False)
        assert "abc" in result

    @patch("entroppy.data.dictionary.top_n_list")
    def test_respects_max_length_boundary(self, mock_top_n: MagicMock) -> None:
        """When word length equals max_word_length, includes it."""
        mock_top_n.return_value = ["test", "word"]
        config = Config(top_n=10, max_word_length=4)
        result = load_source_words(config, verbose=False)
        assert "test" in result

    @patch("entroppy.data.dictionary.top_n_list")
    def test_raises_runtime_error_when_wordfreq_fails(self, mock_top_n: MagicMock) -> None:
        """When wordfreq fails, raises RuntimeError."""
        mock_top_n.side_effect = Exception("wordfreq error")
        config = Config(top_n=10)
        with pytest.raises(RuntimeError, match="Failed to load source words from wordfreq"):
            load_source_words(config, verbose=False)

    @patch("entroppy.data.dictionary.top_n_list")
    def test_fetches_extra_words_for_filtering(self, mock_top_n: MagicMock) -> None:
        """When filtering is needed, fetches extra words from wordfreq."""
        mock_top_n.return_value = ["ab", "cd", "test", "word", "example"]
        config = Config(top_n=2, min_word_length=3)
        load_source_words(config, verbose=False)
        assert mock_top_n.call_args[0][1] == 6  # top_n * WORDFREQ_MULTIPLIER = 2 * 3
