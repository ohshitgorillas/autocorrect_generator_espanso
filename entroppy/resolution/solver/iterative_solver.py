"""Iterative solver engine for dictionary optimization."""

import time
from typing import TYPE_CHECKING

from loguru import logger

from .convergence import _check_convergence, _get_state_counts
from .pass_context import Pass, SolverResult

if TYPE_CHECKING:
    from entroppy.resolution.state import DictionaryState


class IterativeSolver:
    """Orchestrator for the iterative dictionary optimization.

    Runs passes in sequence until convergence (no changes in a full iteration)
    or maximum iterations reached.
    """

    def __init__(
        self,
        passes: list[Pass],
        max_iterations: int,
    ) -> None:
        """Initialize the solver.

        Args:
            passes: List of passes to run in order
            max_iterations: Maximum iterations (from config.max_iterations)
        """
        self.passes = passes
        self.max_iterations = max_iterations

    def _find_conflict_removal_index(self) -> int | None:
        """Find the index of ConflictRemovalPass in the passes list.

        Returns:
            Index of ConflictRemovalPass, or None if not found
        """
        for i, pass_instance in enumerate(self.passes):
            if pass_instance.name == "ConflictRemoval":
                return i
        return None

    def _format_pass_time(self, elapsed_seconds: float) -> str:
        """Format elapsed time for pass logging.

        Args:
            elapsed_seconds: Elapsed time in seconds

        Returns:
            Formatted time string (e.g., "1m 12s", "45s", "2h 5m 30s")
        """
        if elapsed_seconds < 60:
            return f"{int(elapsed_seconds)}s"
        minutes, seconds = divmod(int(elapsed_seconds), 60)
        if minutes < 60:
            return f"{minutes}m {seconds}s"
        hours, minutes = divmod(minutes, 60)
        return f"{hours}h {minutes}m {seconds}s"

    def _log_pass_changes(
        self,
        pass_name: str,
        corrections_delta: int,
        patterns_delta: int,
        graveyard_delta: int,
        elapsed_time: float | None = None,
    ) -> None:
        """Log changes made by a pass.

        Args:
            pass_name: Name of the pass
            corrections_delta: Change in corrections count
            patterns_delta: Change in patterns count
            graveyard_delta: Change in graveyard count
            elapsed_time: Elapsed time in seconds (optional)
        """
        if corrections_delta == 0 and patterns_delta == 0 and graveyard_delta == 0:
            return

        changes = []
        if corrections_delta != 0:
            changes.append(f"corrections: {corrections_delta:+d}")
        if patterns_delta != 0:
            changes.append(f"patterns: {patterns_delta:+d}")
        if graveyard_delta != 0:
            changes.append(f"graveyard: {graveyard_delta:+d}")

        time_str = ""
        if elapsed_time is not None:
            time_str = f", completed in {self._format_pass_time(elapsed_time)}"

        logger.info(f"  [{pass_name}] {', '.join(changes)}{time_str}")

    def _run_single_pass(
        self,
        pass_instance: Pass,
        state: "DictionaryState",
        corrections_before: int,
        patterns_before: int,
        graveyard_before: int,
    ) -> tuple[int, int, int]:
        """Run a single pass and track changes.

        Args:
            pass_instance: The pass to run
            state: The dictionary state
            corrections_before: Corrections count before running pass
            patterns_before: Patterns count before running pass
            graveyard_before: Graveyard count before running pass

        Returns:
            Tuple of (corrections_after, patterns_after, graveyard_after)
        """
        start_time = time.time()
        pass_instance.run(state)
        elapsed_time = time.time() - start_time

        corrections_after, patterns_after, graveyard_after = _get_state_counts(state)

        corrections_delta = corrections_after - corrections_before
        patterns_delta = patterns_after - patterns_before
        graveyard_delta = graveyard_after - graveyard_before

        self._log_pass_changes(
            pass_instance.name,
            corrections_delta,
            patterns_delta,
            graveyard_delta,
            elapsed_time,
        )

        return corrections_after, patterns_after, graveyard_after

    def _run_passes_after_conflict_removal(
        self,
        state: "DictionaryState",
        conflict_removal_index: int,
        corrections_before: int,
        patterns_before: int,
        graveyard_before: int,
    ) -> None:
        """Run passes after ConflictRemovalPass.

        Args:
            state: The dictionary state
            conflict_removal_index: Index of ConflictRemovalPass
            corrections_before: Corrections count before running passes
            patterns_before: Patterns count before running passes
            graveyard_before: Graveyard count before running passes
        """
        passes_after = self.passes[conflict_removal_index + 1 :]
        corrections_before_pass = corrections_before
        patterns_before_pass = patterns_before
        graveyard_before_pass = graveyard_before

        for post_pass in passes_after:
            start_time = time.time()
            post_pass.run(state)
            elapsed_time = time.time() - start_time

            corrections_after, patterns_after, graveyard_after = _get_state_counts(state)

            corrections_delta = corrections_after - corrections_before_pass
            patterns_delta = patterns_after - patterns_before_pass
            graveyard_delta = graveyard_after - graveyard_before_pass

            self._log_pass_changes(
                post_pass.name,
                corrections_delta,
                patterns_delta,
                graveyard_delta,
                elapsed_time,
            )

            corrections_before_pass = corrections_after
            patterns_before_pass = patterns_after
            graveyard_before_pass = graveyard_after

    def _run_all_passes(self, state: "DictionaryState", verbose: bool) -> None:
        """Run all passes in sequence.

        Args:
            state: The dictionary state
            verbose: Whether to show progress bars
        """
        conflict_removal_index = self._find_conflict_removal_index()

        for i, pass_instance in enumerate(self.passes):
            corrections_before, patterns_before, graveyard_before = _get_state_counts(state)

            # Wrap passes after ConflictRemovalPass with progress bar
            if conflict_removal_index is not None and i == conflict_removal_index + 1 and verbose:
                self._run_passes_after_conflict_removal(
                    state,
                    conflict_removal_index,
                    corrections_before,
                    patterns_before,
                    graveyard_before,
                )
                break

            # Run pass normally (before or including ConflictRemovalPass)
            self._run_single_pass(
                pass_instance,
                state,
                corrections_before,
                patterns_before,
                graveyard_before,
            )

    def _log_iteration_start(self, iteration: int, state: "DictionaryState") -> None:
        """Log the start of an iteration.

        Args:
            iteration: Current iteration number
            state: The dictionary state
        """
        logger.info(f"\n--- Iteration {iteration} ---")
        corrections, patterns, graveyard = _get_state_counts(state)
        logger.info(
            f"  Active corrections: {corrections}, "
            f"Active patterns: {patterns}, "
            f"Graveyard: {graveyard}"
        )

    def _log_solver_completion(
        self, iteration: int, converged: bool, state: "DictionaryState"
    ) -> None:
        """Log solver completion information.

        Args:
            iteration: Number of iterations completed
            converged: Whether the solver converged
            state: The dictionary state
        """
        if not converged:
            logger.warning(
                f"  ⚠ Solver reached max iterations ({self.max_iterations}) without converging"
            )

        corrections, patterns, graveyard = _get_state_counts(state)
        logger.info(
            f"\nSolver completed: {iteration} iteration(s), "
            f"{corrections} corrections, "
            f"{patterns} patterns, "
            f"{graveyard} in graveyard"
        )

    def _create_result(
        self, state: "DictionaryState", iteration: int, converged: bool
    ) -> SolverResult:
        """Create the final SolverResult.

        Args:
            state: The dictionary state
            iteration: Number of iterations completed
            converged: Whether the solver converged

        Returns:
            SolverResult with final corrections and metadata
        """
        return SolverResult(
            corrections=list(state.active_corrections),
            patterns=list(state.active_patterns),
            iterations=iteration,
            converged=converged,
            graveyard_size=len(state.graveyard),
            debug_trace=state.get_debug_summary(),
        )

    def solve(self, state: "DictionaryState") -> SolverResult:
        """Run the iterative solver until convergence.

        Args:
            state: The dictionary state to optimize

        Returns:
            SolverResult with final corrections and metadata
        """
        iteration = 0
        previous_corrections, previous_patterns, previous_graveyard = _get_state_counts(state)

        logger.info(f"Starting iterative solver (max {self.max_iterations} iterations)")

        verbose = self.passes[0].context.verbose if self.passes else False

        while state.is_dirty and iteration < self.max_iterations:
            state.start_iteration()
            iteration += 1

            self._log_iteration_start(iteration, state)
            self._run_all_passes(state, verbose)

            converged, previous_corrections, previous_patterns, previous_graveyard = (
                _check_convergence(
                    state,
                    iteration,
                    previous_corrections,
                    previous_patterns,
                    previous_graveyard,
                )
            )

        converged = not state.is_dirty
        self._log_solver_completion(iteration, converged, state)

        return self._create_result(state, iteration, converged)
