"""Stage 2: Typo generation with multiprocessing support."""

from collections import defaultdict
from multiprocessing import Pool
import time
from typing import Any

from loguru import logger
from tqdm import tqdm

from entroppy.core import Config
from entroppy.processing.stages.data_models import DictionaryData, TypoGenerationResult
from entroppy.processing.stages.worker_context import WorkerContext, get_worker_context, init_worker
from entroppy.resolution import process_word
from entroppy.utils.debug import DebugTypoMatcher


def process_word_worker(word: str) -> tuple[str, list[tuple[str, str]], list[str]]:
    """Worker function for multiprocessing.

    Args:
        word: The word to process

    Returns:
        Tuple of (word, list of (typo, word) pairs, list of debug messages)
        Note: Boundaries are determined later in Stage 3 (collision resolution)
    """
    context = get_worker_context()
    # Convert dict[str, list[str]] to dict[str, str] for process_word
    # Join all adjacent letters back into a string
    adj_map: dict[str, str] | None = None
    if context.adjacent_letters_map:
        adj_map = {k: "".join(v) if v else k for k, v in context.adjacent_letters_map.items() if v}

    # Recreate DebugTypoMatcher in worker from patterns (not serializable due to compiled regex)
    debug_typo_matcher: DebugTypoMatcher | None = (
        DebugTypoMatcher.from_patterns(set(context.debug_typo_patterns))
        if context.debug_typo_patterns
        else None
    )

    corrections, debug_messages = process_word(
        word,
        set(context.validation_set),
        set(context.source_words_set),
        context.typo_freq_threshold,
        adj_map,
        set(context.exclusions_set),
        frozenset(context.debug_words),
        debug_typo_matcher,
    )
    return (word, corrections, debug_messages)


def _process_multiprocessing(
    dict_data: DictionaryData,
    config: Config,
    verbose: bool,
) -> tuple[defaultdict[str, list[str]], list[str]]:
    """Process words using multiprocessing."""
    if verbose:
        logger.info(f"  Using {config.jobs} parallel workers")
        logger.info("  Initializing workers and building indexes...")

    # Create worker context (immutable, serializable)
    context = WorkerContext.from_dict_data(dict_data, config)

    typo_map = defaultdict(list)
    all_debug_messages = []

    with Pool(
        processes=config.jobs,
        initializer=init_worker,
        initargs=(context,),
    ) as pool:
        results = pool.imap_unordered(process_word_worker, dict_data.source_words)

        # Wrap with progress bar
        if verbose:
            results_wrapped_iter: Any = tqdm(
                results,
                total=len(dict_data.source_words),
                desc="Processing words",
                unit="word",
            )
        else:
            results_wrapped_iter = results

        for word, corrections, debug_messages in results_wrapped_iter:
            for typo, correction_word in corrections:
                typo_map[typo].append(correction_word)
            # Collect debug messages from workers
            all_debug_messages.extend(debug_messages)

    # Print all collected debug messages after workers complete
    for message in all_debug_messages:
        logger.debug(message)

    return typo_map, all_debug_messages


def _process_single_threaded(
    dict_data: DictionaryData,
    config: Config,
    verbose: bool,
) -> tuple[defaultdict[str, list[str]], list[str]]:
    """Process words using single-threaded mode."""
    typo_map = defaultdict(list)
    all_debug_messages: list[str] = []

    if verbose:
        words_iter: list[str] = list(
            tqdm(dict_data.source_words, desc="Processing words", unit="word")
        )
    else:
        words_iter = dict_data.source_words

    for word in words_iter:
        # Convert dict[str, str] to dict[str, str] | None (already correct type)
        adj_map = dict_data.adjacent_letters_map if dict_data.adjacent_letters_map else None
        corrections, debug_messages = process_word(
            word,
            dict_data.validation_set,
            dict_data.source_words_set,
            config.typo_freq_threshold,
            adj_map,
            dict_data.exclusions,
            frozenset(config.debug_words),
            config.debug_typo_matcher,
        )
        for typo, correction_word in corrections:
            typo_map[typo].append(correction_word)
        # Collect debug messages (still log them, but also store for reports)
        all_debug_messages.extend(debug_messages)
        # In single-threaded mode, log immediately
        for message in debug_messages:
            logger.debug(message)

    return typo_map, all_debug_messages


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
        logger.info(f"  Processing {len(dict_data.source_words)} words...")

    if config.jobs > 1:
        typo_map, debug_messages = _process_multiprocessing(dict_data, config, verbose)
    else:
        typo_map, debug_messages = _process_single_threaded(dict_data, config, verbose)

    elapsed_time = time.time() - start_time

    return TypoGenerationResult(
        typo_map=typo_map,
        elapsed_time=elapsed_time,
        debug_messages=debug_messages,
    )
