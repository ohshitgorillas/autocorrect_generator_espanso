"""Helper functions for suffix array-based substring conflict detection.

Uses Rust implementation for ~100x performance improvement.
"""

from tqdm import tqdm

from entroppy.utils.suffix_array import SubstringIndex


def build_suffix_array(formatted_typos: list[str], verbose: bool, pass_name: str) -> SubstringIndex:
    """Build suffix array from formatted typos.

    Uses Rust implementation for ~100x performance improvement.

    Args:
        formatted_typos: List of formatted typo strings
        verbose: Whether to show progress
        pass_name: Name of the pass (for progress bar)

    Returns:
        SubstringIndex instance
    """
    if verbose:
        build_bar: tqdm = tqdm(
            total=1,
            desc=f"    {pass_name} (building suffix array)",
            unit="step",
            leave=False,
        )
        build_bar.update(0)

    sa = SubstringIndex(formatted_typos)

    if verbose:
        build_bar.update(1)
        build_bar.close()

    return sa


def find_substring_matches(
    sa: SubstringIndex,
    formatted_typo: str,
) -> set[int]:
    """Find which typos contain the given typo as a substring using suffix array.

    Uses Rust implementation for ~100x performance improvement.

    Args:
        sa: SubstringIndex instance (wraps Rust implementation)
        formatted_typo: The typo to search for

    Returns:
        Set of indices of typos that contain formatted_typo as substring
    """
    # Use Rust implementation - O(log N + M) query, no linear scan
    matched_indices = sa.find_conflicts(formatted_typo)
    return set(matched_indices)
