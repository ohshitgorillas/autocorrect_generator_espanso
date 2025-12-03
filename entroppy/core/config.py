"""Configuration management for EntropPy."""

from __future__ import annotations

import json
from argparse import ArgumentParser
from multiprocessing import cpu_count
from typing import Literal

from loguru import logger
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from entroppy.utils import expand_file_path
from entroppy.utils.debug import DebugTypoMatcher


class Config(BaseModel):
    """Configuration for typo generation."""

    top_n: int | None = Field(None, ge=1, description="Top N most common words")
    max_word_length: int = Field(10, ge=1, description="Maximum word length")
    min_word_length: int = Field(3, ge=1, description="Minimum word length")
    min_typo_length: int = Field(3, ge=1, description="Minimum typo length")
    freq_ratio: float = Field(10.0, gt=0, description="Frequency ratio threshold")
    typo_freq_threshold: float = Field(0.0, ge=0, description="Typo frequency threshold")
    output: str | None = None
    include: str | None = None
    exclude: str | None = None
    adjacent_letters: str | None = None
    verbose: bool = False
    debug: bool = False
    jobs: int = Field(default_factory=cpu_count, ge=1)
    max_entries_per_file: int = Field(500, ge=1)
    reports: str | None = None

    # Platform selection
    platform: Literal["espanso", "qmk"] = Field("espanso", description="Target platform")
    max_corrections: int | None = Field(None, ge=1, description="QMK memory limit")
    max_iterations: int = Field(10, ge=1, description="Maximum iterations for iterative solver")

    # Debug tracing
    debug_words: set[str] = Field(default_factory=set, description="Exact word matches only")
    debug_typos: set[str] = Field(
        default_factory=set, description="Raw patterns with wildcards/boundaries"
    )
    debug_typo_matcher: DebugTypoMatcher | None = Field(
        default=None, exclude=True, description="Created after parsing"
    )

    @field_validator("debug_words", "debug_typos", mode="before")
    @classmethod
    def parse_string_set(cls, v):
        """Parse comma-separated string or array into set."""
        if v is None or v == "":
            return set()
        if isinstance(v, list):
            return {s.strip().lower() for s in v if s.strip()}
        if isinstance(v, str):
            return {s.strip().lower() for s in v.split(",") if s.strip()}
        return set()

    @model_validator(mode="after")
    def validate_cross_fields(self):
        """Validate cross-field constraints."""
        if self.max_word_length < self.min_word_length:
            raise ValueError(
                f"max_word_length ({self.max_word_length}) must be >= "
                f"min_word_length ({self.min_word_length})"
            )
        if self.platform == "qmk" and not self.max_corrections:
            raise ValueError("max_corrections is required for QMK platform")
        return self

    model_config = {
        "arbitrary_types_allowed": True,  # For DebugTypoMatcher
    }


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

    json_config = {}
    if json_path:
        json_path = expand_file_path(json_path) or json_path
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                json_config = json.load(f)
        except FileNotFoundError:
            logger.error(f"✗ Config file not found: {json_path}")
            logger.error("  Please check the file path and try again")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"✗ Invalid JSON in config file {json_path}: {e}")
            logger.error("  Please validate your JSON syntax")
            raise ValueError(f"Invalid JSON configuration: {e}") from e
        except PermissionError:
            logger.error(f"✗ Permission denied reading config file: {json_path}")
            logger.error("  Please check file permissions and try again")
            raise
        except UnicodeDecodeError as e:
            logger.error(f"✗ Encoding error reading config file {json_path}: {e}")
            logger.error("  Please ensure the file is UTF-8 encoded")
            raise
        except Exception as e:
            logger.error(f"✗ Unexpected error reading config file {json_path}: {e}")
            raise

    # Build config dict with CLI args taking precedence over JSON
    # Pydantic will handle validation and type coercion automatically
    config_dict = {
        "platform": get_value("platform", "espanso"),
        "top_n": get_value("top_n", None),
        "max_word_length": get_value("max_word_length", 10),
        "min_word_length": get_value("min_word_length", 3),
        "min_typo_length": get_value("min_typo_length", 3),
        "freq_ratio": get_value("freq_ratio", 10.0),
        "typo_freq_threshold": get_value("typo_freq_threshold", 0.0),
        "output": get_value("output", None),
        "include": get_value("include", None),
        "exclude": get_value("exclude", None),
        "adjacent_letters": get_value("adjacent_letters", None),
        "verbose": cli_args.verbose or json_config.get("verbose", False),
        "debug": cli_args.debug or json_config.get("debug", False),
        "jobs": get_value("jobs", cpu_count()),
        "max_entries_per_file": get_value("max_entries_per_file", 500),
        "reports": get_value("reports", None),
        "max_corrections": get_value("max_corrections", None),
        "max_iterations": get_value("max_iterations", 10),
        "debug_words": get_value("debug_words", None),
        "debug_typos": get_value("debug_typos", None),
    }

    # Pydantic handles validation automatically
    try:
        return Config.model_validate(config_dict)
    except ValidationError as e:
        logger.error(f"✗ Configuration validation failed: {e}")
        logger.error("  Please check your configuration values")
        raise ValueError(f"Invalid configuration: {e}") from e
