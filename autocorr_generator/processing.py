"""Word processing and collision resolution."""

from wordfreq import word_frequency

from .boundaries import determine_boundaries
from .config import BoundaryType, Correction
from .exclusions import ExclusionMatcher
from .typos import generate_all_typos
from .utils import compile_wildcard_regex


def process_word(
    word: str,
    validation_set: set[str],
    filtered_validation_set: set[str],
    source_words: set[str],
    typo_freq_threshold: float,
    adj_letters_map: dict[str, str] | None,
    exclusions: set[str],
) -> list[Correction]:
    """Process a single word and generate all valid corrections.

    Args:
        word: The word to generate typos for
        validation_set: Full validation dictionary (for checking if typo is a real word)
        filtered_validation_set: Filtered validation set (for boundary detection, excludes exclusion patterns)
        source_words: Set of source words
        typo_freq_threshold: Frequency threshold for typos
        adj_letters_map: Adjacent letters map for insertions/replacements
    """
    corrections = []
    typos = generate_all_typos(word, adj_letters_map)

    # Compile exclusion patterns once for efficiency
    exact_exclusions = {p for p in exclusions if "*" not in p and "->" not in p}
    wildcard_patterns = {p for p in exclusions if "*" in p and "->" not in p}
    wildcard_regexes = [compile_wildcard_regex(p) for p in wildcard_patterns]

    for typo in typos:
        if typo == word:
            continue

        # Use full validation set to check if typo is a real word
        if typo in validation_set:
            continue

        # If user explicitly excludes a typo, it bypasses the frequency check.
        # This makes the user's exclusion the final authority.
        is_explicitly_excluded = False
        if typo in exact_exclusions:
            is_explicitly_excluded = True
        else:
            for pat in wildcard_regexes:
                if pat.match(typo):
                    is_explicitly_excluded = True
                    break

        if not is_explicitly_excluded and typo_freq_threshold > 0.0:
            typo_freq = word_frequency(typo, "en")
            if typo_freq >= typo_freq_threshold:
                continue

        # Use filtered validation set for boundary detection
        # This allows excluded patterns to not block valid typos
        boundary_type = determine_boundaries(
            typo, filtered_validation_set, source_words
        )
        if boundary_type is not None:
            corrections.append((typo, word, boundary_type))

    return corrections


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
) -> tuple[list[Correction], list, list]:
    """Resolve collisions where multiple words map to same typo."""
    final_corrections = []
    skipped_collisions = []
    skipped_short = []

    for typo, word_boundary_list in typo_map.items():
        unique_pairs = list(set(word_boundary_list))
        unique_words = list(set(w for w, _ in unique_pairs))

        if len(unique_words) == 1:
            word = unique_words[0]
            boundaries = [b for w, b in unique_pairs if w == word]
            boundary = choose_strictest_boundary(boundaries)

            if word in user_words and len(word) == 2:
                boundary = BoundaryType.BOTH

            # A short typo is permissible if it corrects to a word that is also short,
            # using the user's `min_word_length` as the threshold.
            if len(typo) < min_typo_length and len(word) > min_word_length:
                skipped_short.append((typo, word, len(typo)))
            else:
                correction = (typo, word, boundary)
                if not exclusion_matcher.should_exclude(correction):
                    final_corrections.append(correction)
        else:
            word_freqs = [(w, word_frequency(w, "en")) for w in unique_words]
            word_freqs.sort(key=lambda x: x[1], reverse=True)

            most_common = word_freqs[0]
            second_most = word_freqs[1] if len(word_freqs) > 1 else (None, 0)

            ratio = (
                most_common[1] / second_most[1] if second_most[1] > 0 else float("inf")
            )

            if ratio > freq_ratio:
                word = most_common[0]
                boundaries = [b for w, b in unique_pairs if w == word]
                boundary = choose_strictest_boundary(boundaries)

                if word in user_words and len(word) == 2:
                    boundary = BoundaryType.BOTH

                # A short typo is permissible if it corrects to a word that is also short,
                # using the user's `min_word_length` as the threshold.
                if len(typo) < min_typo_length and len(word) > min_word_length:
                    skipped_short.append((typo, word, len(typo)))
                else:
                    correction = (typo, word, boundary)
                    if not exclusion_matcher.should_exclude(correction):
                        final_corrections.append(correction)
            else:
                skipped_collisions.append((typo, unique_words, ratio))

    return final_corrections, skipped_collisions, skipped_short


def remove_substring_conflicts(corrections: list[Correction]) -> list[Correction]:
    """Remove corrections where one typo is a substring of another.
    
    If we have both 'teh' and 'tehir', we keep only 'teh' because the longer
    typo will never be triggered.
    """
    # Sort by length ascending so we process shorter typos first
    corrections.sort(key=lambda c: len(c[0]))

    final_corrections = []
    kept_typos = set()

    for typo, word, boundary in corrections:
        # Check if any already-kept typo is a substring of this one
        is_compound = any(kept_typo in typo for kept_typo in kept_typos if kept_typo != typo)
        
        if not is_compound:
            final_corrections.append((typo, word, boundary))
            kept_typos.add(typo)

    return final_corrections