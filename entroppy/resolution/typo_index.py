"""Typo substring index building for collision resolution."""

from multiprocessing import Pool

from loguru import logger
from tqdm import tqdm


def _process_typo_chunk_for_index(
    chunk_data: tuple[list[str], list[str]],
) -> dict[str, dict[str, bool]]:
    """Worker function to process a chunk of typos for substring index building.

    Args:
        chunk_data: Tuple of (chunk_typos, all_typos_list)
            - chunk_typos: List of typos to process in this chunk
            - all_typos_list: Full list of all typos (for checking against)

    Returns:
        Dictionary mapping each typo in chunk to its substring relationship flags
    """
    chunk_typos, all_typos_list = chunk_data
    chunk_index: dict[str, dict[str, bool]] = {}

    for typo in chunk_typos:
        chunk_index[typo] = {
            "appears_as_prefix": False,
            "appears_as_suffix": False,
            "appears_in_middle": False,
        }

        for other_typo in all_typos_list:
            if other_typo == typo:
                continue
            if typo in other_typo:
                if other_typo.startswith(typo):
                    chunk_index[typo]["appears_as_prefix"] = True
                elif other_typo.endswith(typo):
                    chunk_index[typo]["appears_as_suffix"] = True
                else:
                    chunk_index[typo]["appears_in_middle"] = True

    return chunk_index


def build_typo_substring_index(
    all_typos: set[str], verbose: bool = False, jobs: int = 1
) -> dict[str, dict[str, bool]]:
    """Build an index of substring relationships between typos.

    Pre-computes for each typo whether it appears as a prefix, suffix, or middle
    substring in other typos. This eliminates O(n²) repeated substring checks.

    Args:
        all_typos: Set of all typos to index
        verbose: Whether to show progress bar
        jobs: Number of parallel workers to use (1 = sequential)

    Returns:
        Dictionary mapping each typo to a dict with keys:
        - "appears_as_prefix": True if typo appears as prefix in any other typo
        - "appears_as_suffix": True if typo appears as suffix in any other typo
        - "appears_in_middle": True if typo appears in middle of any other typo
    """
    typos_list = list(all_typos)

    # Initialize all typos with False values
    index: dict[str, dict[str, bool]] = {}
    for typo in all_typos:
        index[typo] = {
            "appears_as_prefix": False,
            "appears_as_suffix": False,
            "appears_in_middle": False,
        }

    if jobs > 1 and len(typos_list) > 100:
        # Parallel processing mode - split typos into chunks
        if verbose:
            logger.info(
                f"  Splitting {len(typos_list):,} typos into chunks for parallel processing..."
            )

        chunk_size = max(
            1, len(typos_list) // (jobs * 4)
        )  # 4 chunks per worker for better load balancing
        chunks = [typos_list[i : i + chunk_size] for i in range(0, len(typos_list), chunk_size)]

        if verbose:
            logger.info(f"  Created {len(chunks)} chunks (using {jobs} workers)...")

        # Prepare chunk data: each chunk gets the full typos_list for checking
        chunk_data_list = [(chunk, typos_list) for chunk in chunks]

        if verbose:
            logger.info("  Starting parallel processing...")

        with Pool(processes=jobs) as pool:
            # Use imap_unordered for better performance
            results = pool.imap_unordered(_process_typo_chunk_for_index, chunk_data_list)

            # Wrap with progress bar if verbose - track by typos, not chunks
            if verbose:
                pbar = tqdm(
                    total=len(typos_list),
                    desc="  Building substring index",
                    unit="typo",
                    leave=False,
                    miniters=max(1, len(typos_list) // 1000),  # Update every 0.1% or so
                    mininterval=0.5,  # Update at least every 0.5 seconds
                )

                # Merge results from all chunks - consume results to update progress bar
                for chunk_index in results:
                    # Update progress by number of typos in this chunk
                    typos_processed = len(chunk_index)
                    index.update(chunk_index)
                    pbar.update(typos_processed)

                pbar.close()
            else:
                # Merge results from all chunks without progress bar
                for chunk_index in results:
                    index.update(chunk_index)
    else:
        # Single-threaded mode
        typos_iter = typos_list
        if verbose:
            typos_iter = tqdm(
                typos_list, desc="  Building substring index", unit="typo", leave=False
            )

        for typo in typos_iter:
            for other_typo in typos_list:
                if other_typo == typo:
                    continue
                if typo in other_typo:
                    if other_typo.startswith(typo):
                        index[typo]["appears_as_prefix"] = True
                    elif other_typo.endswith(typo):
                        index[typo]["appears_as_suffix"] = True
                    else:
                        index[typo]["appears_in_middle"] = True

    return index
