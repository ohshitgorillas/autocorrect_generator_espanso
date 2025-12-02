"""Conflict Removal Pass - removes substring conflicts."""

from collections import defaultdict
from typing import TYPE_CHECKING

from entroppy.core import BoundaryType
from entroppy.resolution.conflicts import get_detector_for_boundary
from entroppy.resolution.state import RejectionReason
from entroppy.resolution.solver import Pass

if TYPE_CHECKING:
    from entroppy.resolution.state import DictionaryState
    from entroppy.resolution.solver import PassContext


class ConflictRemovalPass(Pass):
    """Removes corrections that conflict with shorter corrections.

    This pass enforces substring/overlap rules:
    - For LEFT/NONE/BOTH boundaries: longer typos starting with shorter typos
    - For RIGHT boundaries: longer typos ending with shorter typos

    When a conflict is detected, the longer correction is removed and added
    to the graveyard. This triggers self-healing: in the next iteration,
    CandidateSelectionPass will retry with a stricter boundary.

    Example:
        - "teh" -> "the" (NONE boundary) is active
        - "tehir" -> "their" (NONE boundary) is added
        - This pass detects conflict: "tehir" starts with "teh"
        - Removes "tehir" with NONE, adds to graveyard
        - Next iteration: CandidateSelectionPass retries "tehir" with LEFT/RIGHT/BOTH
    """

    @property
    def name(self) -> str:
        """Return the name of this pass."""
        return "ConflictRemoval"

    def run(self, state: "DictionaryState") -> None:
        """Run the conflict removal pass.

        Args:
            state: The dictionary state to modify
        """
        # Group active corrections by boundary type
        by_boundary = defaultdict(list)
        for correction in state.active_corrections:
            _, _, boundary = correction
            by_boundary[boundary].append(correction)

        # Process each boundary group separately
        for boundary, corrections in by_boundary.items():
            self._process_boundary_group(state, corrections, boundary)

    def _process_boundary_group(
        self,
        state: "DictionaryState",
        corrections: list[tuple[str, str, BoundaryType]],
        boundary: BoundaryType,
    ) -> None:
        """Process a single boundary group to find and remove conflicts.

        Args:
            state: The dictionary state
            corrections: List of corrections with the same boundary
            boundary: The boundary type for this group
        """
        if not corrections:
            return

        # Get the appropriate conflict detector for this boundary
        detector = get_detector_for_boundary(boundary)

        # Build lookup map from typo to full correction
        typo_to_correction = {c[0]: c for c in corrections}

        # Sort typos by length (shorter first)
        sorted_typos = sorted(typo_to_correction.keys(), key=len)

        # Track which typos are blocked
        typos_to_remove = set()

        # Build character-based index for efficient lookup
        # Maps character → list of shorter typos with that character at the relevant position
        candidates_by_char = defaultdict(list)

        for typo in sorted_typos:
            if not typo:
                continue

            index_key = detector.get_index_key(typo)

            # Check against candidates that share the same index character
            if index_key in candidates_by_char:
                for candidate in candidates_by_char[index_key]:
                    blocking_correction = self._check_if_blocked(
                        state,
                        typo,
                        candidate,
                        typo_to_correction,
                        detector,
                    )
                    if blocking_correction:
                        # Mark for removal
                        typos_to_remove.add(typo)
                        break  # No need to check other candidates

            # If not blocked, add to index for future comparisons
            if typo not in typos_to_remove:
                candidates_by_char[index_key].append(typo)

        # Remove all blocked corrections
        for typo in typos_to_remove:
            correction = typo_to_correction[typo]
            typo_str, word, boundary_type = correction

            # Remove from active set
            state.remove_correction(
                typo_str,
                word,
                boundary_type,
                self.name,
                f"Blocked by substring conflict",
            )

    def _check_if_blocked(
        self,
        state: "DictionaryState",
        long_typo: str,
        short_typo: str,
        typo_to_correction: dict[str, tuple[str, str, BoundaryType]],
        detector,
    ) -> tuple[str, str, BoundaryType] | None:
        """Check if a typo is blocked by a shorter candidate.

        Args:
            state: The dictionary state
            long_typo: The longer typo to check
            short_typo: The shorter candidate that might block it
            typo_to_correction: Map from typo to full correction
            detector: Conflict detector for this boundary type

        Returns:
            The blocking correction if blocked, None otherwise
        """
        # Quick substring check first
        if not detector.contains_substring(long_typo, short_typo):
            return None

        # Get the corrections
        long_correction = typo_to_correction[long_typo]
        short_correction = typo_to_correction[short_typo]

        long_word = long_correction[1]
        short_word = short_correction[1]
        boundary = long_correction[2]

        # Full conflict check
        if not detector.check_conflict(long_typo, short_typo, long_word, short_word):
            return None

        # This is a conflict - add to graveyard
        state.add_to_graveyard(
            long_typo,
            long_word,
            boundary,
            RejectionReason.BLOCKED_BY_CONFLICT,
            short_typo,
        )

        return short_correction
