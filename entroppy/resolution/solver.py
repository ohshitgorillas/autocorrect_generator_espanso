"""Iterative solver engine for dictionary optimization."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger
from tqdm import tqdm

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
        validation_index = BoundaryIndex(dictionary_data.filtered_validation_set)
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

    MAX_ITERATIONS = 10  # Safety limit to prevent infinite loops

    def __init__(
        self,
        passes: list[Pass],
        max_iterations: int | None = None,
    ) -> None:
        """Initialize the solver.

        Args:
            passes: List of passes to run in order
            max_iterations: Optional override for max iterations
        """
        self.passes = passes
        self.max_iterations = max_iterations or self.MAX_ITERATIONS

    def solve(self, state: "DictionaryState", verbose: bool = False) -> "SolverResult":
        """Run the iterative solver until convergence.

        Args:
            state: The dictionary state to optimize
            verbose: Whether to show progress bars

        Returns:
            SolverResult with final corrections and metadata
        """
        iteration = 0
        previous_corrections = len(state.active_corrections)
        previous_patterns = len(state.active_patterns)
        previous_graveyard = len(state.graveyard)

        logger.info(f"Starting iterative solver (max {self.max_iterations} iterations)")

        # Create progress bar for iterations
        # We don't know the exact number of iterations, so we'll use a manual update approach
        if verbose:
            iteration_pbar = tqdm(
                total=self.max_iterations,
                desc="Iterations",
                unit="iteration",
                initial=0,
            )
        else:
            iteration_pbar = None

        try:
            while state.is_dirty and iteration < self.max_iterations:
                state.start_iteration()
                iteration += 1

                if iteration_pbar:
                    iteration_pbar.update(1)
                    iteration_pbar.set_postfix(
                        corrections=len(state.active_corrections),
                        patterns=len(state.active_patterns),
                        graveyard=len(state.graveyard),
                    )

                logger.info(f"\n--- Iteration {iteration} ---")
                logger.info(
                    f"  Active corrections: {len(state.active_corrections)}, "
                    f"Active patterns: {len(state.active_patterns)}, "
                    f"Graveyard: {len(state.graveyard)}"
                )

                # Run all passes in sequence
                for pass_instance in self.passes:
                    corrections_before = len(state.active_corrections)
                    patterns_before = len(state.active_patterns)
                    graveyard_before = len(state.graveyard)

                    pass_instance.run(state)

                    corrections_after = len(state.active_corrections)
                    patterns_after = len(state.active_patterns)
                    graveyard_after = len(state.graveyard)

                    corrections_delta = corrections_after - corrections_before
                    patterns_delta = patterns_after - patterns_before
                    graveyard_delta = graveyard_after - graveyard_before

                    if corrections_delta != 0 or patterns_delta != 0 or graveyard_delta != 0:
                        changes = []
                        if corrections_delta != 0:
                            changes.append(f"corrections: {corrections_delta:+d}")
                        if patterns_delta != 0:
                            changes.append(f"patterns: {patterns_delta:+d}")
                        if graveyard_delta != 0:
                            changes.append(f"graveyard: {graveyard_delta:+d}")
                        logger.info(f"  [{pass_instance.name}] {', '.join(changes)}")

                # Check convergence progress
                corrections_change = len(state.active_corrections) - previous_corrections
                patterns_change = len(state.active_patterns) - previous_patterns
                graveyard_change = len(state.graveyard) - previous_graveyard

                # Check if we've converged (no net changes)
                converged_this_iteration = (
                    corrections_change == 0 and patterns_change == 0 and graveyard_change == 0
                )

                if converged_this_iteration:
                    logger.info(f"  ✓ Converged (no net changes in iteration {iteration})")
                    state.clear_dirty_flag()  # Mark as clean to exit loop
                    if iteration_pbar:
                        iteration_pbar.set_postfix(
                            corrections=len(state.active_corrections),
                            patterns=len(state.active_patterns),
                            graveyard=len(state.graveyard),
                            converged=True,
                        )
                else:
                    logger.info(
                        f"  State changed: corrections {corrections_change:+d}, "
                        f"patterns {patterns_change:+d}, graveyard {graveyard_change:+d}"
                    )

                previous_corrections = len(state.active_corrections)
                previous_patterns = len(state.active_patterns)
                previous_graveyard = len(state.graveyard)
        finally:
            if iteration_pbar:
                iteration_pbar.close()

        # Check if we converged or hit the limit
        converged = not state.is_dirty

        if not converged:
            logger.warning(
                f"  ⚠ Solver reached max iterations ({self.max_iterations}) without converging"
            )

        logger.info(
            f"\nSolver completed: {iteration} iteration(s), "
            f"{len(state.active_corrections)} corrections, "
            f"{len(state.active_patterns)} patterns, "
            f"{len(state.graveyard)} in graveyard"
        )

        return SolverResult(
            corrections=list(state.active_corrections),
            patterns=list(state.active_patterns),
            iterations=iteration,
            converged=converged,
            graveyard_size=len(state.graveyard),
            debug_trace=state.get_debug_summary(),
        )


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
