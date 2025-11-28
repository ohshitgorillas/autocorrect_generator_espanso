"""Unit tests for typo generation algorithms.

Tests verify typo generation behavior. Each test has exactly one assertion.
"""

from entroppy.typos import (
    generate_transpositions,
    generate_omissions,
    generate_duplications,
    generate_insertions,
    generate_replacements,
    generate_all_typos,
)


class TestGenerateTranspositions:
    """Test adjacent character transposition behavior."""

    def test_returns_n_minus_1_transpositions(self) -> None:
        """Four-character word produces three transpositions."""
        assert len(generate_transpositions("test")) == 3

    def test_returns_no_transpositions_for_single_char(self) -> None:
        """Single character word cannot be transposed."""
        assert not generate_transpositions("a")

    def test_produces_transposition_ba_from_ab(self) -> None:
        """Word 'ab' produces transposition 'ba'."""
        assert "ba" in generate_transpositions("ab")


class TestGenerateOmissions:
    """Test single character omission behavior."""

    def test_returns_n_omissions_for_n_char_word(self) -> None:
        """Five-character word produces five omissions."""
        assert len(generate_omissions("hello")) == 5

    def test_returns_omissions_for_four_char_minimum(self) -> None:
        """Four-character word at threshold produces omissions."""
        assert len(generate_omissions("test")) == 4

    def test_returns_no_omissions_below_four_chars(self) -> None:
        """Three-character word below threshold produces nothing."""
        assert not generate_omissions("abc")

    def test_produces_est_from_test(self) -> None:
        """Omitting first character of 'test' produces 'est'."""
        assert "est" in generate_omissions("test")


class TestGenerateDuplications:
    """Test character duplication behavior."""

    def test_returns_n_duplications_for_n_chars(self) -> None:
        """Four-character word produces four duplications."""
        assert len(generate_duplications("test")) == 4

    def test_produces_aa_from_a(self) -> None:
        """Single 'a' produces duplication 'aa'."""
        assert "aa" in generate_duplications("a")


class TestGenerateInsertions:
    """Test adjacent letter insertion behavior."""

    def test_returns_nothing_for_empty_adjacency_map(self) -> None:
        """Empty adjacency map produces no insertions."""
        assert not generate_insertions("test", {})

    def test_returns_nothing_when_chars_not_in_map(self) -> None:
        """When word characters not in map, produces nothing."""
        assert not generate_insertions("xyz", {"a": "b"})

    def test_inserts_before_and_after_each_position(self) -> None:
        """Single character with one adjacent produces two insertions."""
        assert len(generate_insertions("a", {"a": "b"})) == 2

    def test_produces_xa_from_a_with_adjacent_x(self) -> None:
        """Inserting 'x' before 'a' produces 'xa'."""
        assert "xa" in generate_insertions("a", {"a": "x"})

    def test_produces_ax_from_a_with_adjacent_x(self) -> None:
        """Inserting 'x' after 'a' produces 'ax'."""
        assert "ax" in generate_insertions("a", {"a": "x"})


class TestGenerateReplacements:
    """Test character replacement behavior."""

    def test_returns_nothing_for_empty_adjacency_map(self) -> None:
        """Empty adjacency map produces no replacements."""
        assert not generate_replacements("test", {})

    def test_returns_nothing_when_chars_not_in_map(self) -> None:
        """When word characters not in map, produces nothing."""
        assert not generate_replacements("xyz", {"a": "b"})

    def test_returns_one_replacement_per_char(self) -> None:
        """Single character with one adjacent produces one replacement."""
        assert len(generate_replacements("a", {"a": "x"})) == 1

    def test_produces_x_from_a_with_adjacent_x(self) -> None:
        """Replacing 'a' with adjacent 'x' produces 'x'."""
        assert "x" in generate_replacements("a", {"a": "x"})

    def test_produces_xb_from_ab_replacing_a(self) -> None:
        """Replacing first char of 'ab' with 'x' produces 'xb'."""
        assert "xb" in generate_replacements("ab", {"a": "x"})


class TestGenerateAllTypos:
    """Test combined typo generation behavior."""

    def test_includes_transpositions(self) -> None:
        """Result includes transposition 'ba' from 'ab'."""
        assert "ba" in generate_all_typos("ab")

    def test_includes_omissions_for_four_plus_chars(self) -> None:
        """Result includes omission 'est' from 'test'."""
        assert "est" in generate_all_typos("test")

    def test_includes_duplications(self) -> None:
        """Result includes duplication 'aab' from 'ab'."""
        assert "aab" in generate_all_typos("ab")

    def test_includes_insertions_when_map_provided(self) -> None:
        """With adjacency map, includes insertion 'xa' before 'a'."""
        assert "xa" in generate_all_typos("a", {"a": "x"})

    def test_includes_replacements_when_map_provided(self) -> None:
        """With adjacency map, includes replacement 'x' from 'a'."""
        assert "x" in generate_all_typos("a", {"a": "x"})

    def test_returns_nothing_for_empty_string(self) -> None:
        """Empty string produces no typos."""
        assert not generate_all_typos("")

    def test_excludes_insertions_without_map(self) -> None:
        """Without map, 'xa' is not generated from 'a'."""
        assert "xa" not in generate_all_typos("ace", None)
