"""Iterative solver engine for dictionary optimization."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

from entroppy.core import BoundaryIndex
from entroppy.core.boundaries import BoundaryType
from entroppy.matching import ExclusionMatcher
from entroppy.platforms.base import PlatformBackend
from entroppy.processing.stages.data_models import DictionaryData

if TYPE_CHECKING:
    from entroppy.resolution.state import DictionaryState


@dataclass
class PassContext:
    """Context passed to each pass containing needed resources.

    This provides passes with access to validation sets, boundary indices,
    platform constraints, and other resources needed for their logic.
    """

    # Dictionary resources
    validation_set: set[str]
    filtered_validation_set: set[str]
    source_words_set: set[str]
    user_words_set: set[str]
    exclusion_matcher: ExclusionMatcher | None
    exclusion_set: set[str]  # Original exclusion patterns for worker context

    # Boundary detection indices
    validation_index: BoundaryIndex
    source_index: BoundaryIndex

    # Platform backend
    platform: PlatformBackend | None

    # Configuration
    min_typo_length: int
    collision_threshold: float
    jobs: int
    verbose: bool

    @classmethod
    def from_dictionary_data(
        cls,
        dictionary_data: DictionaryData,
        platform: PlatformBackend | None,
        min_typo_length: int,
        collision_threshold: float,
        jobs: int = 1,
        verbose: bool = False,
    ) -> "PassContext":
        """Create context from dictionary data.

        Args:
            dictionary_data: Dictionary data from Stage 1
            platform: Platform backend
            min_typo_length: Minimum typo length
            collision_threshold: Collision resolution threshold
            jobs: Number of parallel jobs
            verbose: Whether to show progress bars

        Returns:
            PassContext instance
        """
        # Build boundary indices
        # Use FULL validation set (not filtered) for false trigger checking
        # We need to check against ALL English words to prevent false triggers,
        # not just words that passed our filters
        validation_index = BoundaryIndex(dictionary_data.validation_set)
        source_index = BoundaryIndex(dictionary_data.source_words_set)

        return cls(
            validation_set=dictionary_data.validation_set,
            filtered_validation_set=dictionary_data.filtered_validation_set,
            source_words_set=dictionary_data.source_words_set,
            user_words_set=dictionary_data.user_words_set,
            exclusion_matcher=dictionary_data.exclusion_matcher,
            exclusion_set=dictionary_data.exclusions,
            validation_index=validation_index,
            source_index=source_index,
            platform=platform,
            min_typo_length=min_typo_length,
            collision_threshold=collision_threshold,
            jobs=jobs,
            verbose=verbose,
        )


class Pass(ABC):
    """Base class for solver passes.

    Each pass implements a single responsibility in the optimization pipeline.
    Passes run iteratively until the state converges (no more changes).
    """

    def __init__(self, context: PassContext) -> None:
        """Initialize the pass with context.

        Args:
            context: Shared context with resources
        """
        self.context = context

    @abstractmethod
    def run(self, state: "DictionaryState") -> None:
        """Run this pass on the current state.

        Args:
            state: The dictionary state to modify

        The pass should:
        1. Read from state.active_corrections, state.active_patterns, state.raw_typo_map
        2. Make changes via state.add_correction(), state.remove_correction(), etc.
        3. Check state.graveyard to avoid retrying failed corrections
        4. Use state.add_to_graveyard() to record rejections
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of this pass for logging."""


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

    def _get_state_counts(self, state: "DictionaryState") -> tuple[int, int, int]:
        """Get current state counts.

        Args:
            state: The dictionary state

        Returns:
            Tuple of (corrections_count, patterns_count, graveyard_count)
        """
        return (
            len(state.active_corrections),
            len(state.active_patterns),
            len(state.graveyard),
        )

    def _log_pass_changes(
        self,
        pass_name: str,
        corrections_delta: int,
        patterns_delta: int,
        graveyard_delta: int,
    ) -> None:
        """Log changes made by a pass.

        Args:
            pass_name: Name of the pass
            corrections_delta: Change in corrections count
            patterns_delta: Change in patterns count
            graveyard_delta: Change in graveyard count
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
        logger.info(f"  [{pass_name}] {', '.join(changes)}")

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
        pass_instance.run(state)

        corrections_after, patterns_after, graveyard_after = self._get_state_counts(state)

        corrections_delta = corrections_after - corrections_before
        patterns_delta = patterns_after - patterns_before
        graveyard_delta = graveyard_after - graveyard_before

        self._log_pass_changes(
            pass_instance.name, corrections_delta, patterns_delta, graveyard_delta
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
            post_pass.run(state)

            corrections_after, patterns_after, graveyard_after = self._get_state_counts(state)

            corrections_delta = corrections_after - corrections_before_pass
            patterns_delta = patterns_after - patterns_before_pass
            graveyard_delta = graveyard_after - graveyard_before_pass

            self._log_pass_changes(
                post_pass.name, corrections_delta, patterns_delta, graveyard_delta
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
            corrections_before, patterns_before, graveyard_before = self._get_state_counts(state)

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
                pass_instance, state, corrections_before, patterns_before, graveyard_before
            )

    def _log_iteration_start(self, iteration: int, state: "DictionaryState") -> None:
        """Log the start of an iteration.

        Args:
            iteration: Current iteration number
            state: The dictionary state
        """
        logger.info(f"\n--- Iteration {iteration} ---")
        corrections, patterns, graveyard = self._get_state_counts(state)
        logger.info(
            f"  Active corrections: {corrections}, "
            f"Active patterns: {patterns}, "
            f"Graveyard: {graveyard}"
        )

    def _check_convergence(
        self,
        state: "DictionaryState",
        iteration: int,
        previous_corrections: int,
        previous_patterns: int,
        previous_graveyard: int,
    ) -> tuple[bool, int, int, int]:
        """Check if the solver has converged.

        Args:
            state: The dictionary state
            iteration: Current iteration number
            previous_corrections: Corrections count from previous iteration
            previous_patterns: Patterns count from previous iteration
            previous_graveyard: Graveyard count from previous iteration

        Returns:
            Tuple of (converged, current_corrections, current_patterns, current_graveyard)
        """
        corrections, patterns, graveyard = self._get_state_counts(state)

        corrections_change = corrections - previous_corrections
        patterns_change = patterns - previous_patterns
        graveyard_change = graveyard - previous_graveyard

        converged = corrections_change == 0 and patterns_change == 0 and graveyard_change == 0

        if converged:
            logger.info(f"  ✓ Converged (no net changes in iteration {iteration})")
            state.clear_dirty_flag()
        else:
            logger.info(
                f"  State changed: corrections {corrections_change:+d}, "
                f"patterns {patterns_change:+d}, graveyard {graveyard_change:+d}"
            )

        return converged, corrections, patterns, graveyard

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

        corrections, patterns, graveyard = self._get_state_counts(state)
        logger.info(
            f"\nSolver completed: {iteration} iteration(s), "
            f"{corrections} corrections, "
            f"{patterns} patterns, "
            f"{graveyard} in graveyard"
        )

    def _create_result(
        self, state: "DictionaryState", iteration: int, converged: bool
    ) -> "SolverResult":
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

    def solve(self, state: "DictionaryState") -> "SolverResult":
        """Run the iterative solver until convergence.

        Args:
            state: The dictionary state to optimize

        Returns:
            SolverResult with final corrections and metadata
        """
        iteration = 0
        previous_corrections, previous_patterns, previous_graveyard = self._get_state_counts(state)

        logger.info(f"Starting iterative solver (max {self.max_iterations} iterations)")

        verbose = self.passes[0].context.verbose if self.passes else False

        while state.is_dirty and iteration < self.max_iterations:
            state.start_iteration()
            iteration += 1

            self._log_iteration_start(iteration, state)
            self._run_all_passes(state, verbose)

            converged, previous_corrections, previous_patterns, previous_graveyard = (
                self._check_convergence(
                    state, iteration, previous_corrections, previous_patterns, previous_graveyard
                )
            )

        converged = not state.is_dirty
        self._log_solver_completion(iteration, converged, state)

        return self._create_result(state, iteration, converged)


@dataclass
class SolverResult:
    """Result from the iterative solver.

    Contains the final optimized corrections and metadata about the solving process.
    """

    corrections: list[tuple[str, str, "BoundaryType"]]
    patterns: list[tuple[str, str, "BoundaryType"]]
    iterations: int
    converged: bool
    graveyard_size: int
    debug_trace: str
