#!/usr/bin/env python3
"""
Audiobookshelf Metadata Harmony Agent - CLI Entry Point

Harmonizes metadata across related books in an Audiobookshelf library.

Usage:
    python harmony_agent.py              # Dry-run mode (default)
    python harmony_agent.py --update     # Apply updates
    python harmony_agent.py --confidence 0.85 --update  # Custom threshold
    python harmony_agent.py --verbose    # Verbose logging
"""

import argparse
import asyncio
import sys
import logging
from pathlib import Path

from harmony_config import (
    load_config,
    setup_logging,
    print_config_summary,
    validate_environment,
    ConfigurationError,
)
from harmony_database import HarmonyDatabase
from harmony_orchestrator import HarmonyOrchestrator
from harmony_models import HarmonyConfig


logger = logging.getLogger(__name__)


def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="Audiobookshelf Metadata Harmony Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry-run mode (default - no changes applied)
  python harmony_agent.py

  # Apply updates
  python harmony_agent.py --update

  # Custom confidence threshold
  python harmony_agent.py --confidence 0.85 --update

  # Force rescan (ignore cache)
  python harmony_agent.py --force-rescan

  # Verbose logging
  python harmony_agent.py --verbose

  # Custom environment file
  python harmony_agent.py --env-file .env.production

For more information, see README.md
        """
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=None,
        help="Analyze and report only, don't apply updates (default: True)"
    )

    parser.add_argument(
        "--update",
        action="store_true",
        help="Actually apply updates (disables dry-run)"
    )

    parser.add_argument(
        "--confidence",
        type=float,
        default=None,
        metavar="THRESHOLD",
        help="Confidence threshold for auto-applying updates (0.0-1.0, default: 0.8)"
    )

    parser.add_argument(
        "--force-rescan",
        action="store_true",
        help="Force recalculation of cached data"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    parser.add_argument(
        "--env-file",
        type=str,
        default=None,
        metavar="PATH",
        help="Path to environment file (default: .env or .env.harmony)"
    )

    parser.add_argument(
        "--cache-file",
        type=str,
        default=None,
        metavar="PATH",
        help="Path to cache database (default: .harmony_cache.sqlite)"
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        metavar="DIR",
        help="Directory for report output (default: ./reports)"
    )

    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate environment configuration and exit"
    )

    return parser.parse_args()


async def main():
    """Main entry point"""
    args = parse_args()

    try:
        # Validate environment first
        if args.validate_only:
            print("Validating environment configuration...")
            success, errors = validate_environment()
            if success:
                print("[OK] Environment validation passed")
                return 0
            else:
                print("[FAIL] Environment validation failed:")
                for error in errors:
                    print(f"  - {error}")
                return 1

        # Load configuration
        config = load_config(env_file=args.env_file)

        # Override with command-line arguments
        if args.update:
            config.dry_run = False
        elif args.dry_run is not None:
            config.dry_run = args.dry_run

        if args.confidence is not None:
            if not 0.0 <= args.confidence <= 1.0:
                print(f"Error: Confidence threshold must be between 0.0 and 1.0, got {args.confidence}")
                return 1
            config.confidence_threshold = args.confidence

        if args.force_rescan:
            config.force_rescan = True

        if args.verbose:
            config.verbose = True
            config.log_level = 'DEBUG'

        if args.cache_file:
            config.cache_file = args.cache_file

        if args.output_dir:
            config.output_dir = args.output_dir

        # Setup logging
        setup_logging(config)

        # Print configuration
        if not args.verbose:
            print_config_summary(config)

        # Validate environment
        success, errors = validate_environment()
        if not success:
            logger.error("Environment validation failed:")
            for error in errors:
                logger.error(f"  - {error}")
            return 1

        # Initialize database
        logger.info(f"Initializing database: {config.cache_file}")
        database = HarmonyDatabase(config.cache_file)

        # Initialize orchestrator
        logger.info("Initializing harmony orchestrator...")
        orchestrator = HarmonyOrchestrator(config, database)

        # Run harmonization workflow
        logger.info("Starting harmonization workflow...")
        report = await orchestrator.run()

        # Print summary
        print()
        print("=" * 60)
        print("HARMONY AGENT REPORT")
        print("=" * 60)
        print(f"Mode:                 {'DRY-RUN' if report.dry_run else 'LIVE UPDATE'}")
        print(f"Duration:             {report.duration_seconds:.2f} seconds")
        print(f"Books Scanned:        {report.books_scanned}/{report.total_books}")
        print(f"Relationships Found:  {report.relationships_found}")
        print(f"Discrepancies Found:  {report.discrepancies_found}")

        if not report.dry_run:
            print(f"Updates Applied:      {report.updates_applied}")
            print(f"Updates Failed:       {report.updates_failed}")

        print(f"Manual Review Queue:  {report.books_flagged_for_review}")
        print(f"Avg Completeness:     {report.avg_completeness_before:.2%} → {report.avg_completeness_after:.2%}")
        print(f"Validation:           {'PASSED' if report.validation_passed else 'FAILED'}")
        print()

        # Relationship breakdown
        if report.relationships_by_type:
            print("Relationships by Type:")
            for rel_type, count in sorted(report.relationships_by_type.items()):
                print(f"  {rel_type:20s} {count:5d}")
            print()

        # Discrepancy breakdown
        if report.discrepancies_by_field:
            print("Discrepancies by Field:")
            for field, count in sorted(
                report.discrepancies_by_field.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]:
                print(f"  {field:20s} {count:5d}")
            print()

        # Confidence distribution
        if report.confidence_distribution:
            print("Confidence Distribution:")
            for range_str, count in sorted(report.confidence_distribution.items()):
                print(f"  {range_str:10s} {count:5d}")
            print()

        # Validation errors
        if report.validation_errors:
            print("Validation Errors:")
            for error in report.validation_errors[:10]:
                print(f"  - {error}")
            if len(report.validation_errors) > 10:
                print(f"  ... and {len(report.validation_errors) - 10} more")
            print()

        print("=" * 60)

        # Save detailed report
        output_dir = Path(config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        report_file = output_dir / f"harmony_report_{report.timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            f.write(report.model_dump_json(indent=2))

        print(f"Detailed report saved to: {report_file}")
        print()

        if report.dry_run:
            print("[INFO] This was a DRY-RUN. No changes were applied.")
            print("       Run with --update to apply changes.")
        else:
            print("[OK] Updates applied successfully!")

        return 0

    except ConfigurationError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        print("\nPlease check your .env file or environment variables.", file=sys.stderr)
        return 1

    except KeyboardInterrupt:
        print("\n\nInterrupted by user", file=sys.stderr)
        return 130

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\nFatal error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
