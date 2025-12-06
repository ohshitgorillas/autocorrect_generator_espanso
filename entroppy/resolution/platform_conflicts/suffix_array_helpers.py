"""Helper functions for suffix array-based substring conflict detection."""

from typing import TYPE_CHECKING

from pysuffixarray.core import SuffixArray
from tqdm import tqdm

if TYPE_CHECKING:
    pass


def build_suffix_array(
    formatted_typos: list[str], verbose: bool, pass_name: str
) -> tuple[SuffixArray, str]:
    """Build suffix array from formatted typos.

    Args:
        formatted_typos: List of formatted typo strings
        verbose: Whether to show progress
        pass_name: Name of the pass (for progress bar)

    Returns:
        Tuple of (suffix_array, delimiter)
    """
    if verbose:
        build_bar: tqdm = tqdm(
            total=1,
            desc=f"    {pass_name} (building suffix array)",
            unit="step",
            leave=False,
        )
        build_bar.update(0)

    # Concatenate all typos with a unique delimiter (null character)
    delimiter = "\x00"  # Null character as delimiter (unlikely to appear in typos)
    concatenated_string = delimiter.join(formatted_typos)

    # Build suffix array on concatenated string
    sa = SuffixArray(concatenated_string)

    if verbose:
        build_bar.update(1)
        build_bar.close()

    return sa, delimiter


def find_substring_matches(
    sa: SuffixArray,
    formatted_typo: str,
    formatted_typos: list[str],
    delimiter: str,
) -> set[int]:
    """Find which typos contain the given typo as a substring using suffix array.

    Args:
        sa: Suffix array built from concatenated typos
        formatted_typo: The typo to search for
        formatted_typos: List of all formatted typos
        delimiter: Delimiter used in concatenated string

    Returns:
        Set of indices of typos that contain formatted_typo as substring
    """
    # Use suffix array match() to find all occurrences of this typo
    match_positions = sa.match(formatted_typo)

    # Map match positions back to typo indices
    matched_typo_indices: set[int] = set()
    for pos in match_positions:
        # Find which typo this position belongs to by tracking cumulative lengths
        cumulative_pos = 0
        for j, other_typo in enumerate(formatted_typos):
            typo_length = len(other_typo)
            if cumulative_pos <= pos < cumulative_pos + typo_length:
                matched_typo_indices.add(j)
                break
            cumulative_pos += typo_length + len(delimiter)

    return matched_typo_indices
