"""Word processing and collision resolution."""

from typing import TYPE_CHECKING

from tqdm import tqdm
from wordfreq import word_frequency

from .boundaries import determine_boundaries
from .config import BoundaryType, Correction
from .conflict_resolution import resolve_conflicts_for_group
from .debug_utils import is_debug_word, is_debug_typo
from .exclusions import ExclusionMatcher
from .typos import generate_all_typos
from .pattern_matching import PatternMatcher

if TYPE_CHECKING:
    from .debug_utils import DebugTypoMatcher


def process_word(
    word: str,
    validation_set: set[str],
    filtered_validation_set: set[str],
    source_words: set[str],
    typo_freq_threshold: float,
    adj_letters_map: dict[str, str] | None,
    exclusions: set[str],
    debug_words: frozenset[str] = frozenset(),
    debug_typo_matcher: "DebugTypoMatcher | None" = None,
) -> tuple[list[Correction], list[str]]:
    """Process a single word and generate all valid corrections.

    Args:
        word: The word to generate typos for
        validation_set: Full validation dictionary (for checking if typo is a real word)
        filtered_validation_set: Filtered validation set
            (for boundary detection, excludes exclusion patterns)
        source_words: Set of source words
        typo_freq_threshold: Frequency threshold for typos
        adj_letters_map: Adjacent letters map for insertions/replacements
        exclusions: Set of exclusion patterns
        debug_words: Set of words to debug (exact matches)
        debug_typo_matcher: Matcher for debug typos (with wildcards/boundaries)

    Returns:
        Tuple of (corrections list, debug messages list)
    """
    corrections = []
    debug_messages = []
    is_debug = is_debug_word(word, debug_words)

    if is_debug:
        debug_messages.append(f"[DEBUG WORD: '{word}'] [Stage 2] Generating typos for debug word")

    typos = generate_all_typos(word, adj_letters_map)

    # Filter out typo->word patterns, keep only single word exclusion patterns
    word_exclusion_patterns = {p for p in exclusions if "->" not in p}
    exclusion_matcher = PatternMatcher(word_exclusion_patterns)

    for typo in typos:
        if typo == word:
            continue

        # Check if this typo is being debugged (before we know boundary)
        # For now, check with NONE boundary as a placeholder
        typo_debug_check = is_debug_typo(typo, BoundaryType.NONE, debug_typo_matcher)

        if is_debug:
            debug_messages.append(f"[DEBUG WORD: '{word}'] [Stage 2] Generated typo: {typo}")

        # Skip if typo is a source word (from includes file)
        if typo in source_words:
            if is_debug:
                debug_messages.append(
                    f"[DEBUG WORD: '{word}'] [Stage 2] Typo '{typo}' filtered - is a source word"
                )
            if typo_debug_check:
                debug_messages.append(
                    f"[DEBUG TYPO: '{typo}'] [Stage 2] Filtered - is a source word"
                )
            continue

        # Use full validation set to check if typo is a real word
        if typo in validation_set:
            if is_debug:
                debug_messages.append(
                    f"[DEBUG WORD: '{word}'] [Stage 2] Typo '{typo}' filtered - is a valid word"
                )
            if typo_debug_check:
                debug_messages.append(
                    f"[DEBUG TYPO: '{typo}'] [Stage 2] Filtered - is a valid word in dictionary"
                )
            continue

        # If user explicitly excludes a typo, it bypasses the frequency check.
        # This makes the user's exclusion the final authority.
        is_explicitly_excluded = exclusion_matcher.matches(typo)

        if not is_explicitly_excluded and typo_freq_threshold > 0.0:
            typo_freq = word_frequency(typo, "en")
            if typo_freq >= typo_freq_threshold:
                if is_debug:
                    debug_messages.append(
                        f"[DEBUG WORD: '{word}'] [Stage 2] Typo '{typo}' filtered - frequency {typo_freq:.2e} >= threshold {typo_freq_threshold:.2e}"
                    )
                if typo_debug_check:
                    debug_messages.append(
                        f"[DEBUG TYPO: '{typo}'] [Stage 2] Filtered - frequency {typo_freq:.2e} >= threshold {typo_freq_threshold:.2e}"
                    )
                continue

        # Use filtered validation set for boundary detection
        # This allows excluded patterns to not block valid typos
        boundary_type = determine_boundaries(
            typo, filtered_validation_set, source_words
        )

        if boundary_type is not None:
            # Now that we have the boundary, check if this typo matches any debug patterns
            if debug_typo_matcher:
                matched_patterns = debug_typo_matcher.get_matching_patterns(typo, boundary_type)
                if matched_patterns:
                    patterns_str = ", ".join(matched_patterns)
                    debug_messages.append(
                        f"[DEBUG TYPO: '{typo}' (matched: {patterns_str})] [Stage 2] Generated from word: {word} (boundary: {boundary_type.value})"
                    )

            if is_debug:
                debug_messages.append(
                    f"[DEBUG WORD: '{word}'] [Stage 2] Created correction: {typo} → {word} (boundary: {boundary_type.value})"
                )

            corrections.append((typo, word, boundary_type))
        else:
            # Boundary detection failed
            if is_debug:
                debug_messages.append(
                    f"[DEBUG WORD: '{word}'] [Stage 2] Typo '{typo}' filtered - boundary detection failed"
                )
            if typo_debug_check:
                debug_messages.append(
                    f"[DEBUG TYPO: '{typo}'] [Stage 2] Filtered - boundary detection failed"
                )

    return corrections, debug_messages


def choose_strictest_boundary(boundaries: list[BoundaryType]) -> BoundaryType:
    """Choose the strictest boundary type."""
    if BoundaryType.BOTH in boundaries:
        return BoundaryType.BOTH
    if BoundaryType.LEFT in boundaries and BoundaryType.RIGHT in boundaries:
        return BoundaryType.BOTH
    if BoundaryType.LEFT in boundaries:
        return BoundaryType.LEFT
    if BoundaryType.RIGHT in boundaries:
        return BoundaryType.RIGHT
    return BoundaryType.NONE


def resolve_collisions(
    typo_map: dict[str, list[tuple[str, BoundaryType]]],
    freq_ratio: float,
    min_typo_length: int,
    min_word_length: int,
    user_words: set[str],
    exclusion_matcher: ExclusionMatcher,
    debug_words: set[str] = set(),
    debug_typo_matcher: "DebugTypoMatcher | None" = None,
) -> tuple[list[Correction], list, list, list]:
    """Resolve collisions where multiple words map to same typo.

    Args:
        typo_map: Map of typos to (word, boundary) pairs
        freq_ratio: Minimum frequency ratio for collision resolution
        min_typo_length: Minimum typo length
        min_word_length: Minimum word length
        user_words: Set of user-provided words
        exclusion_matcher: Matcher for exclusion rules
        debug_words: Set of words to debug (exact matches)
        debug_typo_matcher: Matcher for debug typos (with wildcards/boundaries)

    Returns:
        Tuple of (final_corrections, skipped_collisions, skipped_short, excluded_corrections)
    """
    from .debug_utils import is_debug_correction, log_debug_correction, log_debug_word, log_debug_typo

    final_corrections = []
    skipped_collisions = []
    skipped_short = []
    excluded_corrections = []

    for typo, word_boundary_list in typo_map.items():
        unique_pairs = list(set(word_boundary_list))
        unique_words = list(set(w for w, _ in unique_pairs))

        if len(unique_words) == 1:
            word = unique_words[0]
            boundaries = [b for w, b in unique_pairs if w == word]
            boundary = choose_strictest_boundary(boundaries)

            if word in user_words and len(word) == 2:
                orig_boundary = boundary
                boundary = BoundaryType.BOTH
                # Debug logging for forced BOTH boundary
                correction_temp = (typo, word, boundary)
                if is_debug_correction(correction_temp, debug_words, debug_typo_matcher):
                    log_debug_correction(
                        correction_temp,
                        f"Forced BOTH boundary (2-letter user word, was {orig_boundary.value})",
                        debug_words,
                        debug_typo_matcher,
                        "Stage 3"
                    )

            # A short typo is permissible if it corrects to a word that is also short,
            # using the user's `min_word_length` as the threshold.
            if len(typo) < min_typo_length and len(word) > min_word_length:
                skipped_short.append((typo, word, len(typo)))
                # Debug logging
                correction_temp = (typo, word, boundary)
                if is_debug_correction(correction_temp, debug_words, debug_typo_matcher):
                    log_debug_correction(
                        correction_temp,
                        f"SKIPPED - typo length {len(typo)} < min_typo_length {min_typo_length} (word length {len(word)} > min_word_length {min_word_length})",
                        debug_words,
                        debug_typo_matcher,
                        "Stage 3"
                    )
            else:
                correction = (typo, word, boundary)
                if not exclusion_matcher.should_exclude(correction):
                    final_corrections.append(correction)
                    # Debug logging
                    if is_debug_correction(correction, debug_words, debug_typo_matcher):
                        log_debug_correction(
                            correction,
                            f"Selected (no collision, boundary: {boundary.value})",
                            debug_words,
                            debug_typo_matcher,
                            "Stage 3"
                        )
                else:
                    # Track which rule excluded this correction
                    matching_rule = exclusion_matcher.get_matching_rule(correction)
                    excluded_corrections.append((typo, word, matching_rule))
                    # Debug logging
                    if is_debug_correction(correction, debug_words, debug_typo_matcher):
                        log_debug_correction(
                            correction,
                            f"EXCLUDED by rule: {matching_rule}",
                            debug_words,
                            debug_typo_matcher,
                            "Stage 3"
                        )
        else:
            # Collision: multiple words compete for same typo
            word_freqs = [(w, word_frequency(w, "en")) for w in unique_words]
            word_freqs.sort(key=lambda x: x[1], reverse=True)

            most_common = word_freqs[0]
            second_most = word_freqs[1] if len(word_freqs) > 1 else (None, 0)

            ratio = (
                most_common[1] / second_most[1] if second_most[1] > 0 else float("inf")
            )

            # Check if any of the competing words are being debugged
            is_debug_collision = any(
                is_debug_correction((typo, w, BoundaryType.NONE), debug_words, debug_typo_matcher)
                for w in unique_words
            )

            if is_debug_collision:
                # Log collision details
                words_with_freqs = ", ".join([f"{w} (freq: {f:.2e})" for w, f in word_freqs])
                log_debug_typo(
                    typo,
                    f"Collision detected: {typo} → [{words_with_freqs}] (ratio: {ratio:.2f})",
                    [],
                    "Stage 3"
                )

            if ratio > freq_ratio:
                word = most_common[0]
                boundaries = [b for w, b in unique_pairs if w == word]
                boundary = choose_strictest_boundary(boundaries)

                if is_debug_collision:
                    log_debug_correction(
                        (typo, word, boundary),
                        f"Selected '{word}' (freq: {most_common[1]:.2e}) over '{second_most[0]}' (freq: {second_most[1]:.2e}), ratio: {ratio:.2f} > threshold {freq_ratio}",
                        debug_words,
                        debug_typo_matcher,
                        "Stage 3"
                    )

                if word in user_words and len(word) == 2:
                    boundary = BoundaryType.BOTH

                # A short typo is permissible if it corrects to a word that is also short,
                # using the user's `min_word_length` as the threshold.
                if len(typo) < min_typo_length and len(word) > min_word_length:
                    skipped_short.append((typo, word, len(typo)))
                    # Debug logging
                    correction_temp = (typo, word, boundary)
                    if is_debug_correction(correction_temp, debug_words, debug_typo_matcher):
                        log_debug_correction(
                            correction_temp,
                            f"SKIPPED after collision resolution - typo length {len(typo)} < min_typo_length {min_typo_length}",
                            debug_words,
                            debug_typo_matcher,
                            "Stage 3"
                        )
                else:
                    correction = (typo, word, boundary)
                    if not exclusion_matcher.should_exclude(correction):
                        final_corrections.append(correction)
                    else:
                        # Track which rule excluded this correction
                        matching_rule = exclusion_matcher.get_matching_rule(correction)
                        excluded_corrections.append((typo, word, matching_rule))
                        # Debug logging
                        if is_debug_correction(correction, debug_words, debug_typo_matcher):
                            log_debug_correction(
                                correction,
                                f"EXCLUDED after collision resolution by rule: {matching_rule}",
                                debug_words,
                                debug_typo_matcher,
                                "Stage 3"
                            )
            else:
                skipped_collisions.append((typo, unique_words, ratio))
                # Debug logging
                if is_debug_collision:
                    log_debug_typo(
                        typo,
                        f"SKIPPED - ambiguous collision, ratio {ratio:.2f} <= threshold {freq_ratio}",
                        [],
                        "Stage 3"
                    )

    return final_corrections, skipped_collisions, skipped_short, excluded_corrections


def remove_substring_conflicts(
    corrections: list[Correction],
    verbose: bool = False,
    debug_words: set[str] = set(),
    debug_typo_matcher: "DebugTypoMatcher | None" = None,
) -> list[Correction]:
    """Remove corrections where one typo is a substring of another WITH THE SAME BOUNDARY.

    When Espanso sees a typo, it triggers on the first (shortest) match from left to right.

    Example 1: If we have 'teh' → 'the' and 'tehir' → 'their' (both no boundary):
    - When typing "tehir", Espanso sees "teh" first and corrects to "the"
    - User continues typing "ir", getting "their"
    - The "tehir" correction is unreachable, so remove it

    Example 2: If we have 'toin' (no boundary) → 'ton' and 'toin' (right_word) → 'tion':
    - These have DIFFERENT boundaries, so they DON'T conflict
    - 'toin' (no boundary) matches standalone "toin"
    - 'toin' (right_word) matches as a suffix in "*toin"
    - Both can coexist

    Example 3: If we have 'toin' → 'tion' and 'atoin' → 'ation' (both RIGHT):
    - Both would match at end of "information"
    - "toin" makes "atoin" redundant—the "a" is useless
    - Remove "atoin" in favor of shorter "toin"

    Args:
        corrections: List of corrections to check for conflicts
        verbose: Whether to print verbose output
        debug_words: Set of words to debug (exact matches)
        debug_typo_matcher: Matcher for debug typos (with wildcards/boundaries)

    Returns:
        List of corrections with conflicts removed
    """
    # Group by boundary type - process each separately
    by_boundary = {}
    for correction in corrections:
        _, _, boundary = correction
        if boundary not in by_boundary:
            by_boundary[boundary] = []
        by_boundary[boundary].append(correction)

    # Process each boundary group
    final_corrections = []

    if verbose and len(by_boundary) > 1:
        groups_iter = tqdm(
            by_boundary.items(),
            desc="Removing conflicts",
            unit="boundary",
            total=len(by_boundary),
        )
    else:
        groups_iter = by_boundary.items()

    for boundary, group in groups_iter:
        final_corrections.extend(
            resolve_conflicts_for_group(group, boundary, debug_words, debug_typo_matcher)
        )

    return final_corrections
