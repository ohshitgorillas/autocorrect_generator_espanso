"""Configuration management for EntropPy."""

import json
from argparse import ArgumentParser
from dataclasses import dataclass, field
from multiprocessing import cpu_count
from typing import TYPE_CHECKING

from loguru import logger

from entroppy.core.boundaries import BoundaryType

if TYPE_CHECKING:
    from entroppy.utils.debug import DebugTypoMatcher


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
    debug: bool = False
    jobs: int = field(default_factory=cpu_count)
    max_entries_per_file: int = 500
    reports: str | None = None

    # Platform selection
    platform: str = "espanso"  # "espanso", "qmk", etc.
    max_corrections: int | None = None  # QMK memory limit

    # Debug tracing
    debug_words: set[str] = field(default_factory=set)  # Exact word matches only
    debug_typos: set[str] = field(default_factory=set)  # Raw patterns with wildcards/boundaries
    debug_typo_matcher: "DebugTypoMatcher | None" = field(
        default=None, init=False
    )  # Created after parsing


def _validate_config(config: Config) -> None:
    """Validate configuration parameters.
    
    Raises:
        ValueError: If any configuration parameter is invalid
    """
    if config.min_typo_length < 1:
        raise ValueError(f"min_typo_length must be >= 1, got {config.min_typo_length}")
    
    if config.min_word_length < 1:
        raise ValueError(f"min_word_length must be >= 1, got {config.min_word_length}")
    
    if config.max_word_length and config.max_word_length < config.min_word_length:
        raise ValueError(
            f"max_word_length ({config.max_word_length}) must be >= "
            f"min_word_length ({config.min_word_length})"
        )
    
    if config.freq_ratio <= 0:
        raise ValueError(f"freq_ratio must be > 0, got {config.freq_ratio}")
    
    if config.top_n and config.top_n < 1:
        raise ValueError(f"top_n must be >= 1, got {config.top_n}")
    
    if config.max_corrections and config.max_corrections < 1:
        raise ValueError(f"max_corrections must be >= 1, got {config.max_corrections}")
    
    if config.max_entries_per_file < 1:
        raise ValueError(
            f"max_entries_per_file must be >= 1, got {config.max_entries_per_file}"
        )
    
    if config.typo_freq_threshold < 0:
        raise ValueError(
            f"typo_freq_threshold must be >= 0, got {config.typo_freq_threshold}"
        )
    
    if config.jobs < 1:
        raise ValueError(f"jobs must be >= 1, got {config.jobs}")


def load_config(json_path: str | None, cli_args, parser: ArgumentParser) -> Config:
    """Load JSON config, override with CLI args, return Config object."""

    def get_value(key: str, fallback):
        """Get value with correct priority: CLI > JSON > Fallback."""
        cli_value = getattr(cli_args, key)
        default_value = parser.get_default(key)
        # Use CLI value only if it was explicitly set by the user
        if cli_value != default_value:
            return cli_value
        # Otherwise, try JSON, then the hardcoded fallback
        return json_config.get(key, fallback)

    def parse_string_set(value) -> set[str]:
        """Parse comma-separated string or array into set of lowercase, stripped strings."""
        if value is None or value == "":
            return set()
        if isinstance(value, list):
            # JSON array format
            return {s.strip().lower() for s in value if s.strip()}
        if isinstance(value, str):
            # Comma-separated string format
            return {s.strip().lower() for s in value.split(",") if s.strip()}
        return set()

    json_config = {}
    if json_path:
        from entroppy.utils import expand_file_path

        json_path = expand_file_path(json_path) or json_path
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                json_config = json.load(f)
        except FileNotFoundError:
            logger.error(f"Config file not found: {json_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file {json_path}: {e}")
            raise ValueError(f"Invalid JSON configuration: {e}") from e
        except PermissionError:
            logger.error(f"Permission denied reading config file: {json_path}")
            raise
        except UnicodeDecodeError as e:
            logger.error(f"Encoding error reading config file {json_path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error reading config file {json_path}: {e}")
            raise

    # Parse debug words and typos
    debug_words_raw = get_value("debug_words", None)
    debug_typos_raw = get_value("debug_typos", None)
    debug_words = parse_string_set(debug_words_raw)
    debug_typos = parse_string_set(debug_typos_raw)

    # Build config with CLI args taking precedence over JSON
    config = Config(
        platform=get_value("platform", "espanso"),
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
        debug=cli_args.debug or json_config.get("debug", False),
        jobs=get_value("jobs", cpu_count()),
        max_entries_per_file=get_value("max_entries_per_file", 500),
        reports=get_value("reports", None),
        max_corrections=get_value("max_corrections", None),
        debug_words=debug_words,
        debug_typos=debug_typos,
    )

    _validate_config(config)

    return config
