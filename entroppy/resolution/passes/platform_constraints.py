"""Platform Constraints Pass - enforces platform-specific limits."""

from typing import TYPE_CHECKING, Any

from tqdm import tqdm

from entroppy.core import BoundaryType
from entroppy.platforms import PlatformConstraints
from entroppy.resolution.solver import Pass
from entroppy.resolution.state import RejectionReason
from entroppy.utils.debug import log_if_debug_correction

if TYPE_CHECKING:
    from entroppy.resolution.state import DictionaryState


class PlatformConstraintsPass(Pass):
    """Enforces platform-specific constraints and limits.

    This pass validates corrections against platform requirements:
    - Character set restrictions (e.g., QMK: only a-z and apostrophe)
    - Length limits for typos and words
    - Platform-specific format constraints

    Corrections that violate constraints are removed and added to the graveyard.
    """

    @property
    def name(self) -> str:
        """Return the name of this pass."""
        return "PlatformConstraints"

    def _check_correction_constraints(
        self,
        correction: tuple[str, str, BoundaryType],
        constraints: PlatformConstraints,
    ) -> str | None:
        """Check if a correction violates platform constraints.

        Args:
            correction: The correction to check
            constraints: Platform constraints

        Returns:
            Reason string if constraint violated, None otherwise
        """
        typo, word, boundary = correction

        # Check character constraints
        if constraints.allowed_chars:
            if not self._check_allowed_chars(typo, word, constraints.allowed_chars):
                return "Invalid characters"

        # Check length constraints
        if constraints.max_typo_length and len(typo) > constraints.max_typo_length:
            return f"Typo too long (>{constraints.max_typo_length})"

        if constraints.max_word_length and len(word) > constraints.max_word_length:
            return f"Word too long (>{constraints.max_word_length})"

        # Check boundary support
        if not constraints.supports_boundaries and boundary.value != "none":
            return "Platform doesn't support boundaries"

        return None

    def _remove_invalid_items(
        self,
        state: "DictionaryState",
        items_to_remove: list[tuple[tuple[str, str, BoundaryType], str]],
        is_pattern: bool,
    ) -> None:
        """Remove invalid corrections or patterns from state.

        Args:
            state: The dictionary state to modify
            items_to_remove: List of (item, reason) tuples
            is_pattern: True if removing patterns, False if removing corrections
        """
        for item, reason in items_to_remove:
            typo, word, boundary = item
            if is_pattern:
                state.remove_pattern(typo, word, boundary, self.name, reason)
            else:
                state.remove_correction(typo, word, boundary, self.name, reason)
            # pylint: disable=duplicate-code
            # Acceptable pattern: This is a function call to state.add_to_graveyard
            # with standard parameters. The similar code in platform_pass.py calls
            # the same function with the same parameters. This is expected when
            # multiple places need to add items to the graveyard for the same reason.
            state.add_to_graveyard(
                typo,
                word,
                boundary,
                RejectionReason.PLATFORM_CONSTRAINT,
                reason,
                pass_name=self.name,
            )

    def _check_items(
        self,
        items: list[tuple[str, str, BoundaryType]],
        constraints: PlatformConstraints,
        item_type: str,
        state: "DictionaryState",
    ) -> list[tuple[tuple[str, str, BoundaryType], str]]:
        """Check items against platform constraints.

        Args:
            items: List of corrections or patterns to check
            constraints: Platform constraints
            item_type: Type of items ("corrections" or "patterns")
            state: The dictionary state (for debug logging)

        Returns:
            List of (item, reason) tuples for items that violate constraints
        """
        items_to_remove = []
        if self.context.verbose:
            items_iter: Any = tqdm(
                items,
                desc=f"    {self.name} ({item_type})",
                unit=item_type[:-1],  # Remove 's' from end
                leave=False,
            )
        else:
            items_iter = items

        for item in items_iter:
            reason = self._check_correction_constraints(item, constraints)
            if reason:
                items_to_remove.append((item, reason))
                # Log removal for debug targets
                log_if_debug_correction(
                    item,
                    f"REMOVED - platform constraint violation: {reason}",
                    state.debug_words,
                    state.debug_typo_matcher,
                    "Stage 6",
                )
            else:
                # Log that item passed constraints check
                log_if_debug_correction(
                    item,
                    "Kept - passed platform constraints check",
                    state.debug_words,
                    state.debug_typo_matcher,
                    "Stage 6",
                )

        return items_to_remove

    def run(self, state: "DictionaryState") -> None:
        """Run the platform constraints pass.

        Args:
            state: The dictionary state to modify
        """
        if not self.context.platform:
            # No platform specified, skip constraints
            return

        # Get platform constraints
        constraints = self.context.platform.get_constraints()

        # Check corrections
        corrections_to_remove = self._check_items(
            list(state.active_corrections), constraints, "corrections", state
        )
        self._remove_invalid_items(state, corrections_to_remove, is_pattern=False)

        # Check patterns
        patterns_to_remove = self._check_items(
            list(state.active_patterns), constraints, "patterns", state
        )
        self._remove_invalid_items(state, patterns_to_remove, is_pattern=True)

    @staticmethod
    def _check_allowed_chars(typo: str, word: str, allowed_chars: set[str]) -> bool:
        """Check if typo and word only contain allowed characters.

        Args:
            typo: The typo string
            word: The correct word
            allowed_chars: Set of allowed characters

        Returns:
            True if all characters are allowed
        """
        # Check typo characters
        for char in typo:
            if char not in allowed_chars:
                return False

        # Check word characters
        for char in word:
            if char not in allowed_chars:
                return False

        return True
