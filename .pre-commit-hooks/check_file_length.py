#!/usr/bin/env python3
"""Pre-commit hook to check that Python files don't exceed 500 lines."""

from pathlib import Path
import sys


def check_file_length(file_path: str, max_lines: int = 500) -> bool:
    """Check if a file exceeds the maximum line count.

    Args:
        file_path: Path to the file to check
        max_lines: Maximum allowed lines (default: 500)

    Returns:
        True if file is within limit, False otherwise
    """
    path = Path(file_path)
    if not path.exists():
        return True

    try:
        with open(path, "r", encoding="utf-8") as f:
            line_count = sum(1 for _ in f)

        if line_count > max_lines:
            print(
                f"ERROR: {file_path} has {line_count} lines, "
                f"exceeds maximum of {max_lines} lines"
            )
            return False
        return True
    except (OSError, IOError) as e:
        print(f"ERROR: Failed to check {file_path}: {e}")
        return False


def main():
    """Main entry point for the pre-commit hook."""
    max_lines = 500
    failed = False

    # Exclude test files from length check (they often need to be longer)
    for file_path in sys.argv[1:]:
        # Skip test files
        if "tests/" in file_path or file_path.startswith("test_"):
            continue
        if not check_file_length(file_path, max_lines):
            failed = True

    if failed:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
