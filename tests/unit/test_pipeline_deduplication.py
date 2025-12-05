"""Tests for duplicate correction detection in pipeline."""

from entroppy.core import BoundaryType
from entroppy.resolution.solver import SolverResult


class TestPipelineDeduplication:
    """Tests to ensure pipeline removes duplicates when combining corrections and patterns."""

    def test_duplicate_in_both_lists_removed(self):
        """Same correction in both corrections and patterns appears only once after combining."""
        duplicate = ("ciunt", "count", BoundaryType.NONE)
        solver_result = SolverResult(
            corrections=[duplicate],
            patterns=[duplicate],  # Same correction also in patterns
            iterations=1,
            converged=True,
            graveyard_size=0,
            debug_trace="",
        )

        all_corrections = list(dict.fromkeys(solver_result.corrections + solver_result.patterns))

        assert all_corrections.count(duplicate) == 1
