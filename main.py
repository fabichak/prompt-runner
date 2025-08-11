#!/usr/bin/env python3
"""
Prompt Runner v2 - Main entry point
Complex video generation system with HIGH/LOW noise model alternation
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
from models.job import JobType
from services.job_orchestrator import JobOrchestrator
from services.service_factory import ServiceFactory
from services.dry_run_manager import enable_dry_run, dry_run_manager
from utils.file_parser import PromptFileParser
from utils.job_planner import JobPlanner


def setup_logging(log_level: str = "INFO", timestamp: str = None):
    """Set up logging configuration"""
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Determine log file location
    log_filename = f"prompt_runner_{timestamp}.log"
    
    # Use dry-run logs directory if in dry-run mode
    logs_dir = dry_run_manager.get_logs_directory()
    if logs_dir:
        log_filepath = logs_dir / log_filename
    else:
        log_filepath = Path(log_filename)
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(str(log_filepath))
        ]
    )


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Prompt Runner v2 - Complex video generation with Wan2.2 workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all prompt files in default directory
  python main.py
  
  # Process specific prompt file
  python main.py --prompt-file my_prompt.txt
  
  # Resume from saved state
  python main.py --resume video_name
  
  # Keep RunPod instance running after completion
  python main.py --no-shutdown
  
  # Process with custom frames per chunk
  python main.py --frames-per-chunk 150
        """
    )
    
    # Input options
    parser.add_argument(
        "--prompt-file",
        type=str,
        help="Specific prompt file to process (default: process all in prompt_files/)"
    )
    parser.add_argument(
        "--prompt-dir",
        type=str,
        default="prompt_files",
        help="Directory containing prompt files (default: prompt_files)"
    )
    
    # Execution options
    parser.add_argument(
        "--resume",
        type=str,
        metavar="VIDEO_NAME",
        help="Resume from saved state for given video name"
    )
    parser.add_argument(
        "--frames-per-chunk",
        type=int,
        default=config.FRAMES_TO_RENDER,
        help=f"Frames to render per chunk (default: {config.FRAMES_TO_RENDER})"
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=config.MAX_RETRIES,
        help=f"Maximum retries per job (default: {config.MAX_RETRIES})"
    )
    
    # Output options
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Custom output directory (default: /workspace/ComfyUI/output/prompt-runner)"
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="Skip GCS upload after completion"
    )
    parser.add_argument(
        "--keep-intermediate",
        action="store_true",
        help="Keep intermediate files after completion"
    )
    
    # RunPod options
    parser.add_argument(
        "--no-shutdown",
        action="store_true",
        default=config.DEFAULT_NO_SHUTDOWN,
        help="Do NOT shutdown RunPod instance after completion (default: don't shutdown)"
    )
    parser.add_argument(
        "--force-shutdown",
        action="store_true",
        help="Force shutdown RunPod instance after completion"
    )
    
    # Debug options
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan jobs without executing them"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate prompt files and workflows"
    )
    
    return parser.parse_args()


def process_single_prompt(prompt_data: PromptData, args, orchestrator: JobOrchestrator, promptName: str) -> bool:
    """Process a single prompt file"""
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 80)
    logger.info(f"NAME: {promptName}")
    logger.info(f"PROCESSING: {prompt_data.video_name}")
    logger.info(f"Total frames: {prompt_data.total_frames}")
    logger.info("=" * 80)
    
    # Update frames per chunk if specified
    if args.frames_per_chunk != config.FRAMES_TO_RENDER:
        config.FRAMES_TO_RENDER = args.frames_per_chunk
        orchestrator.job_planner.frames_per_chunk = args.frames_per_chunk
    
    logger.info(f"Frames per chunk: {config.FRAMES_TO_RENDER}")

    # Plan jobs
    planner = JobPlanner(promptName, frames_per_chunk=args.frames_per_chunk)
    
    if args.dry_run:
        render_jobs, combine_jobs = planner.calculate_job_sequence(prompt_data)
        
        # Save job plans to temp folder
        dry_run_manager.save_job_plan("render", render_jobs, {
            "video_name": prompt_data.video_name,
            "total_frames": prompt_data.total_frames,
            "frames_per_chunk": args.frames_per_chunk
        })
        
        dry_run_manager.save_job_plan("combine", combine_jobs, {
            "video_name": prompt_data.video_name,
            "total_combines": len(combine_jobs)
        })
        
        # Generate workflows for dry-run analysis
        logger.info("🔧 Generating workflows for dry-run analysis...")
        workflow_manager = ServiceFactory.create_workflow_manager(
            Path("prompt.json"), 
            Path("combine.json")
        )
        
        # Generate render job workflows
        for job in render_jobs:
            try:
                if job.job_type == JobType.HIGH:
                    workflow_manager.modify_for_high_job(job)
                else:
                    workflow_manager.modify_for_low_job(job)
            except Exception as e:
                logger.warning(f"Could not generate workflow for job {job.job_number}: {e}")
        
        # Generate combine job workflows  
        for job in combine_jobs:
            try:
                workflow_manager.create_combine_workflow(job)
            except Exception as e:
                logger.warning(f"Could not generate combine workflow for job {job.combine_number}: {e}")
        
        logger.info("🎭 DRY RUN - Jobs planned but not executed")
        logger.info(f"📊 Render jobs: {len(render_jobs)}, Combine jobs: {len(combine_jobs)}")
        return True
    
    # Execute pipeline
    success = orchestrator.execute_full_pipeline(
        prompt_data,
        promptName,
        resume_from_state=args.resume
    )
    
    if success:
        logger.info(f"✅ Successfully processed {prompt_data.video_name}")
        
        # Upload to GCS if requested
        if not args.no_upload:
            storage = ServiceFactory.create_storage_manager()
            upload_success = storage.zip_and_upload_output(promptName, prompt_data.video_name)
            if upload_success:
                logger.info(f"✅ Uploaded {prompt_data.video_name} to GCS")
            else:
                logger.warning(f"⚠️ Failed to upload {prompt_data.video_name} to GCS")
        
        # Clean up if requested
        if not args.keep_intermediate:
            storage = ServiceFactory.create_storage_manager()
            storage.cleanup_intermediate_files(promptName, prompt_data.video_name, keep_final=True)
            logger.info("Cleaned up intermediate files")
    else:
        logger.error(f"❌ Failed to process {prompt_data.video_name}")
    
    return success


def main():
    """Main entry point"""
    args = parse_arguments()
    
    # Enable dry-run mode if requested (before logging setup)
    if args.dry_run:
        enable_dry_run()
    
    # Setup logging (after dry-run mode is potentially enabled)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    setup_logging(args.log_level, timestamp)
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 80)
    logger.info("PROMPT RUNNER V2 - Starting")
    logger.info(f"Client ID: {config.CLIENT_ID}")
    logger.info("=" * 80)
    
    if args.dry_run:
        logger.info("🎭 DRY-RUN MODE ENABLED")
    
    # Show RunPod info if available
    runpod = ServiceFactory.create_runpod_manager()
    runpod_info = runpod.get_instance_info()
    if runpod_info['pod_id'] != 'N/A':
        logger.info(f"RunPod Instance: {runpod_info}")
    
    # Check system health
    if not runpod.check_instance_health():
        logger.warning("System health check failed - continuing anyway")
    
    # Set up storage
    storage = ServiceFactory.create_storage_manager()
    
    # Check disk space (using a temp prompt name for global check)
    temp_prompt = "_global_check"
    if not storage.check_disk_space(temp_prompt, required_gb=10.0):
        logger.error("Insufficient disk space")
        sys.exit(1)
    
    # Handle resume mode
    if args.resume:
        logger.info(f"Resuming from state: {args.resume}")
        # Load state will be handled in orchestrator
    
    # Get prompt files to process
    prompt_files = []
    
    if args.prompt_file:
        # Process specific file
        prompt_path = Path(args.prompt_file)
        prompt_data = PromptFileParser.parse_prompt_file(prompt_path)
        if prompt_data:
            prompt_files.append((prompt_path, prompt_data))
        else:
            logger.error(f"Failed to parse prompt file: {prompt_path}")
            sys.exit(1)
    else:
        # Process all files in directory
        prompt_dir = Path(args.prompt_dir)
        prompt_files = PromptFileParser.validate_prompt_directory(prompt_dir)
        
        if not prompt_files:
            logger.error(f"No valid prompt files found in {prompt_dir}")
            sys.exit(1)
    
    logger.info(f"Found {len(prompt_files)} prompt file(s) to process")
    
    # Validate only mode
    if args.validate_only:
        logger.info("Validation complete - exiting (--validate-only)")
        sys.exit(0)
    
    # Create orchestrator
    orchestrator = JobOrchestrator()
    
    # Process each prompt file
    total_success = 0
    total_failed = 0
    
    for prompt_path, prompt_data in prompt_files:
        try:
            logger.info(f"\nProcessing: {prompt_path}")
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            success = process_single_prompt(prompt_data, args, orchestrator, timestamp)
            
            if success:
                total_success += 1
            else:
                total_failed += 1
                
        except KeyboardInterrupt:
            logger.warning("Interrupted by user")
            break
        except Exception as e:
            logger.error(f"Error processing {prompt_path}: {e}")
            total_failed += 1
    
    # Final summary
    logger.info("=" * 80)
    logger.info("PROMPT RUNNER V2 - Complete")
    logger.info(f"Successful: {total_success}")
    logger.info(f"Failed: {total_failed}")
    logger.info("=" * 80)
    
    # Show disk usage across all prompts
    # Note: This now shows usage for the last processed prompt only
    # TODO: Consider adding a method to get total disk usage across all prompts
    if 'timestamp' in locals():
        disk_usage = storage.get_disk_usage(timestamp)
        logger.info(f"Disk usage for last prompt: {disk_usage}")
    else:
        logger.info("No disk usage to report (no prompts processed)")
    
    # Show dry-run summary if applicable
    if args.dry_run:
        summary = dry_run_manager.get_summary()
        logger.info("=" * 80)
        logger.info("DRY-RUN SUMMARY")
        logger.info("=" * 80)
        logger.info(f"🗂️ Temp directory: {summary.get('temp_directory', 'N/A')}")
        logger.info(f"📄 Workflows generated: {summary.get('workflows_generated', 0)}")
        
        if hasattr(storage, 'get_simulation_summary'):
            sim_summary = storage.get_simulation_summary()
            logger.info(f"☁️ Simulated GCS uploads: {sim_summary.get('total_uploads', 0)}")
            logger.info(f"📁 Simulated file copies: {sim_summary.get('total_copies', 0)}")
        
        logger.info("=" * 80)
        dry_run_manager.cleanup()
    
    # Handle RunPod shutdown
    if args.force_shutdown:
        logger.info("Force shutdown requested")
        runpod.shutdown_instance(force=True)
    elif not args.no_shutdown and total_failed == 0:
        logger.info("All jobs completed successfully - considering shutdown")
        # Only shutdown if explicitly requested with force
        if args.force_shutdown:
            runpod.shutdown_instance(force=True)
    else:
        logger.info("RunPod instance will remain running")
    
    # Exit with appropriate code
    if total_failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()