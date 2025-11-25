"""Configuration management for autocorrgen."""

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from multiprocessing import cpu_count


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


def load_config(json_path: str | None, cli_args) -> Config:
    """Load JSON config, override with CLI args, return Config object."""
    json_config = {}
    if json_path:
        json_path = os.path.expanduser(json_path)
        with open(json_path, "r", encoding="utf-8") as f:
            json_config = json.load(f)

    # Build config with CLI args taking precedence over JSON
    return Config(
        top_n=(
            cli_args.top_n if cli_args.top_n is not None else json_config.get("top_n")
        ),
        max_word_length=(
            cli_args.max_word_length
            if cli_args.max_word_length is not None
            else json_config.get("max_word_length", 10)
        ),
        min_word_length=(
            cli_args.min_word_length
            if cli_args.min_word_length is not None
            else json_config.get("min_word_length", 3)
        ),
        min_typo_length=(
            cli_args.min_typo_length
            if cli_args.min_typo_length is not None
            else json_config.get("min_typo_length", 3)
        ),
        freq_ratio=(
            cli_args.freq_ratio
            if cli_args.freq_ratio is not None
            else json_config.get("freq_ratio", 10.0)
        ),
        typo_freq_threshold=(
            cli_args.typo_freq_threshold
            if cli_args.typo_freq_threshold is not None
            else json_config.get("typo_freq_threshold", 0.0)
        ),
        output=cli_args.output if cli_args.output else json_config.get("output"),
        include=cli_args.include if cli_args.include else json_config.get("include"),
        exclude=cli_args.exclude if cli_args.exclude else json_config.get("exclude"),
        adjacent_letters=(
            cli_args.adjacent_letters
            if cli_args.adjacent_letters
            else json_config.get("adjacent_letters")
        ),
        verbose=cli_args.verbose or json_config.get("verbose", False),
        jobs=(
            cli_args.jobs
            if cli_args.jobs is not None
            else json_config.get("jobs", cpu_count())
        ),
    )
