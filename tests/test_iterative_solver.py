"""Integration tests for the iterative solver architecture."""

import pytest

from entroppy.core.boundaries import BoundaryIndex
from entroppy.resolution.passes import (
    CandidateSelectionPass,
    ConflictRemovalPass,
    PatternGeneralizationPass,
)
from entroppy.resolution.solver import IterativeSolver, PassContext
from entroppy.resolution.state import DictionaryState


class TestIterativeSolver:
    """Test the iterative solver architecture."""

    @pytest.mark.slow
    def test_basic_solver_convergence(self):
        """Test that the solver converges on a simple case."""
        # Create a simple typo map
        typo_map = {
            "teh": ["the"],
            "tehm": ["them"],
        }

        # Create validation sets
        validation_set = {"the", "them", "other"}
        source_words_set = {"the", "them"}

        # Create state
        state = DictionaryState(typo_map)

        # Create pass context
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

        # Create passes
        passes = [
            CandidateSelectionPass(pass_context),
            ConflictRemovalPass(pass_context),
        ]

        # Run solver
        solver = IterativeSolver(passes, max_iterations=5)
        result = solver.solve(state)

        # Verify convergence
        assert result.converged, "Solver should converge"
        assert result.iterations > 0, "Should run at least one iteration"
        assert len(result.corrections) > 0, "Should have corrections"

    @pytest.mark.slow
    def test_self_healing_conflict_resolution(self):
        """Test that conflicts trigger self-healing (retry with stricter boundaries).

        Scenario:
        1. "teh" -> "the" is added with NONE boundary
        2. "tehir" -> "their" is attempted with NONE boundary
        3. Conflict detected: "tehir" starts with "teh"
        4. "tehir" is removed and added to graveyard
        5. Next iteration: "tehir" is retried with LEFT boundary
        6. Should succeed since LEFT boundary is stricter
        """
        # Create typo map with conflict
        typo_map = {
            "teh": ["the"],
            "tehir": ["their"],
        }

        # Create validation sets that will cause NONE boundary for both
        validation_set = {"the", "their", "other"}
        source_words_set = {"the", "their"}

        # Create state
        state = DictionaryState(typo_map)

        # Create pass context
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

        # Create passes
        passes = [
            CandidateSelectionPass(pass_context),
            ConflictRemovalPass(pass_context),
        ]

        # Run solver
        solver = IterativeSolver(passes, max_iterations=10)
        result = solver.solve(state)

        # Verify results
        assert result.converged, "Solver should converge"
        assert len(result.corrections) == 2, "Both corrections should be present"

        # Check that we have both corrections (with appropriate boundaries)
        typos = {c[0] for c in result.corrections}
        assert "teh" in typos, "'teh' should be in corrections"
        assert "tehir" in typos, "'tehir' should be in corrections"

        # Verify that graveyard has entries (from the conflict)
        assert result.graveyard_size > 0, "Graveyard should have rejected corrections"

    @pytest.mark.slow
    def test_multiple_iterations_with_patterns(self):
        """Test that solver handles pattern generalization across iterations."""
        # Create typo map with pattern candidates
        typo_map = {
            "aer": ["are"],
            "ehr": ["her"],
            "oer": ["ore"],
        }

        # Create validation sets
        validation_set = {"are", "her", "ore", "other"}
        source_words_set = {"are", "her", "ore"}

        # Create state
        state = DictionaryState(typo_map)

        # Create pass context
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

        # Create passes (including pattern generalization)
        passes = [
            CandidateSelectionPass(pass_context),
            PatternGeneralizationPass(pass_context),
            ConflictRemovalPass(pass_context),
        ]

        # Run solver
        solver = IterativeSolver(passes, max_iterations=10)
        result = solver.solve(state)

        # Verify convergence
        assert result.converged, "Solver should converge"
        assert result.iterations > 0, "Should run at least one iteration"

        # Should have either corrections or patterns
        total_rules = len(result.corrections) + len(result.patterns)
        assert total_rules > 0, "Should have rules (corrections or patterns)"

    def test_platform_constraints_enforcement(self):
        """Test that platform constraints are enforced by the solver."""
        # This test would need a mock platform with constraints
        # For now, just verify the structure is in place


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
