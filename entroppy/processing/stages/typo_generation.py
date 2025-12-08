"""Stage 2: Typo generation with multiprocessing support."""

from collections import defaultdict
from multiprocessing import Pool
import time
from typing import TYPE_CHECKING, Any

from loguru import logger
from tqdm import tqdm

from entroppy.core import Config
from entroppy.core.boundaries import BoundaryType
from entroppy.core.patterns.data_collection import create_typo_generated_event
from entroppy.core.patterns.data_models import (
    TypoAcceptedEvent,
    TypoGeneratedEvent,
    WordProcessingEvent,
)
from entroppy.processing.stages.data_models import DictionaryData, TypoGenerationResult
from entroppy.processing.stages.worker_context import WorkerContext, get_worker_context, init_worker
from entroppy.resolution import process_word
from entroppy.utils.debug import DebugTypoMatcher

if TYPE_CHECKING:
    from entroppy.resolution.state import DictionaryState


def _merge_stage2_events_into_state(
    state: "DictionaryState", all_stage2_events: list[dict]
) -> None:
    """Merge Stage 2 events from workers into state.

    Args:
        state: Dictionary state to merge events into
        all_stage2_events: List of event dictionaries from workers
    """
    for event_dict in all_stage2_events:
        event_type = event_dict.get("event_type")
        if event_type == "processing_start":
            event = WordProcessingEvent(**event_dict)
        elif event_type == "typo_generated":
            event = TypoGeneratedEvent(**event_dict)
        elif event_type == "typo_accepted":
            event = TypoAcceptedEvent(**event_dict)
        else:
            continue
        state.stage2_word_events.append(event)


def _collect_typo_events_for_word(
    word: str,
    corrections: list[tuple[str, str]],
    debug_typo_matcher: "DebugTypoMatcher | None",
    stage2_events: list,
) -> None:
    """Collect typo events for a debug word.

    Args:
        word: The word being processed
        corrections: List of (typo, correction_word) pairs
        debug_typo_matcher: Optional matcher for debug typo patterns
        stage2_events: List to append events to
    """
    for typo, _correction_word in corrections:
        # Check if typo matches debug patterns
        matched_patterns: list[str] | None = None
        if debug_typo_matcher:
            matched = debug_typo_matcher.get_matching_patterns(typo, BoundaryType.NONE)
            if matched:
                matched_patterns = list(matched)

        stage2_events.append(create_typo_generated_event(word, typo, matched_patterns).model_dump())
        stage2_events.append(
            TypoAcceptedEvent(
                word=word,
                event_type="typo_accepted",
                typo=typo,
                boundary=BoundaryType.NONE.value,
                iteration=0,
            ).model_dump()
        )


def _setup_worker_context() -> tuple[dict[str, str] | None, "DebugTypoMatcher | None"]:
    """Set up worker context for processing.

    Returns:
        Tuple of (adj_map, debug_typo_matcher)
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

    return adj_map, debug_typo_matcher


def _is_debug_word(word: str) -> bool:
    """Check if word is being debugged.

    Args:
        word: Word to check

    Returns:
        True if word is being debugged
    """
    context = get_worker_context()
    return word.lower() in {w.lower() for w in context.debug_words}


def process_word_worker(word: str) -> tuple[str, list[tuple[str, str]], list[str], list]:
    """Worker function for multiprocessing.

    Args:
        word: The word to process

    Returns:
        Tuple of (word, list of (typo, word) pairs, list of debug messages, list of Stage 2 events)
        Note: Boundaries are determined later in Stage 3 (collision resolution)
    """
    context = get_worker_context()
    adj_map, debug_typo_matcher = _setup_worker_context()

    # Collect Stage 2 events in worker (state not available in multiprocessing)
    stage2_events: list = []

    # Track if word is being debugged
    is_debug_word = _is_debug_word(word)

    if is_debug_word:
        stage2_events.append(
            WordProcessingEvent(
                word=word,
                event_type="processing_start",
                iteration=0,
            ).model_dump()
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
        state=None,  # State not available in multiprocessing workers
    )

    # Collect events for generated/accepted typos
    if is_debug_word:
        _collect_typo_events_for_word(word, corrections, debug_typo_matcher, stage2_events)

    return (word, corrections, debug_messages, stage2_events)


def _process_multiprocessing(
    dict_data: DictionaryData,
    config: Config,
    verbose: bool,
    state: "DictionaryState | None" = None,
) -> tuple[defaultdict[str, list[str]], list[str]]:
    """Process words using multiprocessing.

    Args:
        dict_data: Dictionary data
        config: Configuration object
        verbose: Whether to show verbose output
        state: Optional dictionary state for storing structured debug data

    Returns:
        Tuple of (typo_map, debug_messages)
    """
    if verbose:
        logger.info(f"  Using {config.jobs} parallel workers")
        logger.info("  Initializing workers and building indexes...")

    # Create worker context (immutable, serializable)
    context = WorkerContext.from_dict_data(dict_data, config)

    typo_map = defaultdict(list)
    all_debug_messages = []
    all_stage2_events: list[dict] = []

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

        for _word, corrections, debug_messages, stage2_events in results_wrapped_iter:
            for typo, correction_word in corrections:
                typo_map[typo].append(correction_word)
            # Collect debug messages from workers
            all_debug_messages.extend(debug_messages)
            # Collect Stage 2 events from workers
            all_stage2_events.extend(stage2_events)

    # Print all collected debug messages after workers complete
    for message in all_debug_messages:
        logger.debug(message)

    # Merge Stage 2 events into state if available
    if state:
        _merge_stage2_events_into_state(state, all_stage2_events)

    return typo_map, all_debug_messages


def _process_single_threaded(
    dict_data: DictionaryData,
    config: Config,
    verbose: bool,
    state: "DictionaryState | None" = None,
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
            state,
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
    state: "DictionaryState | None" = None,
) -> TypoGenerationResult:
    """Generate typos for all source words.

    Args:
        dict_data: Dictionary data from loading stage
        config: Configuration object
        verbose: Whether to print verbose output
        state: Optional dictionary state for storing structured debug data

    Returns:
        TypoGenerationResult containing typo map
    """
    start_time = time.time()

    if verbose:
        logger.info(f"  Processing {len(dict_data.source_words)} words...")

    if config.jobs > 1:
        typo_map, debug_messages = _process_multiprocessing(dict_data, config, verbose, state)
    else:
        typo_map, debug_messages = _process_single_threaded(dict_data, config, verbose, state)

    elapsed_time = time.time() - start_time

    return TypoGenerationResult(
        typo_map=typo_map,
        elapsed_time=elapsed_time,
        debug_messages=debug_messages,
    )
