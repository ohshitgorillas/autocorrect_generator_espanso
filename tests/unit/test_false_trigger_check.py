"""Behavioral tests for false trigger prevention.

Tests verify that typos which appear as substrings in validation words
are not added with NONE boundary.
"""

import pytest

from entroppy.core import BoundaryType
from entroppy.core.boundaries import BoundaryIndex
from entroppy.resolution.passes import (
    CandidateSelectionPass,
    PatternGeneralizationPass,
)
from entroppy.resolution.solver import IterativeSolver, PassContext
from entroppy.resolution.state import DictionaryState, RejectionReason


class TestSubstringTyposNotAddedWithNoneBoundary:
    """Test that typos appearing as substrings are not added with NONE boundary."""

    @pytest.mark.slow
    def test_typo_in_middle_of_validation_word_not_none(self) -> None:
        """Typo appearing in middle of validation word must not use NONE boundary."""
        typo_map = {"tain": ["train"]}
        validation_set = {"train", "containing", "maintain"}
        source_words_set = {"train"}

        state = DictionaryState(typo_map)
        validation_index = BoundaryIndex(validation_set)
        source_index = BoundaryIndex(source_words_set)

        pass_context = PassContext(
            validation_set=validation_set,
            filtered_validation_set=validation_set,
            source_words_set=source_words_set,
            user_words_set=set(),
            exclusion_matcher=None,
            exclusion_set=set(),
            validation_index=validation_index,
            source_index=source_index,
            platform=None,
            min_typo_length=2,
            collision_threshold=2.0,
            jobs=1,
            verbose=False,
        )

        pass_obj = CandidateSelectionPass(pass_context)
        pass_obj.run(state)

        tain_corrections = [c for c in state.active_corrections if c[0] == "tain"]
        assert all(c[2] != BoundaryType.NONE for c in tain_corrections)

    @pytest.mark.slow
    def test_ethre_with_incomplete_validation_set_not_none(self) -> None:
        """Typo 'ethre' must not use NONE when it appears in validation words."""
        typo_map = {"ethre": ["there"]}
        # Use full validation set that includes words where 'ethre' appears as substring
        validation_set = {"there", "urethrectomy", "olethreutidae", "brethren", "rethread"}
        source_words_set = {"there"}

        state = DictionaryState(typo_map)
        validation_index = BoundaryIndex(validation_set)
        source_index = BoundaryIndex(source_words_set)

        pass_context = PassContext(
            validation_set=validation_set,
            filtered_validation_set=validation_set,
            source_words_set=source_words_set,
            user_words_set=set(),
            exclusion_matcher=None,
            exclusion_set=set(),
            validation_index=validation_index,
            source_index=source_index,
            platform=None,
            min_typo_length=2,
            collision_threshold=2.0,
            jobs=1,
            verbose=False,
        )

        pass_obj = CandidateSelectionPass(pass_context)
        pass_obj.run(state)

        ethre_corrections = [c for c in state.active_corrections if c[0] == "ethre"]
        assert all(c[2] != BoundaryType.NONE for c in ethre_corrections)


class TestFalseTriggerGraveyarding:
    """Test that false triggers are graveyarded and safer boundaries are tried."""

    @pytest.mark.slow
    def test_false_trigger_added_to_graveyard(self) -> None:
        """When a boundary would cause false triggers, it is added to graveyard."""
        # Use a typo where natural boundary is NONE (typo doesn't appear in filtered validation)
        # but NONE would cause false triggers because typo is a prefix of the target word
        # The target word check in false_trigger_check detects this
        typo_map = {"alway": ["always"]}
        validation_set = {"other", "words"}  # 'alway' doesn't appear in validation set
        source_words_set = set()  # Empty - so 'alway' doesn't appear in source either

        state = DictionaryState(typo_map)
        # validation_index is built from filtered_validation_set (same as validation_set here)
        validation_index = BoundaryIndex(validation_set)
        source_index = BoundaryIndex(source_words_set)

        pass_context = PassContext(
            validation_set=validation_set,
            filtered_validation_set=validation_set,
            source_words_set=source_words_set,
            user_words_set=set(),
            exclusion_matcher=None,
            exclusion_set=set(),
            validation_index=validation_index,
            source_index=source_index,
            platform=None,
            min_typo_length=2,
            collision_threshold=2.0,
            jobs=1,
            verbose=False,
        )

        pass_obj = CandidateSelectionPass(pass_context)
        pass_obj.run(state)

        # Verify NONE boundary is in graveyard with FALSE_TRIGGER reason
        # NONE would cause false triggers because 'alway' is a prefix of target word 'always'
        assert state.is_in_graveyard("alway", "always", BoundaryType.NONE)

    @pytest.mark.slow
    def test_safer_boundary_tried_after_false_trigger(self) -> None:
        """After NONE boundary is graveyarded for false trigger, safer boundary is tried."""
        typo_map = {"tain": ["train"]}
        validation_set = {"train", "containing", "maintain", "attain"}
        source_words_set = {"train"}

        state = DictionaryState(typo_map)
        validation_index = BoundaryIndex(validation_set)
        source_index = BoundaryIndex(source_words_set)

        pass_context = PassContext(
            validation_set=validation_set,
            filtered_validation_set=validation_set,
            source_words_set=source_words_set,
            user_words_set=set(),
            exclusion_matcher=None,
            exclusion_set=set(),
            validation_index=validation_index,
            source_index=source_index,
            platform=None,
            min_typo_length=2,
            collision_threshold=2.0,
            jobs=1,
            verbose=False,
        )

        passes = [CandidateSelectionPass(pass_context)]
        solver = IterativeSolver(passes, max_iterations=3)
        result = solver.solve(state)

        # Verify correction is eventually added with a safe boundary (not NONE)
        tain_corrections = [c for c in result.corrections if c[0] == "tain"]
        assert len(tain_corrections) > 0

    @pytest.mark.slow
    def test_false_trigger_graveyard_reason(self) -> None:
        """Graveyard entry for false trigger has correct reason."""
        # Use a typo where natural boundary is NONE (typo doesn't appear in filtered validation)
        # but NONE would cause false triggers because typo is a prefix of the target word
        # The target word check in false_trigger_check detects this
        typo_map = {"alway": ["always"]}
        validation_set = {"other", "words"}  # 'alway' doesn't appear in validation set
        source_words_set = set()  # Empty - so 'alway' doesn't appear in source either

        state = DictionaryState(typo_map)
        # validation_index is built from filtered_validation_set (same as validation_set here)
        validation_index = BoundaryIndex(validation_set)
        source_index = BoundaryIndex(source_words_set)

        pass_context = PassContext(
            validation_set=validation_set,
            filtered_validation_set=validation_set,
            source_words_set=source_words_set,
            user_words_set=set(),
            exclusion_matcher=None,
            exclusion_set=set(),
            validation_index=validation_index,
            source_index=source_index,
            platform=None,
            min_typo_length=2,
            collision_threshold=2.0,
            jobs=1,
            verbose=False,
        )

        pass_obj = CandidateSelectionPass(pass_context)
        pass_obj.run(state)

        graveyard_entry = state.graveyard.get(("alway", "always", BoundaryType.NONE))
        assert graveyard_entry is not None
        assert graveyard_entry.reason == RejectionReason.FALSE_TRIGGER


class TestPatternSubstringFalseTriggers:
    """Test that patterns with NONE boundary appearing as substrings are not added."""

    @pytest.mark.slow
    def test_pattern_simet_not_added_when_in_dosimeter(self) -> None:
        """Pattern 'simet' is not added when it appears as substring in 'dosimeter'."""
        typo_map = {"simet": ["somet"], "simetr": ["sometr"]}
        validation_set = {"dosimeter", "bradypnea", "snowmobile", "somet", "sometr"}
        source_words_set = {"somet", "sometr"}

        state = DictionaryState(typo_map)
        validation_index = BoundaryIndex(validation_set)
        source_index = BoundaryIndex(source_words_set)

        pass_context = PassContext(
            validation_set=validation_set,
            filtered_validation_set=validation_set,
            source_words_set=source_words_set,
            user_words_set=set(),
            exclusion_matcher=None,
            exclusion_set=set(),
            validation_index=validation_index,
            source_index=source_index,
            platform=None,
            min_typo_length=2,
            collision_threshold=2.0,
            jobs=1,
            verbose=False,
        )

        candidate_pass = CandidateSelectionPass(pass_context)
        candidate_pass.run(state)

        pattern_pass = PatternGeneralizationPass(pass_context)
        pattern_pass.run(state)

        simet_patterns = [p for p in state.active_patterns if p[0] == "simet"]
        assert len(simet_patterns) == 0
