"""Main entry point for autocorrgen package."""

from loguru import logger

from entroppy.cli import create_parser
from entroppy.core import load_config
from entroppy.processing import run_pipeline
from entroppy.utils.debug import DebugTypoMatcher
from entroppy.utils.logging import setup_logger


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config, args, parser)

    # Setup logging
    setup_logger(verbose=config.verbose, debug=config.debug)

    # Validate
    if not config.top_n and not config.include:
        parser.error("Must specify either --top-n or --include (or both)")

    if not config.platform:
        parser.error("Must specify a platform")
    if config.platform == "qmk" and not config.max_corrections:
        parser.error("Must specify --max-corrections for QMK")
    from entroppy.utils import Constants

    if config.platform == "espanso" and config.max_entries_per_file > Constants.ESPANSO_MAX_ENTRIES_WARNING:
        logger.warning("--------------------------------")
        logger.warning("!!! WARNING:")
        logger.warning("max_entries_per_file is greater than 1000")
        logger.warning("This is not recommended and may cause Espanso performance issues")
        logger.warning("--------------------------------")

    # Validate debug flags
    if (config.debug_words or config.debug_typos) and not (config.debug and config.verbose):
        parser.error("--debug-words and --debug-typos require BOTH --debug and --verbose flags")

    # Create debug typo matcher (post-init)
    if config.debug_typos:
        config.debug_typo_matcher = DebugTypoMatcher.from_patterns(config.debug_typos)

    # Run pipeline
    run_pipeline(config)


if __name__ == "__main__":
    main()
