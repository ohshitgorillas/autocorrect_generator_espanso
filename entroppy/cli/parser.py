"""Command-line interface for the EntropPy project."""

import argparse
from multiprocessing import cpu_count


def create_parser() -> argparse.ArgumentParser:
    """Create and configure argument parser."""
    parser = argparse.ArgumentParser(
        description="Generate autocorrect dictionary from common typos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Espanso - generates multiple YAML files in specified directory
  %(prog)s --platform espanso --top-n 1000 -o corrections -v
  
  # QMK - generates single text file
  %(prog)s --platform qmk --top-n 1000 -o corrections/autocorrect.txt -v
  
  # With the top 5000 most common English words and custom words
  %(prog)s --platform espanso --top-n 5000 --include settings/include.txt -o corrections/autocorrect.txt

  # With custom words only, do not use dictionary
  %(prog)s --platform qmk --include settings/include.txt -o corrections/autocorrect.txt --max-corrections 800
  
  # Using JSON config
  %(prog)s --config config.json

Output files are organized based on platform:
- Espanso: Multiple YAML files in output directory
  - If corrections exceed max_entries_per_file: typos_<first_word>_to_<last_word>.yml
  - Otherwise: typos_<letter>.yml or typos_symbols.yml
- QMK: Single text file at output path
  - Format: typo -> correction (one per line)

Example config.json:
{
  "platform": "qmk",
  "top_n": 1000,
  "max_corrections": 800,
  "max_word_length": 10,
  "min_word_length": 3,
  "min_typo_length": 5,
  "freq_ratio": 10.0,
  "typo_freq_threshold": 1e-8,
  "output": "corrections/autocorrect.txt",
  "reports": "./reports",
  "verbose": true,
  "debug": false,
  "jobs": 4
}
        """,
    )

    # Configuration
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        help="JSON configuration file (CLI args override JSON values)",
    )

    # Platform selection
    parser.add_argument(
        "--platform",
        type=str,
        choices=["espanso", "qmk"],
        default="espanso",
        help="Target platform (espanso: YAML files, qmk: text file)",
    )

    # Output
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        help="Output path (directory for Espanso, file for QMK)",
    )
    parser.add_argument(
        "--reports",
        type=str,
        help="Directory to generate detailed reports (creates timestamped subdirectories)",
    )

    # Word lists
    parser.add_argument("--top-n", type=int, help="Pull top N most common English words")
    parser.add_argument("--include", type=str, help="File with additional words to include")
    parser.add_argument("--exclude", type=str, help="File with exclusion patterns")
    parser.add_argument(
        "--adjacent-letters", type=str, help="File mapping keys to adjacent letters"
    )

    # Parameters
    parser.add_argument(
        "--max-corrections",
        type=int,
        help="Maximum number of corrections (QMK only, typically 1000-6000)",
        default=None,
    )
    parser.add_argument(
        "--freq-ratio",
        type=float,
        help="Minimum frequency ratio for collision resolution",
        default=10.0,
    )
    parser.add_argument(
        "--max-word-length", type=int, help="Maximum word length to process", default=10
    )
    parser.add_argument("--min-word-length", type=int, help="Minimum source word length", default=3)
    parser.add_argument(
        "--min-typo-length",
        type=int,
        help="Minimum typo length to include in output",
        default=4,
    )
    parser.add_argument(
        "--max-entries-per-file",
        type=int,
        help="Maximum corrections per YAML file (Espanso only)",
        default=500,
    )
    parser.add_argument(
        "--typo-freq-threshold",
        type=float,
        help="Skip typos with wordfreq frequency above this",
        default=0.0,
    )

    # Flags
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        help=f"Number of parallel workers (default: {cpu_count()})",
    )

    # Debug tracing
    parser.add_argument(
        "--debug-words",
        type=str,
        help="Comma-separated list of words to trace through "
        "pipeline (requires --debug and --verbose). "
        "Exact matches only (case-insensitive).",
    )
    parser.add_argument(
        "--debug-typos",
        type=str,
        help="Comma-separated list of typo patterns to trace "
        "(supports wildcards * and boundaries :, requires --debug and --verbose). "
        "Exact matches only (case-insensitive).",
    )

    return parser
