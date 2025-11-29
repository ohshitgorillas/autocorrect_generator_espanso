"""Main entry point for autocorrgen package."""

from .cli import create_parser
from .config import load_config
from .pipeline import run_pipeline


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config, args, parser)

    # Validate
    if not config.top_n and not config.include:
        parser.error("Must specify either --top-n or --include (or both)")

    if not config.platform:
        parser.error("Must specify a platform")
    if config.platform == "qmk" and not config.max_corrections:
        parser.error("Must specify --max-corrections for QMK")
    if config.platform == "espanso" and config.max_entries_per_file > 1000:
        print("--------------------------------")
        print("!!! WARNING:")
        print("max_entries_per_file is greater than 1000")
        print("This is not recommended and may cause Espanso performance issues")
        print("--------------------------------")

    # Run pipeline
    run_pipeline(config)


if __name__ == "__main__":
    main()
