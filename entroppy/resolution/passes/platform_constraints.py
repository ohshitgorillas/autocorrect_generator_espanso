"""Platform Constraints Pass - enforces platform-specific limits."""

from typing import TYPE_CHECKING, Any

from tqdm import tqdm

from entroppy.resolution.solver import Pass
from entroppy.resolution.state import RejectionReason

if TYPE_CHECKING:
    from entroppy.resolution.solver import PassContext
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

        # Check each active correction
        corrections_to_remove = []
        if self.context.verbose:
            corrections_iter: Any = tqdm(
                state.active_corrections,
                desc=f"    {self.name} (corrections)",
                unit="correction",
                leave=False,
            )
        else:
            corrections_iter = state.active_corrections

        for correction in corrections_iter:
            typo, word, boundary = correction

            # Check character constraints
            if constraints.allowed_chars:
                if not self._check_allowed_chars(typo, word, constraints.allowed_chars):
                    corrections_to_remove.append((correction, "Invalid characters"))
                    continue

            # Check length constraints
            if constraints.max_typo_length and len(typo) > constraints.max_typo_length:
                corrections_to_remove.append(
                    (correction, f"Typo too long (>{constraints.max_typo_length})")
                )
                continue

            if constraints.max_word_length and len(word) > constraints.max_word_length:
                corrections_to_remove.append(
                    (correction, f"Word too long (>{constraints.max_word_length})")
                )
                continue

            # Check boundary support
            if not constraints.supports_boundaries and boundary.value != "none":
                corrections_to_remove.append((correction, "Platform doesn't support boundaries"))
                continue

        # Remove invalid corrections
        for correction, reason in corrections_to_remove:
            typo, word, boundary = correction
            state.remove_correction(typo, word, boundary, self.name, reason)
            state.add_to_graveyard(
                typo,
                word,
                boundary,
                RejectionReason.PLATFORM_CONSTRAINT,
                reason,
            )

        # Also check patterns
        patterns_to_remove = []
        if self.context.verbose:
            patterns_iter: Any = tqdm(
                state.active_patterns,
                desc=f"    {self.name} (patterns)",
                unit="pattern",
                leave=False,
            )
        else:
            patterns_iter = state.active_patterns

        for pattern in patterns_iter:
            typo, word, boundary = pattern

            # Check character constraints
            if constraints.allowed_chars:
                if not self._check_allowed_chars(typo, word, constraints.allowed_chars):
                    patterns_to_remove.append((pattern, "Invalid characters"))
                    continue

            # Check length constraints
            if constraints.max_typo_length and len(typo) > constraints.max_typo_length:
                patterns_to_remove.append(
                    (pattern, f"Typo too long (>{constraints.max_typo_length})")
                )
                continue

            if constraints.max_word_length and len(word) > constraints.max_word_length:
                patterns_to_remove.append(
                    (pattern, f"Word too long (>{constraints.max_word_length})")
                )
                continue

            # Check boundary support
            if not constraints.supports_boundaries and boundary.value != "none":
                patterns_to_remove.append((pattern, "Platform doesn't support boundaries"))
                continue

        # Remove invalid patterns
        for pattern, reason in patterns_to_remove:
            typo, word, boundary = pattern
            state.remove_pattern(typo, word, boundary, self.name, reason)
            state.add_to_graveyard(
                typo,
                word,
                boundary,
                RejectionReason.PLATFORM_CONSTRAINT,
                reason,
            )

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
