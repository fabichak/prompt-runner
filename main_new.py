#!/usr/bin/env python3
"""
Prompt Runner - Main entry point (Simplified with Unified Orchestrator)
API-driven job processing system using ComfyUI workflows
"""

import argparse
import logging
import sys
import uuid
import time
from pathlib import Path
from datetime import datetime

# Set up config before other imports
import config
config.CLIENT_ID = str(uuid.uuid4())

from services.runpod_utils import RunPodManager
from services.slackClient import SlackClient
from services.unified_orchestrator import UnifiedOrchestrator
from services.trello_client import TrelloApiClient
from services.service_factory import ServiceFactory
from services.mode_registry import ModeRegistry


def setup_logging(log_level: str = "INFO", timestamp: str = None):
    """Set up logging configuration"""
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Determine log file location
    log_filename = f"prompt_runner_{timestamp}.log"
    log_filepath = Path(log_filename)

    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(str(log_filepath))
        ]
    )

    return logging.getLogger(__name__)


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Prompt Runner - API-driven job processing for ComfyUI"
    )

    # Trello API processing
    parser.add_argument(
        "--trello",
        action="store_true",
        help="Process jobs from Trello API"
    )

    # Continuous mode
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Run continuously, polling for new jobs"
    )

    parser.add_argument(
        "--poll-interval",
        type=int,
        default=15,
        help="Polling interval in seconds (default: 15)"
    )

    parser.add_argument(
        "--max-poll-seconds",
        type=int,
        default=600,
        help="Maximum polling time in seconds (default: 600)"
    )

    # Dry run mode
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate execution without actually processing"
    )

    # Error handling
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue processing even if a job fails"
    )

    # RunPod control
    parser.add_argument(
        "--no-shutdown",
        action="store_true",
        help="Don't shutdown RunPod instance after completion"
    )

    # Upload control
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="Don't upload results to cloud storage"
    )

    # Logging
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level"
    )

    # Debug/Testing
    parser.add_argument(
        "--test-api",
        action="store_true",
        help="Test Trello API connection and exit"
    )

    parser.add_argument(
        "--list-modes",
        action="store_true",
        help="List available processing modes and exit"
    )

    return parser.parse_args()


def test_api_connection(logger):
    """Test Trello API connection"""
    try:
        client = TrelloApiClient(config.TRELLO_API_BASE_URL)
        logger.info(f"Testing API connection to {config.TRELLO_API_BASE_URL}")

        # Try to get next card (might be None)
        card = client.get_next_card(timeout=10)

        if card:
            logger.info(f"✅ API connection successful. Found card: {card.get('cardName', 'Unknown')}")
        else:
            logger.info("✅ API connection successful. No cards available.")

        return True
    except Exception as e:
        logger.error(f"❌ API connection failed: {e}")
        return False


def process_trello_jobs(args, logger) -> int:
    """Main processing loop for API jobs"""
    orchestrator = UnifiedOrchestrator()
    client = TrelloApiClient(config.TRELLO_API_BASE_URL)
    slack_client = SlackClient()

    poll_interval = 15
    max_poll_seconds = 600
    jobs_processed = 0

    logger.info(f"Starting Trello job processing (continuous={args.continuous})")

    while True:
        card = None
        try:
            # Get next job from API
            logger.debug("Fetching next card from Trello API")
            card = client.get_next_card()
        except Exception as e:
            logger.warning(f"Error fetching next Trello card: {e}")
            card = None

        if not card:
            if not args.continuous:
                logger.info("No more cards to process. Exiting.")
                try:
                    client.delete_machine()
                except Exception as e:
                    logger.warning(f"Could not request machine deletion: {e}")
                break

            logger.info(
                f"No cards available. Polling for up to {max_poll_seconds}s "
                f"(interval {poll_interval}s)..."
            )

            deadline = time.time() + max_poll_seconds

            while time.time() < deadline and not card:
                time.sleep(poll_interval)
                try:
                    logger.info("Polling for next card from Trello API")
                    card = client.get_next_card()
                except Exception as e:
                    logger.warning(f"Polling error: {e}")
                    slack_client.send_message(f"Erro ao buscar card: {e}")

            if not card:
                logger.info("No cards found during polling window. Stopping.")
                try:
                    client.delete_machine()
                except Exception as e:
                    logger.warning(f"Could not request machine deletion: {e}")
                break

        # Process the card
        try:
            card_name = card.get('cardName', 'Unknown')
            logger.info(f"Processing card: {card_name}")

            result = orchestrator.process_api_job(card, dry_run=args.dry_run)

            if result['status'] == 'completed':
                jobs_processed += 1
                logger.info(f"✅ Successfully processed: {card_name}")
            elif result['status'] == 'dry_run':
                logger.info(f"🔧 Dry run completed: {card_name}")
            else:
                logger.error(f"❌ Failed to process: {card_name} - {result.get('error')}")
                if not args.continue_on_error:
                    logger.warning("Stopping due to error (use --continue-on-error to continue)")
                    break

        except Exception as e:
            logger.error(f"Error processing card: {e}", exc_info=True)
            if not args.continue_on_error:
                break

    # Print summary
    status = orchestrator.get_status()
    logger.info("=" * 60)
    logger.info("Processing Summary:")
    logger.info(f"  Completed: {status['completed_jobs']} jobs")
    logger.info(f"  Failed: {status['failed_jobs']} jobs")
    logger.info(f"  Total processed: {jobs_processed} cards")
    logger.info("=" * 60)

    return 0 if status['failed_jobs'] == 0 else 1


def main():
    """Main entry point"""
    # Generate timestamp for this run
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Parse arguments
    args = parse_arguments()

    # Set up logging
    logger = setup_logging(args.log_level, timestamp)

    logger.info("=" * 80)
    logger.info("PROMPT RUNNER - Unified Job Processing System")
    logger.info("=" * 80)
    logger.info(f"Session ID: {config.CLIENT_ID}")
    logger.info(f"Timestamp: {timestamp}")
    logger.info(f"Available modes: {', '.join(ModeRegistry.get_available_modes())}")

    try:
        # Handle special commands
        if args.list_modes:
            print("\nAvailable processing modes:")
            for mode in ModeRegistry.get_available_modes():
                print(f"  - {mode}")
            return 0

        if args.test_api:
            return 0 if test_api_connection(logger) else 1

        # Main processing
        if args.trello:
            exit_code = process_trello_jobs(args, logger)
        else:
            logger.error("Please use --trello flag to process jobs from API")
            logger.info("Example: python main.py --trello --continuous")
            return 1

        # Handle RunPod shutdown if requested
        if exit_code == 0 and not args.no_shutdown:
            try:
                runpod = ServiceFactory.create_runpod_manager()
                runpod.shutdown_current_pod()
                logger.info("🔌 RunPod instance shutdown initiated")
            except Exception as e:
                logger.warning(f"Could not shutdown RunPod: {e}")

        logger.info("✅ All operations completed")
        return exit_code

    except KeyboardInterrupt:
        logger.info("⚠️ Interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())