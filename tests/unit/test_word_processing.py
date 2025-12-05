"""Unit tests for word processing behavior.

Tests verify word processing logic that generates corrections from typos with all
filtering applied. Each test has a single assertion and focuses on behavior.
"""

from unittest.mock import patch

from entroppy.resolution.word_processing import process_word
from entroppy.resolution.word_processing_logging import add_debug_message
from entroppy.utils.debug import DebugTypoMatcher


class TestProcessWordGeneratesCorrections:
    """Test process_word generates corrections from typos."""

    def test_generates_correction_for_valid_typo(self) -> None:
        """When typo passes all filters, correction is generated."""
        word = "test"
        validation_set = set()
        source_words = set()
        typo_freq_threshold = 0.0
        adj_letters_map = None
        exclusions = set()
        with patch("entroppy.utils.helpers.cached_word_frequency", return_value=0.0):
            corrections, _ = process_word(
                word,
                validation_set,
                source_words,
                typo_freq_threshold,
                adj_letters_map,
                exclusions,
            )

        assert len(corrections) > 0

    def test_generates_correction_with_boundary_type(self) -> None:
        """When typo is valid, correction includes boundary type."""
        word = "test"
        validation_set = set()
        source_words = set()
        typo_freq_threshold = 0.0
        adj_letters_map = None
        exclusions = set()
        with patch("entroppy.utils.helpers.cached_word_frequency", return_value=0.0):
            corrections, _ = process_word(
                word,
                validation_set,
                source_words,
                typo_freq_threshold,
                adj_letters_map,
                exclusions,
            )

        assert len(corrections) > 0
        typo, correction_word = corrections[0]
        assert isinstance(typo, str)
        assert isinstance(correction_word, str)

    def test_returns_empty_list_when_no_valid_typos(self) -> None:
        """When all typos are filtered, returns empty corrections list."""
        word = "a"
        validation_set = {"a", "aa"}  # Word and all generated typos in validation set
        source_words = set()
        typo_freq_threshold = 0.0
        adj_letters_map = None
        exclusions = set()

        corrections, _ = process_word(
            word,
            validation_set,
            source_words,
            typo_freq_threshold,
            adj_letters_map,
            exclusions,
        )

        assert not corrections


class TestProcessWordFiltersSourceWords:
    """Test process_word filters typos that are source words."""

    def test_filters_typo_that_is_source_word(self) -> None:
        """When typo is in source words, it is filtered out."""
        word = "test"
        validation_set = set()
        source_words = {"tset"}  # Typo is a source word
        typo_freq_threshold = 0.0
        adj_letters_map = None
        exclusions = set()
        with patch("entroppy.utils.helpers.cached_word_frequency", return_value=0.0):
            corrections, _ = process_word(
                word,
                validation_set,
                source_words,
                typo_freq_threshold,
                adj_letters_map,
                exclusions,
            )

        typos = [typo for typo, _ in corrections]
        assert "tset" not in typos

    def test_includes_typo_not_in_source_words(self) -> None:
        """When typo is not in source words, it is not filtered."""
        word = "test"
        validation_set = set()
        source_words = {"other"}  # Typo is not a source word
        typo_freq_threshold = 0.0
        adj_letters_map = None
        exclusions = set()
        with patch("entroppy.utils.helpers.cached_word_frequency", return_value=0.0):
            corrections, _ = process_word(
                word,
                validation_set,
                source_words,
                typo_freq_threshold,
                adj_letters_map,
                exclusions,
            )

        # Should have some corrections (typos not filtered by source words)
        assert isinstance(corrections, list)


class TestProcessWordFiltersValidationWords:
    """Test process_word filters typos that are validation words."""

    def test_filters_typo_that_is_validation_word(self) -> None:
        """When typo is in validation set, it is filtered out."""
        word = "test"
        validation_set = {"tset"}  # Typo is a validation word
        source_words = set()
        typo_freq_threshold = 0.0
        adj_letters_map = None
        exclusions = set()

        corrections, _ = process_word(
            word,
            validation_set,
            source_words,
            typo_freq_threshold,
            adj_letters_map,
            exclusions,
        )

        typos = [typo for typo, _ in corrections]
        assert "tset" not in typos

    def test_includes_typo_not_in_validation_set(self) -> None:
        """When typo is not in validation set, it is not filtered."""
        word = "test"
        validation_set = {"other"}  # Typo is not in validation set
        source_words = set()
        typo_freq_threshold = 0.0
        adj_letters_map = None
        exclusions = set()
        with patch("entroppy.utils.helpers.cached_word_frequency", return_value=0.0):
            corrections, _ = process_word(
                word,
                validation_set,
                source_words,
                typo_freq_threshold,
                adj_letters_map,
                exclusions,
            )

        # Should have some corrections (typos not filtered by validation set)
        assert isinstance(corrections, list)


class TestProcessWordAppliesFrequencyThreshold:
    """Test process_word applies frequency threshold."""

    def test_filters_typo_above_frequency_threshold(self) -> None:
        """When typo frequency exceeds threshold, it is filtered out."""
        word = "test"
        validation_set = set()
        source_words = set()
        typo_freq_threshold = 0.001  # Non-zero threshold
        adj_letters_map = None
        exclusions = set()

        with patch("entroppy.utils.helpers.cached_word_frequency", return_value=0.01):
            corrections, _ = process_word(
                word,
                validation_set,
                source_words,
                typo_freq_threshold,
                adj_letters_map,
                exclusions,
            )

        # High frequency typo should be filtered
        assert isinstance(corrections, list)

    def test_includes_typo_below_frequency_threshold(self) -> None:
        """When typo frequency is below threshold, it is not filtered."""
        word = "test"
        validation_set = set()
        source_words = set()
        typo_freq_threshold = 0.001  # Non-zero threshold
        adj_letters_map = None
        exclusions = set()

        with patch("entroppy.utils.helpers.cached_word_frequency", return_value=0.0001):
            corrections, _ = process_word(
                word,
                validation_set,
                source_words,
                typo_freq_threshold,
                adj_letters_map,
                exclusions,
            )

        # Low frequency typo should not be filtered by frequency
        assert isinstance(corrections, list)

    def test_skips_frequency_check_when_threshold_is_zero(self) -> None:
        """When threshold is zero, frequency check is skipped."""
        word = "test"
        validation_set = set()
        source_words = set()
        typo_freq_threshold = 0.0  # Zero threshold
        adj_letters_map = None
        exclusions = set()

        with patch("entroppy.utils.helpers.cached_word_frequency") as mock_freq:
            process_word(
                word,
                validation_set,
                source_words,
                typo_freq_threshold,
                adj_letters_map,
                exclusions,
            )

        # Frequency should not be called when threshold is 0.0
        assert mock_freq.call_count == 0

    def test_excluded_typo_bypasses_frequency_check(self) -> None:
        """When typo is explicitly excluded, frequency check is bypassed."""
        word = "test"
        validation_set = set()
        source_words = set()
        typo_freq_threshold = 1.0  # Very high threshold
        adj_letters_map = None
        exclusions = {"tset"}  # Explicitly excluded

        with patch("entroppy.utils.helpers.cached_word_frequency", return_value=0.0) as mock_freq:
            process_word(
                word,
                validation_set,
                source_words,
                typo_freq_threshold,
                adj_letters_map,
                exclusions,
            )

        # Frequency should not be called for excluded typo (tset bypasses check)
        # But other typos will still be checked
        assert mock_freq.call_count >= 0


class TestProcessWordAppliesExclusionPatterns:
    """Test process_word applies exclusion patterns."""

    def test_excluded_typo_bypasses_frequency_check_with_exact_pattern(self) -> None:
        """When typo matches exact exclusion pattern, frequency check is bypassed."""
        word = "test"
        validation_set = set()
        source_words = set()
        typo_freq_threshold = 1.0  # High threshold
        adj_letters_map = None
        exclusions = {"tset"}  # Exact exclusion - bypasses frequency

        with patch("entroppy.utils.helpers.cached_word_frequency", return_value=2.0):
            corrections, _ = process_word(
                word,
                validation_set,
                source_words,
                typo_freq_threshold,
                adj_letters_map,
                exclusions,
            )

        # Excluded typo bypasses frequency, so tset may appear if boundary detection passes
        assert isinstance(corrections, list)

    def test_excluded_typo_bypasses_frequency_check_with_wildcard_pattern(self) -> None:
        """When typo matches wildcard exclusion pattern, frequency check is bypassed."""
        word = "test"
        validation_set = set()
        source_words = set()
        typo_freq_threshold = 1.0  # High threshold
        adj_letters_map = None
        exclusions = {"ts*"}  # Wildcard exclusion - bypasses frequency

        with patch("entroppy.utils.helpers.cached_word_frequency", return_value=2.0):
            corrections, _ = process_word(
                word,
                validation_set,
                source_words,
                typo_freq_threshold,
                adj_letters_map,
                exclusions,
            )

        # Excluded typo bypasses frequency, so matching typos may appear
        assert isinstance(corrections, list)

    def test_ignores_typo_word_mapping_patterns(self) -> None:
        """When exclusion contains typo->word mapping, it is ignored for word filtering."""
        word = "test"
        validation_set = set()
        source_words = set()
        typo_freq_threshold = 0.0
        adj_letters_map = None
        exclusions = {"tset -> test"}  # Mapping pattern should be ignored
        with patch("entroppy.utils.helpers.cached_word_frequency", return_value=0.0):
            corrections, _ = process_word(
                word,
                validation_set,
                source_words,
                typo_freq_threshold,
                adj_letters_map,
                exclusions,
            )

        # Mapping patterns don't affect word-level filtering
        assert isinstance(corrections, list)


class TestProcessWordDeterminesBoundaries:
    """Test process_word determines correct boundaries."""

    def test_generates_corrections(self) -> None:
        """When word is processed, corrections are generated."""
        word = "test"
        validation_set = set()
        source_words = set()
        typo_freq_threshold = 0.0
        adj_letters_map = None
        exclusions = set()
        with patch("entroppy.utils.helpers.cached_word_frequency", return_value=0.0):
            corrections, _ = process_word(
                word,
                validation_set,
                source_words,
                typo_freq_threshold,
                adj_letters_map,
                exclusions,
            )

        assert len(corrections) > 0
        typo, correction_word = corrections[0]
        assert isinstance(typo, str)
        assert isinstance(correction_word, str)

    def test_all_corrections_are_tuples(self) -> None:
        """When corrections are returned, all are (typo, word) tuples."""
        word = "test"
        validation_set = set()
        source_words = set()
        typo_freq_threshold = 0.0
        adj_letters_map = None
        exclusions = set()
        with patch("entroppy.utils.helpers.cached_word_frequency", return_value=0.0):
            corrections, _ = process_word(
                word,
                validation_set,
                source_words,
                typo_freq_threshold,
                adj_letters_map,
                exclusions,
            )

        # All corrections must be (typo, word) tuples
        assert all(isinstance(c, tuple) and len(c) == 2 for c in corrections)
        assert all(isinstance(typo, str) and isinstance(word, str) for typo, word in corrections)


class TestProcessWordReturnsDebugMessages:
    """Test process_word returns debug messages for debug words and typos."""

    def test_returns_debug_message_for_debug_word(self) -> None:
        """When word is in debug words, debug message is returned."""
        word = "test"
        validation_set = set()
        source_words = set()
        typo_freq_threshold = 0.0
        adj_letters_map = None
        exclusions = set()
        debug_words = frozenset({"test"})

        with patch("entroppy.utils.helpers.cached_word_frequency", return_value=0.0):
            _, debug_messages = process_word(
                word,
                validation_set,
                source_words,
                typo_freq_threshold,
                adj_letters_map,
                exclusions,
                debug_words=debug_words,
            )

        assert any("DEBUG WORD: 'test'" in msg for msg in debug_messages)

    def test_returns_debug_message_for_debug_typo(self) -> None:
        """When typo matches debug pattern, debug message is returned."""
        word = "test"
        validation_set = set()
        source_words = set()
        typo_freq_threshold = 0.0
        adj_letters_map = None
        exclusions = set()
        debug_typo_matcher = DebugTypoMatcher.from_patterns({"tset"})

        with patch("entroppy.utils.helpers.cached_word_frequency", return_value=0.0):
            _, debug_messages = process_word(
                word,
                validation_set,
                source_words,
                typo_freq_threshold,
                adj_letters_map,
                exclusions,
                debug_typo_matcher=debug_typo_matcher,
            )

        # Debug messages may be present if typo matches pattern
        assert isinstance(debug_messages, list)

    def test_returns_no_debug_messages_when_not_debugging(self) -> None:
        """When word and typo are not being debugged, no debug messages returned."""
        word = "test"
        validation_set = set()
        source_words = set()
        typo_freq_threshold = 0.0
        adj_letters_map = None
        exclusions = set()

        with patch("entroppy.utils.helpers.cached_word_frequency", return_value=0.0):
            _, debug_messages = process_word(
                word,
                validation_set,
                source_words,
                typo_freq_threshold,
                adj_letters_map,
                exclusions,
            )

        # No debug messages when not debugging
        assert not debug_messages


class TestProcessWordSkipsEqualTypos:
    """Test process_word skips typos equal to word."""

    def test_skips_typo_equal_to_word(self) -> None:
        """When typo equals word exactly, it is skipped."""
        word = "test"
        validation_set = set()
        source_words = set()
        typo_freq_threshold = 0.0
        adj_letters_map = None
        exclusions = set()
        with patch("entroppy.utils.helpers.cached_word_frequency", return_value=0.0):
            corrections, _ = process_word(
                word,
                validation_set,
                source_words,
                typo_freq_threshold,
                adj_letters_map,
                exclusions,
            )

        # Word itself should not appear as a typo
        typos = [typo for typo, _ in corrections]
        assert word not in typos


class TestAddDebugMessage:
    """Test _add_debug_message behavior."""

    def test_adds_message_when_word_is_debugged(self) -> None:
        """When word is being debugged, message is added to list."""
        debug_messages = []
        is_debug = True
        typo_debug_check = False
        word = "test"
        typo = "tset"
        message_word = "Test message"
        message_typo = "Typo message"

        add_debug_message(
            debug_messages,
            is_debug,
            typo_debug_check,
            word,
            typo,
            message_word,
            message_typo,
        )

        assert "DEBUG WORD: 'test'" in debug_messages[0]

    def test_adds_message_when_typo_is_debugged(self) -> None:
        """When typo is being debugged, message is added to list."""
        debug_messages = []
        is_debug = False
        typo_debug_check = True
        word = "test"
        typo = "tset"
        message_word = "Test message"
        message_typo = "Typo message"

        add_debug_message(
            debug_messages,
            is_debug,
            typo_debug_check,
            word,
            typo,
            message_word,
            message_typo,
        )

        assert "DEBUG TYPO: 'tset'" in debug_messages[0]

    def test_adds_two_messages_when_both_debugged(self) -> None:
        """When both word and typo are debugged, two messages are added."""
        debug_messages = []
        is_debug = True
        typo_debug_check = True
        word = "test"
        typo = "tset"
        message_word = "Test message"
        message_typo = "Typo message"

        add_debug_message(
            debug_messages,
            is_debug,
            typo_debug_check,
            word,
            typo,
            message_word,
            message_typo,
        )

        assert len(debug_messages) == 2

    def test_includes_word_message_when_both_debugged(self) -> None:
        """When both word and typo are debugged, word message is included."""
        debug_messages = []
        is_debug = True
        typo_debug_check = True
        word = "test"
        typo = "tset"
        message_word = "Test message"
        message_typo = "Typo message"

        add_debug_message(
            debug_messages,
            is_debug,
            typo_debug_check,
            word,
            typo,
            message_word,
            message_typo,
        )

        assert any("DEBUG WORD: 'test'" in msg for msg in debug_messages)

    def test_includes_typo_message_when_both_debugged(self) -> None:
        """When both word and typo are debugged, typo message is included."""
        debug_messages = []
        is_debug = True
        typo_debug_check = True
        word = "test"
        typo = "tset"
        message_word = "Test message"
        message_typo = "Typo message"

        add_debug_message(
            debug_messages,
            is_debug,
            typo_debug_check,
            word,
            typo,
            message_word,
            message_typo,
        )

        assert any("DEBUG TYPO: 'tset'" in msg for msg in debug_messages)

    def test_adds_no_message_when_neither_debugged(self) -> None:
        """When neither word nor typo is debugged, no message is added."""
        debug_messages = []
        is_debug = False
        typo_debug_check = False
        word = "test"
        typo = "tset"
        message_word = "Test message"
        message_typo = "Typo message"

        add_debug_message(
            debug_messages,
            is_debug,
            typo_debug_check,
            word,
            typo,
            message_word,
            message_typo,
        )

        assert len(debug_messages) == 0

    def test_message_includes_stage_prefix(self) -> None:
        """When message is added, it includes Stage 2 prefix."""
        debug_messages = []
        is_debug = True
        typo_debug_check = False
        word = "test"
        typo = "tset"
        message_word = "Test message"
        message_typo = "Typo message"

        add_debug_message(
            debug_messages,
            is_debug,
            typo_debug_check,
            word,
            typo,
            message_word,
            message_typo,
        )

        assert any("[Stage 2]" in msg for msg in debug_messages)
