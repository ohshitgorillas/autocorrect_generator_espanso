"""Stage 2: Typo generation with multiprocessing support."""

import time
from collections import defaultdict
from multiprocessing import Pool

from loguru import logger
from tqdm import tqdm

from entroppy.core import Config, Correction
from entroppy.resolution import process_word
from entroppy.processing.stages.data_models import DictionaryData, TypoGenerationResult
from entroppy.processing.stages.worker_context import WorkerContext, init_worker, get_worker_context


def process_word_worker(word: str) -> tuple[str, list[Correction], list[str]]:
    """Worker function for multiprocessing.

    Args:
        word: The word to process

    Returns:
        Tuple of (word, list of corrections, list of debug messages)
    """
    context = get_worker_context()
    corrections, debug_messages = process_word(
        word,
        context.validation_set,
        context.filtered_validation_set,
        context.source_words_set,
        context.typo_freq_threshold,
        context.adjacent_letters_map,
        context.exclusions_set,
        context.debug_words,
        context.debug_typo_matcher,
    )
    return (word, corrections, debug_messages)


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
        logger.info(f"\nGenerating typos for {len(dict_data.source_words)} words...\n")

    typo_map = defaultdict(list)
    all_debug_messages = []

    if config.jobs > 1:
        # Multiprocessing mode
        if verbose:
            logger.info(f"Processing using {config.jobs} workers...")

        # Create worker context (immutable, serializable)
        context = WorkerContext.from_dict_data(dict_data, config)

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

            for word, corrections, debug_messages in results:
                for typo, correction_word, boundary_type in corrections:
                    typo_map[typo].append((correction_word, boundary_type))
                # Collect debug messages from workers
                all_debug_messages.extend(debug_messages)

        # Print all collected debug messages after workers complete
        for message in all_debug_messages:
            logger.debug(message)
    else:
        # Single-threaded mode
        words_iter = dict_data.source_words
        if verbose:
            words_iter = tqdm(dict_data.source_words, desc="Processing words", unit="word")

        for word in words_iter:
            corrections, debug_messages = process_word(
                word,
                dict_data.validation_set,
                dict_data.filtered_validation_set,
                dict_data.source_words_set,
                config.typo_freq_threshold,
                dict_data.adjacent_letters_map,
                dict_data.exclusions,
                frozenset(config.debug_words),
                config.debug_typo_matcher,
            )
            for typo, correction_word, boundary_type in corrections:
                typo_map[typo].append((correction_word, boundary_type))
            # In single-threaded mode, log immediately
            for message in debug_messages:
                logger.debug(message)

    elapsed_time = time.time() - start_time

    return TypoGenerationResult(
        typo_map=typo_map,
        elapsed_time=elapsed_time,
    )
