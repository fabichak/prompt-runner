#!/usr/bin/env python3
"""
Prompt Runner - Main entry point
Video generation system using ComfyUI workflows
"""

import argparse
import json
import logging
import sys
import uuid
import time
from pathlib import Path
from datetime import datetime

# Set up config before other imports
import config
from services.storage_utils import StorageManager
config.CLIENT_ID = str(uuid.uuid4())

from models.prompt_data import PromptData
from services.job_orchestrator import JobOrchestrator
from services.service_factory import ServiceFactory
from services.i2i_orchestrator import I2IOrchestrator
from services.trello_client import TrelloApiClient
from utils.file_parser import PromptFileParser
from utils.job_planner import JobPlanner


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
        description="Prompt Runner - Video generation automation for ComfyUI"
    )
    
    # Mode selection
    parser.add_argument(
        "--mode",
        choices=["v2v", "i2i"],
        default="v2v",
        help="Operation mode: v2v (video-to-video) or i2i (image-to-image)"
    )
    
    # Core arguments
    parser.add_argument(
        "prompt_file",
        nargs="?",
        help="Path to prompt text file (optional if using --prompt-dir or --mode i2i)"
    )
    
    parser.add_argument(
        "--prompt-dir",
        type=str,
        help="Directory containing prompt files to process"
    )
    
    parser.add_argument(
        "--resume",
        type=str,
        help="Resume from saved state file (provide promptName)"
    )
    
    parser.add_argument(
        "--start-at",
        type=int,
        default=0,
        help="Start processing at this prompt index (for batch processing)"
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
        help="Skip uploading to cloud storage"
    )
    
    parser.add_argument(
        "--no-archive",
        action="store_true",
        help="Skip creating tar archives"
    )
    
    # i2i mode specific arguments
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Continuously monitor for new images (i2i mode only)"
    )
    
    # Logging
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level"
    )
    
    parser.add_argument(
        "--full-logs",
        action="store_true",
        help="Show detailed output from all operations"
    )

    # Dry run (no ComfyUI execution)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not connect to ComfyUI; only generate and save workflows"
    )

    # Trello helper
    parser.add_argument(
        "--trello",
        action="store_true",
        help="Call POST /api/trello/getNextCard on the configured Trello API base URL and print the result"
    )
    
    args = parser.parse_args()
    
    # Set defaults/validate based on mode
    if args.mode == "v2v":
        if not args.prompt_file and not args.prompt_dir:
            # Default to configured directory when nothing provided
            args.prompt_dir = config.INPUT_PROMPT_DIR
    # i2i mode doesn't require prompt files
    
    return args


def process_single_prompt(prompt_data: PromptData, promptName: str, args) -> bool:
    """Process a single prompt through the pipeline
    
    Args:
        prompt_data: The prompt data to process
        promptName: Name for organizing this prompt's files
        args: Command line arguments
        
    Returns:
        True if successful, False otherwise
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Create job orchestrator
        orchestrator = JobOrchestrator()
        
        # Execute the pipeline
        success = orchestrator.execute_full_pipeline(
            prompt_data=prompt_data,
            promptName=promptName,
            resume_from_state=args.resume,
            dry_run=getattr(args, "dry_run", False)
        )
        
        if success:
            logger.info(f"✅ Successfully processed prompt: {promptName}")
            
            # Handle uploads if not disabled
            if not args.no_upload:
                storage = ServiceFactory.create_storage_manager()
                                
                # Upload to cloud storage
                storage.zip_and_upload_output(promptName)
                #storage.cleanup_intermediate_files(promptName)
                logger.info(f"☁️ Uploaded to cloud storage")
        else:
            logger.error(f"❌ Failed to process prompt: {promptName}")
            
        return success
        
    except Exception as e:
        logger.error(f"Error processing prompt {promptName}: {e}", exc_info=True)
        return False

def process_all_prompt_directories_trello(args) -> int:
    logger = logging.getLogger(__name__)
    client = TrelloApiClient(config.TRELLO_API_BASE_URL)

    poll_interval = getattr(args, "poll_interval", 15)
    max_poll_seconds = getattr(args, "max_poll_seconds", 600)  # 10 minutos

    while True:
        card = None
        try:
            card = client.get_next_card()
        except Exception as e:
            logger.warning(f"Error fetching next Trello card: {e}")
            card = None

        if not card:
            logger.info(
                f"No more Trello cards to process. Polling for up to "
                f"{max_poll_seconds}s (interval {poll_interval}s)..."
            )
            deadline = time.time() + max_poll_seconds

            while time.time() < deadline and not card:
                time.sleep(poll_interval)
                try:
                    card = client.get_next_card()
                except Exception as e:
                    logger.warning(f"Polling error on get_next_card: {e}")

            if not card:
                logger.info("No cards found during polling window. Stopping.")
                break

        logger.info(f"Processing card {card.get('cardName')}")
        exit_code = process_prompt_directory_trello(args, card)

        if exit_code != 0 and not getattr(args, "continue_on_error", False):
            logger.warning("Stopping because of error in card processing.")
            break

    return 0


def process_prompt_directory_trello(args, card) -> int:
    logger = logging.getLogger(__name__)


    # --- I2I FLOW (Image) ---
    if card.get("responseType") == "Image":
        try:
            orchestrator = I2IOrchestrator(card)
            status = orchestrator.get_status(card.get("cfg"))
            logger.info(f"CFG Values: {status.get('cfg_values')}")
            logger.info(f"Renders per CFG: {status.get('renders_per_cfg')}")
            logger.info(f"Continuous mode: {getattr(args, 'continuous', False)}")

            response =orchestrator.run(continuous=args.continuous, cfg=card.get("cfg"))

            final_status = orchestrator.get_status(card.get("cfg"))
            logger.info("=" * 80)
            logger.info("I2I Processing Complete")
            logger.info(f"Processed: {final_status.get('processed')} images")
            logger.info(f"Failed: {final_status.get('failed')} images")
            logger.info(f"Pending: {final_status.get('pending')} images")
            logger.info("=" * 80)

            links = orchestrator.get_last_output_links() or {}
            gcs_link = links.get("gcs_path") or ""

            # Convert gs://bucket/path -> https://storage.googleapis.com/bucket/path
            if gcs_link.startswith("gs://"):
                https_link = "https://storage.googleapis.com/" + gcs_link[len("gs://"):]
            else:
                https_link = gcs_link

            result_payload = https_link or response

            # Clean up transient artifacts
            try:
                StorageManager().cleanup_temp_folder()
            except Exception:
                pass

            TrelloApiClient(config.TRELLO_API_BASE_URL).completed_card(
                card_id=card.get("cardId"),
                result=result_payload,
            )
            return 0
        except Exception as e:
            logger.warning(f"Could not process/report i2i output link: {e}")
            return 1

    # --- V2V FLOW (Video) ---
    try:
        prompt_data = PromptData(
            video_name=card.get("cardName"),
            start_frame=int(card.get("startFrame") or 0),
            total_frames=int(card.get("totalFrames") or 0),
            positive_prompt=card.get("description", ""),
            negative_prompt=card.get("negativePrompt", ""),
            image_reference=card.get("imageReference"),
            video_reference=card.get("videoSource"),
            # select_every_n_frames=int(card.get("selectEveryNFrames") or 1),
            source_file="trello",
        )

        logger.debug("V2V Processing Started")
        logger.debug("video-name: " + prompt_data.video_name)
        logger.debug("start-frame: " + str(prompt_data.start_frame))
        logger.debug("total-frames: " + str(prompt_data.total_frames))
        logger.debug("positive-prompt: " + prompt_data.positive_prompt)
        logger.debug("negative-prompt: " + prompt_data.negative_prompt)

        prompt_data.validate()

        promptName = card.get("cardId")

        # Plan + run
        job_planner = JobPlanner(promptName)
        render_jobs = job_planner.calculate_job_sequence(prompt_data)

        logger.info(f"Planned {len(render_jobs)} render job(s)")
        ok = process_single_prompt(prompt_data, promptName, args)

        # Clean up transient artifacts
        try:
            StorageManager().cleanup_temp_folder()
        except Exception:
            pass

        if ok:
            try:
                result_payload = str(render_jobs[0].video_output_full_path)
                TrelloApiClient(config.TRELLO_API_BASE_URL).completed_card(
                    card_id=card.get("cardId", promptName),
                    result=result_payload,
                )
                logger.info("Reported completion to Trello API: completedCard")
            except Exception as e:
                logger.error(f"Failed to report completion to Trello API: {e}")
            return 0
        else:
            return 1

    except Exception as e:
        logger.exception(f"Error during V2V processing for card {card.get('cardName')}: {e}")
        # Attempt cleanup even on failure
        try:
            StorageManager().cleanup_temp_folder()
        except Exception:
            pass
        return 1

def main():
    """Main entry point"""
    # Generate timestamp for this run
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Parse arguments
    args = parse_arguments()
    
    # Set up logging
    logger = setup_logging(args.log_level, timestamp)
    
    logger.info("=" * 80)
    logger.info("PROMPT RUNNER - Video Generation System")
    logger.info("=" * 80)
    logger.info(f"Session ID: {config.CLIENT_ID}")
    logger.info(f"Timestamp: {timestamp}")
    logger.info(f"Mode: {args.mode.upper()}")
    
    try:
        # Use Trello route-based input if requested
        if args.trello:
            return process_all_prompt_directories_trello(args)

        # Route based on mode
        # if args.mode == "i2i":
        #     # Run i2i mode
        #     return run_i2i_mode(args)
        
        # Otherwise run v2v mode
        # Process based on input mode
        # if args.prompt_dir:
        #     # Batch processing mode
        #     prompt_dir = Path(args.prompt_dir)
        #     if not prompt_dir.exists():
        #         logger.error(f"Directory not found: {prompt_dir}")
        #         return 1
            
        #     successful = process_prompt_directory(prompt_dir, args)
            
        #     if successful == 0:
        #         logger.error("No prompts were successfully processed")
        #         return 1
                
        else:
            # Single prompt mode
            prompt_file = Path(args.prompt_file)
            if not prompt_file.exists():
                logger.error(f"Prompt file not found: {prompt_file}")
                return 1
            
            # Parse the prompt file
            prompt_data = PromptFileParser.parse_prompt_file(prompt_file)
            if prompt_data is None:
                logger.error("Failed to parse prompt file")
                return 1
            
            # Generate promptName from filename
            promptName = prompt_file.stem
            
            logger.info(f"Processing: {prompt_data.video_name}")
            logger.info(f"Total frames: {prompt_data.total_frames}")
            
            # Calculate job sequence for preview
            job_planner = JobPlanner(promptName)
            render_jobs = job_planner.calculate_job_sequence(prompt_data)
            
            logger.info(f"Will create {len(render_jobs)} render job(s)")
            
            # Process the prompt
            if not process_single_prompt(prompt_data, promptName, args):
                logger.error("Failed to process prompt")
                return 1
        
        # Handle RunPod shutdown if requested
        if not args.no_shutdown:
            try:
                runpod = ServiceFactory.create_runpod_manager()
                runpod.shutdown_current_pod()
                logger.info("🔌 RunPod instance shutdown initiated")
            except Exception as e:
                logger.warning(f"Could not shutdown RunPod: {e}")
        
        logger.info("✅ All operations completed successfully")
        return 0
        
    except KeyboardInterrupt:
        logger.info("⚠️ Interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())