"""Configuration management for autocorrgen."""

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from multiprocessing import cpu_count
from argparse import ArgumentParser


class BoundaryType(Enum):
    """Boundary types for Espanso matches."""

    NONE = "none"  # No boundaries - triggers anywhere
    LEFT = "left"  # Left boundary only - must be at word start
    RIGHT = "right"  # Right boundary only - must be at word end
    BOTH = "both"  # Both boundaries - standalone word only


# Type alias for corrections
Correction = tuple[str, str, BoundaryType]  # (typo, correct_word, boundary_type)


@dataclass
class Config:
    """Configuration for typo generation."""

    top_n: int | None = None
    max_word_length: int = 10
    min_word_length: int = 3
    min_typo_length: int = 3
    freq_ratio: float = 10.0
    typo_freq_threshold: float = 0.0
    output: str | None = None
    include: str | None = None
    exclude: str | None = None
    adjacent_letters: str | None = None
    verbose: bool = False
    jobs: int = field(default_factory=cpu_count)
    max_entries_per_file: int = 500


def load_config(json_path: str | None, cli_args, parser: ArgumentParser) -> Config:
    """Load JSON config, override with CLI args, return Config object."""
    json_config = {}
    if json_path:
        json_path = os.path.expanduser(json_path)
        with open(json_path, "r", encoding="utf-8") as f:
            json_config = json.load(f)

    def get_value(key: str, fallback):
        """Get value with correct priority: CLI > JSON > Fallback."""
        cli_value = getattr(cli_args, key)
        default_value = parser.get_default(key)
        # Use CLI value only if it was explicitly set by the user
        if cli_value != default_value:
            return cli_value
        # Otherwise, try JSON, then the hardcoded fallback
        return json_config.get(key, fallback)

    # Build config with CLI args taking precedence over JSON
    return Config(
        top_n=get_value("top_n", None),
        max_word_length=get_value("max_word_length", 10),
        min_word_length=get_value("min_word_length", 3),
        min_typo_length=get_value("min_typo_length", 3),
        freq_ratio=get_value("freq_ratio", 10.0),
        typo_freq_threshold=get_value("typo_freq_threshold", 0.0),
        output=get_value("output", None),
        include=get_value("include", None),
        exclude=get_value("exclude", None),
        adjacent_letters=get_value("adjacent_letters", None),
        verbose=cli_args.verbose or json_config.get("verbose", False),
        jobs=get_value("jobs", cpu_count()),
        max_entries_per_file=get_value("max_entries_per_file", 500),
    )
