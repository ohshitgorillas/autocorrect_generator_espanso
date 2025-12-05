"""Helper functions for pipeline initialization and setup."""

from pathlib import Path

from loguru import logger

from entroppy.core import Config
from entroppy.platforms import PlatformBackend, get_platform_backend
from entroppy.reports import ReportData, create_report_directory
from entroppy.utils.logging import add_log_file_handler


def initialize_platform(config: Config) -> PlatformBackend:
    """Initialize and validate platform backend.

    Args:
        config: Configuration object

    Returns:
        Initialized platform backend

    Raises:
        ValueError: If platform is invalid
        Exception: For unexpected errors
    """
    try:
        platform = get_platform_backend(config.platform)
    except ValueError as e:
        logger.error(f"✗ Invalid platform '{config.platform}': {e}")
        logger.error("  Supported platforms: espanso, qmk")
        raise
    except Exception as e:
        logger.error(f"✗ Unexpected error getting platform backend: {e}")
        raise
    return platform


def setup_reporting(
    config: Config, platform: PlatformBackend, start_time: float
) -> tuple[ReportData | None, Path | None]:
    """Set up reporting infrastructure if enabled.

    Args:
        config: Configuration object
        platform: Platform backend
        start_time: Pipeline start time

    Returns:
        Tuple of (report_data, report_dir) or (None, None) if reports disabled
    """
    if not config.reports:
        return None, None

    report_data = ReportData(start_time=start_time)
    platform_name = platform.get_name()
    report_dir = create_report_directory(config.reports, platform_name)

    # Set up log file in report directory
    # Extract timestamp from directory name (format: YYYY-MM-DD_HH-MM-SS_platform)
    # Timestamp is always the first 19 characters: YYYY-MM-DD_HH-MM-SS
    timestamp = report_dir.name[:19]
    log_file = report_dir / f"entroppy-{timestamp}.log"
    add_log_file_handler(log_file, verbose=config.verbose, debug=config.debug)

    if config.verbose:
        logger.info(f"Logs will be saved to: {log_file}")
        logger.info("")

    return report_data, report_dir
