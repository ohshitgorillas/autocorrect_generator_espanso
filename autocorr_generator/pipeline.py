"""Main processing pipeline and multiprocessing support."""

import sys
import time
from collections import defaultdict
from multiprocessing import Pool

from tqdm import tqdm

from .config import BoundaryType, Config, Correction
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
from .reports import ReportData, generate_reports

# Global state for multiprocessing workers
_VALIDATION_SET = None
_FILTERED_VALIDATION_SET = None
_SOURCE_WORDS_SET = None
_TYPO_FREQ_THRESHOLD = 0.0
_ADJ_LETTERS_MAP = None
_EXCLUSIONS_SET: set[str] | None = None


# pylint: disable=global-statement, line-too-long


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
    start_time = time.time()
    verbose = config.verbose

    # Initialize report data if reports are enabled
    report_data = None
    if config.reports:
        report_data = ReportData(start_time=start_time)

    # Load dictionaries and mappings
    stage_start = time.time()
    validation_set = load_validation_dictionary(config.exclude, config.include, verbose)
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

    if report_data:
        report_data.stage_times["Loading dictionaries"] = time.time() - stage_start
        report_data.words_processed = len(source_words)

    if verbose:
        print(f"\nGenerating typos for {len(source_words)} words...\n", file=sys.stderr)

    source_words_set = set(source_words)

    # Start typo generation stage
    stage_start = time.time()

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
            results = pool.imap_unordered(process_word_worker, source_words)

            # Wrap with progress bar
            if verbose:
                results = tqdm(
                    results,
                    total=len(source_words),
                    desc="Processing words",
                    unit="word",
                )

            for word, corrections in results:
                for typo, correction_word, boundary_type in corrections:
                    typo_map[typo].append((correction_word, boundary_type))
    else:
        # Wrap with progress bar for single-threaded processing
        words_iter = source_words
        if verbose:
            words_iter = tqdm(source_words, desc="Processing words", unit="word")

        for word in words_iter:
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

    if report_data:
        report_data.stage_times["Generating typos"] = time.time() - stage_start

    # Resolve collisions
    stage_start = time.time()
    final_corrections, skipped_collisions, skipped_short, excluded_corrections = (
        resolve_collisions(
            typo_map,
            config.freq_ratio,
            config.min_typo_length,
            config.min_word_length,
            user_words_set,
            exclusion_matcher,
        )
    )

    if report_data:
        report_data.stage_times["Resolving collisions"] = time.time() - stage_start
        report_data.skipped_collisions = skipped_collisions
        report_data.skipped_short = skipped_short
        report_data.excluded_corrections = excluded_corrections
        report_data.corrections_before_generalization = len(final_corrections)

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
    (
        patterns,
        to_remove,
        pattern_replacements,
        rejected_patterns,
    ) = generalize_patterns(
        final_corrections,
        filtered_validation_set,
        set(source_words),
        config.min_typo_length,
        verbose,
    )

    # Remove original corrections that have been generalized
    pre_generalization_count = len(final_corrections)
    final_corrections = [c for c in final_corrections if c not in to_remove]
    removed_count = pre_generalization_count - len(final_corrections)

    if report_data:
        report_data.stage_times["Generalizing patterns"] = time.time() - stage_start

    # Patterns need collision resolution - multiple words might generate same pattern
    pattern_typo_map = defaultdict(list)
    for typo, word, boundary in patterns:
        pattern_typo_map[typo].append((word, boundary))

    # Resolve collisions for patterns
    resolved_patterns, _, _, _ = resolve_collisions(
        pattern_typo_map,
        config.freq_ratio,
        config.min_typo_length,
        config.min_word_length,
        user_words_set,
        exclusion_matcher,
    )

    # Remove substring conflicts from patterns
    # Patterns can also have redundancies (e.g., "lectiona" is redundant if "ectiona" exists)
    resolved_patterns = remove_substring_conflicts(resolved_patterns, verbose=False)

    # Add resolved patterns to final corrections
    final_corrections.extend(resolved_patterns)

    if report_data:
        report_data.corrections_after_generalization = len(final_corrections)
        # Store pattern info with count of replacements
        for typo, word, boundary in resolved_patterns:
            pattern_key = (typo, word, boundary)
            count = len(pattern_replacements.get(pattern_key, []))
            report_data.generalized_patterns.append((typo, word, boundary, count))
        report_data.pattern_replacements = pattern_replacements
        report_data.rejected_patterns = rejected_patterns

    if verbose:
        if patterns:
            print(
                f"# Generalized {len(resolved_patterns)} patterns, removing {removed_count} specific corrections.",
                file=sys.stderr,
            )
        print(
            f"# After pattern generalization: {len(final_corrections)} entries",
            file=sys.stderr,
        )

    # Remove substring conflicts
    stage_start = time.time()
    pre_conflict_count = len(final_corrections)

    # Track which corrections are removed by building a lookup
    if report_data:
        pre_conflict_corrections = {c: c for c in final_corrections}

    final_corrections = remove_substring_conflicts(final_corrections, verbose)

    if report_data:
        report_data.stage_times["Removing conflicts"] = time.time() - stage_start
        report_data.corrections_after_conflicts = len(final_corrections)
        # Find which corrections were removed
        final_set = set(final_corrections)
        for typo, word, boundary in pre_conflict_corrections.values():
            if (typo, word, boundary) not in final_set:
                # Find what blocked it and what it corrects to
                blocking_typo = "unknown"
                blocking_word = "unknown"
                for other_typo, other_word, other_boundary in final_corrections:
                    if other_boundary == boundary and typo != other_typo:
                        # For RIGHT boundaries (suffixes), check if typo ends with shorter typo
                        # For other boundaries, check if typo starts with shorter typo
                        if boundary == BoundaryType.RIGHT:
                            if typo.endswith(other_typo):
                                blocking_typo = other_typo
                                blocking_word = other_word
                                break
                        else:
                            if typo.startswith(other_typo):
                                blocking_typo = other_typo
                                blocking_word = other_word
                                break
                report_data.removed_conflicts.append(
                    (typo, word, blocking_typo, blocking_word, boundary)
                )

    if verbose:
        conflicts_removed = pre_conflict_count - len(final_corrections)
        if conflicts_removed > 0:
            print(
                f"# Removed {conflicts_removed} typos due to substring conflicts",
                file=sys.stderr,
            )

    # Generate output
    stage_start = time.time()
    generate_espanso_yaml(
        final_corrections, config.output, verbose, config.max_entries_per_file
    )

    if report_data:
        if verbose:
            print(f"# Writing {len(final_corrections)} corrections to YAML files", file=sys.stderr)
        report_data.stage_times["Writing YAML files"] = time.time() - stage_start
        report_data.total_corrections = len(final_corrections)

    # Generate reports if enabled
    if config.reports:
        if verbose:
            print(f"# Generating reports in {config.reports}", file=sys.stderr)
        generate_reports(report_data, config.reports, verbose)

    # Print total time
    elapsed_time = time.time() - start_time
    if verbose:
        minutes, seconds = divmod(elapsed_time, 60)
        if minutes > 0:
            print(
                f"\n✓ Total processing time: {int(minutes)}m {seconds:.1f}s",
                file=sys.stderr,
            )
        else:
            print(f"\n✓ Total processing time: {seconds:.1f}s", file=sys.stderr)
