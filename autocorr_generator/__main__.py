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

    # Run pipeline
    run_pipeline(config)


if __name__ == "__main__":
    main()
