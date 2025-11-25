"""Main processing pipeline and multiprocessing support."""

import sys
from collections import defaultdict
from multiprocessing import Pool

from .config import Config, Correction
from .dictionary import (
    load_adjacent_letters,
    load_exclusions,
    load_source_words,
    load_validation_dictionary,
    load_word_list,
)
from .exclusions import ExclusionMatcher
from .output import generate_espanso_yaml
from .patterns import generalize_patterns
from .processing import (
    process_word,
    remove_substring_conflicts,
    resolve_collisions,
)

# Global state for multiprocessing workers
_VALIDATION_SET = None
_FILTERED_VALIDATION_SET = None
_SOURCE_WORDS_SET = None
_TYPO_FREQ_THRESHOLD = 0.0
_ADJ_LETTERS_MAP = None
_EXCLUSIONS_SET: set[str] | None = None


def init_worker(
    validation_set,
    filtered_validation_set,
    source_words_set,
    typo_freq_threshold,
    adj_letters_map,
    exclusions_set,
):
    """Initialize worker process."""
    global _VALIDATION_SET, _FILTERED_VALIDATION_SET, _SOURCE_WORDS_SET, _TYPO_FREQ_THRESHOLD, _ADJ_LETTERS_MAP, _EXCLUSIONS_SET
    _VALIDATION_SET = validation_set
    _FILTERED_VALIDATION_SET = filtered_validation_set
    _SOURCE_WORDS_SET = source_words_set
    _TYPO_FREQ_THRESHOLD = typo_freq_threshold
    _ADJ_LETTERS_MAP = adj_letters_map
    _EXCLUSIONS_SET = exclusions_set


def process_word_worker(word: str) -> tuple[str, list[Correction]]:
    """Worker function for multiprocessing."""
    return (
        word,
        process_word(
            word,
            _VALIDATION_SET,
            _FILTERED_VALIDATION_SET,
            _SOURCE_WORDS_SET,
            _TYPO_FREQ_THRESHOLD,
            _ADJ_LETTERS_MAP,
            _EXCLUSIONS_SET,
        ),
    )


def run_pipeline(config: Config) -> None:
    """Main processing pipeline."""
    verbose = config.verbose

    # Load dictionaries and mappings
    validation_set = load_validation_dictionary(
        config.exclude, config.include, verbose
    )
    exclusions = load_exclusions(config.exclude, verbose)
    exclusion_matcher = ExclusionMatcher(exclusions)

    # Filter validation set for boundary detection
    # This removes words matching exclusion patterns so they don't block valid typos
    filtered_validation_set = exclusion_matcher.filter_validation_set(validation_set)

    if verbose and len(filtered_validation_set) != len(validation_set):
        removed = len(validation_set) - len(filtered_validation_set)
        print(
            f"Filtered {removed} words from validation set using exclusion patterns",
            file=sys.stderr,
        )

    adjacent_letters_map = load_adjacent_letters(config.adjacent_letters, verbose)

    # Load source words
    user_words = load_word_list(config.include, verbose)
    if verbose and user_words:
        print(f"Loaded {len(user_words)} words from include file", file=sys.stderr)

    user_words_set = set(user_words)
    source_words = load_source_words(config, verbose)
    source_words.extend(user_words)

    if verbose and user_words:
        print(
            f"Included {len(user_words)} user words (bypassed filters)",
            file=sys.stderr,
        )

    if verbose:
        print(f"\nProcessing {len(source_words)} words...\n", file=sys.stderr)

    source_words_set = set(source_words)

    # Process words to generate typos
    typo_map = defaultdict(list)

    if config.jobs > 1:
        if verbose:
            print(f"Processing using {config.jobs} workers...", file=sys.stderr)

        with Pool(
            processes=config.jobs,
            initializer=init_worker,
            initargs=(
                validation_set,
                filtered_validation_set,  # Use filtered set for boundary detection
                source_words_set,
                config.typo_freq_threshold,
                adjacent_letters_map,
                exclusions,
            ),
        ) as pool:
            results = pool.map(process_word_worker, source_words)

        for word, corrections in results:
            for typo, correction_word, boundary_type in corrections:
                typo_map[typo].append((correction_word, boundary_type))
    else:
        for word in source_words:
            corrections = process_word(
                word,
                validation_set,
                filtered_validation_set,  # Use filtered set for boundary detection
                source_words_set,
                config.typo_freq_threshold,
                adjacent_letters_map,
                exclusions,
            )
            for typo, correction_word, boundary_type in corrections:
                typo_map[typo].append((correction_word, boundary_type))

    # Resolve collisions
    final_corrections, skipped_collisions, skipped_short = resolve_collisions(
        typo_map,
        config.freq_ratio,
        config.min_typo_length,
        config.min_word_length,
        user_words_set,
        exclusion_matcher,
    )

    # Statistics
    if verbose:
        print(
            f"# Generated {len(final_corrections)} corrections (before pattern generalization)",
            file=sys.stderr,
        )
        if skipped_short:
            print(
                f"# Skipped {len(skipped_short)} typos shorter than {config.min_typo_length} characters",
                file=sys.stderr,
            )
        if skipped_collisions:
            print(
                f"# Skipped {len(skipped_collisions)} ambiguous collisions:",
                file=sys.stderr,
            )
            for typo, words, ratio in skipped_collisions[:5]:
                print(f"#   {typo}: {words} (ratio: {ratio:.2f})", file=sys.stderr)

    # Generalize patterns
    patterns, to_remove = generalize_patterns(
        final_corrections, validation_set, config.min_typo_length
    )

    # Remove original corrections that have been generalized
    pre_generalization_count = len(final_corrections)
    final_corrections = [c for c in final_corrections if c not in to_remove]
    removed_count = pre_generalization_count - len(final_corrections)

    # Add the new generalized patterns
    final_corrections.extend(patterns)

    if verbose:
        if patterns:
            print(
                f"# Generalized {len(patterns)} patterns, removing {removed_count} specific corrections.",
                file=sys.stderr,
            )
        print(
            f"# After pattern generalization: {len(final_corrections)} entries",
            file=sys.stderr,
        )

    # Remove substring conflicts
    pre_conflict_count = len(final_corrections)
    final_corrections = remove_substring_conflicts(final_corrections)

    if verbose:
        conflicts_removed = pre_conflict_count - len(final_corrections)
        if conflicts_removed > 0:
            print(
                f"# Removed {conflicts_removed} typos due to substring conflicts",
                file=sys.stderr,
            )

    # Generate output
    generate_espanso_yaml(final_corrections, config.output, verbose, config.max_entries_per_file)
