"""Iterative solver engine for dictionary optimization."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from entroppy.core import BoundaryIndex
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

    # Boundary detection indices
    validation_index: BoundaryIndex
    source_index: BoundaryIndex

    # Platform backend
    platform: PlatformBackend | None

    # Configuration
    min_typo_length: int
    collision_threshold: float

    @classmethod
    def from_dictionary_data(
        cls,
        dictionary_data: DictionaryData,
        platform: PlatformBackend | None,
        min_typo_length: int,
        collision_threshold: float,
    ) -> "PassContext":
        """Create context from dictionary data.

        Args:
            dictionary_data: Dictionary data from Stage 1
            platform: Platform backend
            min_typo_length: Minimum typo length
            collision_threshold: Collision resolution threshold

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
            validation_index=validation_index,
            source_index=source_index,
            platform=platform,
            min_typo_length=min_typo_length,
            collision_threshold=collision_threshold,
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

    def solve(self, state: "DictionaryState") -> "SolverResult":
        """Run the iterative solver until convergence.

        Args:
            state: The dictionary state to optimize

        Returns:
            SolverResult with final corrections and metadata
        """
        iteration = 0

        while state.is_dirty and iteration < self.max_iterations:
            state.start_iteration()

            # Run all passes in sequence
            for pass_instance in self.passes:
                pass_instance.run(state)

            iteration += 1

        # Check if we converged or hit the limit
        converged = not state.is_dirty

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
