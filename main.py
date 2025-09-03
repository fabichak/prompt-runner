#!/usr/bin/env python3
"""
Prompt Runner - Main entry point
Video generation system using ComfyUI workflows
"""

import argparse
import logging
import sys
import uuid
from pathlib import Path
from datetime import datetime

# Set up config before other imports
import config
config.CLIENT_ID = str(uuid.uuid4())

from models.prompt_data import PromptData
from services.job_orchestrator import JobOrchestrator
from services.service_factory import ServiceFactory
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
    
    # Core arguments
    parser.add_argument(
        "prompt_file",
        nargs="?",
        help="Path to prompt text file (optional if using --prompt-dir)"
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
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.prompt_file and not args.prompt_dir:
        parser.error("Either prompt_file or --prompt-dir must be provided")
    
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
            resume_from_state=args.resume
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


def process_prompt_directory(prompt_dir: Path, args) -> int:
    """Process all prompt files in a directory
    
    Args:
        prompt_dir: Directory containing prompt files
        args: Command line arguments
        
    Returns:
        Number of successfully processed prompts
    """
    logger = logging.getLogger(__name__)
    
    # Find all .txt files in directory
    prompt_files = sorted(prompt_dir.glob("*.txt"))
    
    if not prompt_files:
        logger.warning(f"No prompt files found in {prompt_dir}")
        return 0
    
    logger.info(f"Found {len(prompt_files)} prompt files")
    
    # Apply start-at offset
    if args.start_at > 0:
        logger.info(f"Starting at prompt index {args.start_at}")
        prompt_files = prompt_files[args.start_at:]
    
    successful = 0
    failed = 0
    
    for idx, prompt_file in enumerate(prompt_files, start=args.start_at):
        logger.info("=" * 80)
        logger.info(f"Processing prompt {idx + 1}: {prompt_file.name}")
        logger.info("=" * 80)
        
        try:
            # Parse prompt file
            prompt_data = PromptFileParser.parse_prompt_file(Path(prompt_file))
            
            # Generate promptName from filename
            promptName = prompt_file.stem
            
            # Process the prompt
            if process_single_prompt(prompt_data, promptName, args):
                successful += 1
            else:
                failed += 1
                
        except Exception as e:
            logger.error(f"Failed to process {prompt_file}: {e}")
            failed += 1
    
    logger.info("=" * 80)
    logger.info(f"Batch processing complete: {successful} successful, {failed} failed")
    
    return successful


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
    
    try:
        # Process based on input mode
        if args.prompt_dir:
            # Batch processing mode
            prompt_dir = Path(args.prompt_dir)
            if not prompt_dir.exists():
                logger.error(f"Directory not found: {prompt_dir}")
                return 1
            
            successful = process_prompt_directory(prompt_dir, args)
            
            if successful == 0:
                logger.error("No prompts were successfully processed")
                return 1
                
        else:
            # Single prompt mode
            prompt_file = Path(args.prompt_file)
            if not prompt_file.exists():
                logger.error(f"Prompt file not found: {prompt_file}")
                return 1
            
            # Parse the prompt file
            parser = PromptFileParser(str(prompt_file))
            prompt_data = parser.parse()
            
            # Generate promptName from filename
            promptName = prompt_file.stem
            
            logger.info(f"Processing: {prompt_data.video_name}")
            logger.info(f"Total frames: {prompt_data.total_frames}")
            
            # Calculate job sequence for preview
            job_planner = JobPlanner(promptName)
            render_jobs, combine_jobs = job_planner.calculate_job_sequence(prompt_data)
            
            logger.info(f"Will create {len(render_jobs)} render jobs and {len(combine_jobs)} combine jobs")
            
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