"""Stage 6: Output generation."""

import sys
import time

from ..output import generate_espanso_yaml
from .data_models import ConflictRemovalResult, OutputGenerationResult


def generate_output(
    conflict_result: ConflictRemovalResult,
    output_dir: str,
    max_entries_per_file: int,
    jobs: int,
    verbose: bool = False,
) -> OutputGenerationResult:
    """Generate YAML output files.

    Args:
        conflict_result: Result from conflict removal stage
        output_dir: Output directory path
        max_entries_per_file: Maximum entries per YAML file
        jobs: Number of parallel jobs
        verbose: Whether to print verbose output

    Returns:
        OutputGenerationResult containing metrics
    """
    start_time = time.time()

    if verbose:
        print(
            f"# Writing {len(conflict_result.corrections)} corrections to YAML files",
            file=sys.stderr,
        )

    generate_espanso_yaml(
        conflict_result.corrections,
        output_dir,
        verbose,
        max_entries_per_file,
        jobs,
    )

    elapsed_time = time.time() - start_time

    return OutputGenerationResult(
        files_written=1,  # We don't track the exact count currently
        elapsed_time=elapsed_time,
    )
