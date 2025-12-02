"""Espanso YAML file writing utilities."""

import os
from multiprocessing import Pool

from loguru import logger

from entroppy.utils import expand_file_path
from entroppy.utils.helpers import ensure_directory_exists, write_file_safely
from entroppy.platforms.espanso.yaml_helpers import write_yaml_to_stream


def write_single_yaml_file(args: tuple) -> tuple[str, int]:
    """Worker function to write a single YAML file."""
    filename, chunk = args

    yaml_output = {"matches": chunk}

    def write_yaml_content(f):
        write_yaml_to_stream(yaml_output, f, f"writing file {filename}")

    write_file_safely(filename, write_yaml_content, "writing YAML file")

    return (os.path.basename(filename), len(chunk))


def write_yaml_files(
    corrections_by_letter: dict[str, list[dict]],
    output_dir: str,
    verbose: bool,
    max_entries_per_file: int = 500,
    jobs: int = 1,
) -> None:
    """Write YAML files in parallel, splitting large files into chunks."""
    output_dir = expand_file_path(output_dir) or output_dir
    ensure_directory_exists(output_dir)

    write_tasks = []

    for letter, matches in sorted(corrections_by_letter.items()):
        matches_sorted = sorted(matches, key=lambda m: m["replace"])

        for i in range(0, len(matches_sorted), max_entries_per_file):
            chunk = matches_sorted[i : i + max_entries_per_file]

            first_word = chunk[0]["replace"]
            last_word = chunk[-1]["replace"]

            if letter == "symbols":
                if len(matches_sorted) <= max_entries_per_file:
                    filename = os.path.join(output_dir, "typos_symbols.yml")
                else:
                    chunk_num = i // max_entries_per_file + 1
                    filename = os.path.join(output_dir, f"typos_symbols_{chunk_num:03d}.yml")
            else:
                if len(matches_sorted) <= max_entries_per_file:
                    filename = os.path.join(output_dir, f"typos_{letter}.yml")
                else:
                    filename = os.path.join(output_dir, f"typos_{first_word}_to_{last_word}.yml")

            write_tasks.append((filename, chunk))

    total_entries = 0
    total_files = 0

    if jobs > 1 and len(write_tasks) > 1:
        if verbose:
            logger.info(f"  Writing {len(write_tasks)} YAML files using {jobs} workers...")

        with Pool(processes=jobs) as pool:
            results = pool.map(write_single_yaml_file, write_tasks)

            for _, entry_count in results:
                total_entries += entry_count
                total_files += 1
    else:
        if verbose:
            logger.info(f"  Writing {len(write_tasks)} YAML files...")

        for filename, chunk in write_tasks:
            _, entry_count = write_single_yaml_file((filename, chunk))
            total_entries += entry_count
            total_files += 1

    if verbose:
        logger.info(f"  Wrote {total_entries} corrections across {total_files} files")
