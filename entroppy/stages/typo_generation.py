"""Stage 2: Typo generation with multiprocessing support."""

import sys
import time
from collections import defaultdict
from multiprocessing import Pool

from tqdm import tqdm

from ..config import Config, Correction
from ..processing import process_word
from .data_models import DictionaryData, TypoGenerationResult
from .worker_context import WorkerContext, init_worker, get_worker_context


def process_word_worker(word: str) -> tuple[str, list[Correction]]:
    """Worker function for multiprocessing.

    Args:
        word: The word to process

    Returns:
        Tuple of (word, list of corrections)
    """
    context = get_worker_context()
    return (
        word,
        process_word(
            word,
            context.validation_set,
            context.filtered_validation_set,
            context.source_words_set,
            context.typo_freq_threshold,
            context.adjacent_letters_map,
            context.exclusions_set,
        ),
    )


def generate_typos(
    dict_data: DictionaryData,
    config: Config,
    verbose: bool = False,
) -> TypoGenerationResult:
    """Generate typos for all source words.

    Args:
        dict_data: Dictionary data from loading stage
        config: Configuration object
        verbose: Whether to print verbose output

    Returns:
        TypoGenerationResult containing typo map
    """
    start_time = time.time()

    if verbose:
        print(
            f"\nGenerating typos for {len(dict_data.source_words)} words...\n",
            file=sys.stderr,
        )

    typo_map = defaultdict(list)

    if config.jobs > 1:
        # Multiprocessing mode
        if verbose:
            print(f"Processing using {config.jobs} workers...", file=sys.stderr)

        # Create worker context (immutable, serializable)
        context = WorkerContext.from_dict_data(dict_data, config.typo_freq_threshold)

        with Pool(
            processes=config.jobs,
            initializer=init_worker,
            initargs=(context,),
        ) as pool:
            results = pool.imap_unordered(process_word_worker, dict_data.source_words)

            # Wrap with progress bar
            if verbose:
                results = tqdm(
                    results,
                    total=len(dict_data.source_words),
                    desc="Processing words",
                    unit="word",
                )

            for word, corrections in results:
                for typo, correction_word, boundary_type in corrections:
                    typo_map[typo].append((correction_word, boundary_type))
    else:
        # Single-threaded mode
        words_iter = dict_data.source_words
        if verbose:
            words_iter = tqdm(
                dict_data.source_words, desc="Processing words", unit="word"
            )

        for word in words_iter:
            corrections = process_word(
                word,
                dict_data.validation_set,
                dict_data.filtered_validation_set,
                dict_data.source_words_set,
                config.typo_freq_threshold,
                dict_data.adjacent_letters_map,
                dict_data.exclusions,
            )
            for typo, correction_word, boundary_type in corrections:
                typo_map[typo].append((correction_word, boundary_type))

    elapsed_time = time.time() - start_time

    return TypoGenerationResult(
        typo_map=typo_map,
        elapsed_time=elapsed_time,
    )
