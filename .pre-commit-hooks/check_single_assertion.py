#!/usr/bin/env python3
"""Pre-commit hook to check that each test function has only one assertion."""

import ast
from pathlib import Path
import sys


def count_assertions(node: ast.AST) -> int:
    """Count the number of assert statements in an AST node subtree.

    Args:
        node: The AST node to search (should be a function definition)

    Returns:
        The number of assert statements found within this node's subtree
    """
    count = 0
    # Walk only the subtree of this node, not the entire tree
    for child in ast.walk(node):
        if isinstance(child, ast.Assert):
            count += 1
    return count


def is_test_function(node: ast.AST) -> bool:
    """Check if a function or method is a test function.

    Args:
        node: The AST node to check (should be FunctionDef or AsyncFunctionDef)

    Returns:
        True if the function name starts with 'test_', False otherwise
    """
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return node.name.startswith("test_")
    return False


def check_test_file(file_path: str) -> bool:
    """Check that all test functions in a file have only one assertion.

    Args:
        file_path: Path to the test file to check

    Returns:
        True if all tests have at most one assertion, False otherwise
    """
    path = Path(file_path)
    if not path.exists():
        return True

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content, filename=str(path))

        errors = []
        for node in ast.walk(tree):
            if is_test_function(node):
                assertion_count = count_assertions(node)
                if assertion_count > 1:
                    line_no = node.lineno
                    # Type narrowing: we know node is FunctionDef or AsyncFunctionDef
                    # from is_test_function check
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        errors.append(
                            f"  {file_path}:{line_no}: "
                            f"Test '{node.name}' has {assertion_count} assertions "
                            f"(expected at most 1)"
                        )

        if errors:
            print("ERROR: Multiple assertions found in test functions:")
            for error in errors:
                print(error)
            return False

        return True
    except SyntaxError as e:
        print(f"ERROR: Failed to parse {file_path}: {e}")
        return False
    except (OSError, UnicodeDecodeError) as e:
        print(f"ERROR: Failed to check {file_path}: {e}")
        return False


def main():
    """Main entry point for the pre-commit hook."""
    failed = False

    # Only check test files
    for file_path in sys.argv[1:]:
        # Only process test files
        if "tests/" not in file_path and not Path(file_path).name.startswith("test_"):
            continue
        if not check_test_file(file_path):
            failed = True

    if failed:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
