"""Job orchestration engine for executing render and combine jobs"""
import json
import logging
import time
import subprocess
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from models.job import RenderJob, CombineJob, JobType, JobStatus
from models.job_result import JobResult
from models.prompt_data import PromptData
from services.service_factory import ServiceFactory
from services.dry_run_manager import is_dry_run, dry_run_manager
from utils.job_planner import JobPlanner
from config import (
    FRAMES_TO_RENDER, REFERENCE_FRAME_OFFSET, MAX_RETRIES,
    RETRY_DELAY, JSON_WORKFLOW_FILE, COMBINE_WORKFLOW_FILE, SERVER_ADDRESS, START_FRAME_OFFSET
)

logger = logging.getLogger(__name__)


class JobOrchestrator:
    """Orchestrates execution of render and combine jobs"""
    
    def __init__(self):
        self.comfyui_client = ServiceFactory.create_comfyui_client(SERVER_ADDRESS)
        self.storage = ServiceFactory.create_storage_manager()
        self.workflow_manager = ServiceFactory.create_workflow_manager(
            Path(JSON_WORKFLOW_FILE),
            Path(COMBINE_WORKFLOW_FILE)
        )
        # job_planner will be created per-prompt with promptName
        
        # Track execution state
        self.completed_jobs = []
        self.failed_jobs = []
        self.current_state = {}
        self.last_combine_job = 0
    
    def execute_full_pipeline(self, prompt_data: PromptData, promptName: str, resume_from_state: Optional[str] = None) -> bool:
        """Execute the complete rendering pipeline for a prompt
        
        Args:
            prompt_data: The prompt data to process
            promptName: Name/identifier for organizing this prompt's files
            resume_from_state: Optional state file to resume from
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Store promptName for use in storage operations
            self.current_prompt_name = promptName
            
            # Set video name for dry-run organized storage
            if is_dry_run():
                dry_run_manager.set_current_video_name(prompt_data.video_name)
            
            # Connect to ComfyUI
            if not self.comfyui_client.connect():
                logger.error("Failed to connect to ComfyUI")
                return False
            
            # Load or create execution state
            if resume_from_state:
                self.current_prompt_name = resume_from_state
                # state = self.storage.load_state(promptName, resume_from_state)
                # if state:
                #     self.restore_state(state)
                #     logger.info(f"Resumed from state: {resume_from_state}")
            
            # Ensure prompt directories exist
            self.storage.ensure_directories(promptName)
            
            # Create job planner for this prompt
            job_planner = JobPlanner(promptName)
            
            # Plan jobs
            render_jobs, combine_jobs = job_planner.calculate_job_sequence(prompt_data)
            
            # Validate job sequence
            if not job_planner.validate_job_sequence(render_jobs, prompt_data.total_frames):
                logger.error("Invalid job sequence")
                return False
            
            # Execute render jobs
            logger.info("=" * 60)
            logger.info("STARTING RENDER JOBS")
            logger.info("=" * 60)
            
            render_results = self.execute_render_jobs(prompt_data, render_jobs, prompt_data.total_frames)
            
            if not all(r.success for r in render_results):
                logger.error("Some render jobs failed")
                self.save_state()
                return False
            
            # Execute combine jobs
            logger.info("=" * 60)
            logger.info("STARTING COMBINE JOBS")
            logger.info("=" * 60)
            
            combine_results = self.execute_combine_jobs(combine_jobs)
            
            if not all(r.success for r in combine_results):
                logger.error("Some combine jobs failed")
                self.save_state()
                return False
                                    
            logger.info(f"✅ Successfully completed pipeline for {prompt_data.video_name}")
            return True
                        
        except Exception as e:
            logger.error(f"Pipeline execution error: {e}")
            self.save_state()
            return False
        finally:
            self.comfyui_client.disconnect()
    
    def execute_render_jobs(self, prompt_data: PromptData, jobs: List[RenderJob], total_frames: int) -> List[JobResult]:
        """Execute all render jobs in sequence"""
        results = []
        
        for job in jobs:
            # Check dependencies  
            # Note: For now, run jobs in sequence. Dependencies handled by job ordering.
            if job.status == JobStatus.SKIPPED:
                logger.warning(f"Skipping {job} - already marked as skipped")
                continue
            
            # Skip if already completed (for resume)
            if job.job_number in self.completed_jobs:
                logger.info(f"Skipping {job} - already completed")
                continue
            
            logger.info(f"\nExecuting {job}")
            logger.info("-" * 40)
            
            result = self.execute_single_render_job(job)
            results.append(result)
            
            if result.success:
                self.completed_jobs.append(job.job_number)
                job.status = JobStatus.COMPLETED
                
                # Extract reference image if this is a LOW job
                if job.job_type == JobType.LOW:
                    ref_success, frames_rendered = self.extract_reference_image(job)
                    job.frames_rendered = frames_rendered
                    
                    logger.debug("|" * 60)
                    for job_to_change in jobs:   
                        logger.debug(f"\job {job_to_change.job_number} start-frame {job_to_change.start_frame} frames-to-render {job_to_change.frames_to_render}, total {total_frames}")
                    logger.debug("|" * 60)
                    # Calculate remaining frames for subsequent jobs
                    start_frame = 0
                    for job_to_change in jobs:
                        remaining_frames = (total_frames - start_frame)
                        chunk_frames = min(FRAMES_TO_RENDER, remaining_frames)
                        if job_to_change.job_type == JobType.LOW:
                            if job_to_change.job_number <= job.job_number:
                                start_frame += job_to_change.frames_rendered
                        if job_to_change.job_number > job.job_number:
                            job_to_change.start_frame = start_frame - START_FRAME_OFFSET
                            job_to_change.frames_to_render = chunk_frames
                            if job_to_change.job_type == JobType.LOW:
                                start_frame += (chunk_frames - START_FRAME_OFFSET)
                    
                    for job_to_change in jobs:   
                        logger.debug(f"\job {job_to_change.job_number} start-frame {job_to_change.start_frame} frames-to-render {job_to_change.frames_to_render}")
                    logger.debug("|" * 60)
                    if not ref_success:
                        logger.error(f"Failed to extract reference image for job {job.job_number}")
            else:
                self.failed_jobs.append(job.job_number)
                job.status = JobStatus.FAILED
                
                # Save state on failure
                self.save_state()
                
                if job.retry_count >= MAX_RETRIES:
                    logger.error(f"Job {job.job_number} failed after {MAX_RETRIES} retries")
                    break
        
        return results
    
    def execute_single_render_job(self, job: RenderJob) -> JobResult:
        """Execute a single render job"""
        result = JobResult(
            job_id=job.job_id,
            job_type="render"
        )
        
        try:
            # Debug logging to understand the job type issue
            logger.info(f"🔍 Processing job {job.job_number}: job_type={job.job_type}, type={type(job.job_type)}")
            
            # Modify workflow based on job type
            if job.job_type == JobType.HIGH:
                logger.info(f"🔵 Calling modify_for_high_job for job {job.job_number}")
                workflow = self.workflow_manager.modify_for_high_job(job)
            else:
                logger.info(f"🟡 Calling modify_for_low_job for job {job.job_number}")
                workflow = self.workflow_manager.modify_for_low_job(job)
            
            # Execute workflow with retry
            success = True
            if job.job_type == JobType.LOW:
                success, prompt_id, error = self.comfyui_client.execute_with_retry(workflow)
            
            if success:
                result.complete(True)
                logger.info(f"✓ Job {job.job_number} completed successfully")
            else:
                result.complete(False, error)
                logger.error(f"✗ Job {job.job_number} failed: {error}")
                job.retry_count += 1
                
        except Exception as e:
            result.complete(False, str(e))
            logger.error(f"✗ Job {job.job_number} exception: {e}")
            job.retry_count += 1
        
        return result
    
    def get_last_combine_job(self) -> int:
        return self.last_combine_job
    
    def execute_combine_jobs(self, jobs: List[CombineJob]) -> List[JobResult]:
        """Execute all combine jobs in sequence"""
        results = []
        
        for job in jobs:
            logger.info(f"\nExecuting {job}")
            logger.info("-" * 40)
            
            result = self.execute_single_combine_job(job)
            results.append(result)
            
            self.last_combine_job = job.combine_number
            if result.success:
                job.status = JobStatus.COMPLETED
            else:
                job.status = JobStatus.FAILED
                if job.retry_count >= MAX_RETRIES:
                    logger.error(f"Combine job {job.combine_number} failed after {MAX_RETRIES} retries")
                    break
        
        return results
    
    def execute_single_combine_job(self, job: CombineJob) -> JobResult:
        """Execute a single combine job"""
        result = JobResult(
            job_id=job.job_id,
            job_type="combine"
        )
        
        try:
            # Create combine workflow
            workflow = self.workflow_manager.create_combine_workflow(job)
            
            # Execute workflow with retry
            success, prompt_id, error = self.comfyui_client.execute_with_retry(workflow)
            
            if success:
                result.complete(True)
                logger.info(f"✓ Combine job {job.combine_number} completed")
                logger.info(f"✓ Combine job {job.output_path} completed")
            else:
                result.complete(False, error)
                logger.error(f"✗ Combine job {job.combine_number} failed: {error}")
                job.retry_count += 1
                
        except Exception as e:
            result.complete(False, str(e))
            logger.error(f"✗ exception Combine job {job.combine_number} exception: {e}")
            job.retry_count += 1
        
        return result
    
    def extract_reference_image(self, job: RenderJob) -> Tuple[bool, int]:
        """Extract reference image from video output
        
        Extracts frame at position (frames_to_render - 10) from the video
        """
        try:
            if not job.video_output_path:
                logger.error("No video output path for reference extraction")
                return False, 0
            
            video_path = Path(job.video_output_full_path)
            if not video_path.exists():
                logger.error(f"Video not found: {video_path}")
                return False, 0
            
            
            # Get reference image path
            ref_path = self.storage.get_reference_path(self.current_prompt_name, job.job_number)
            
            # Handle dry-run mode
            if is_dry_run():
                # Simulate ffmpeg extraction
                ref_path.parent.mkdir(parents=True, exist_ok=True)
                frame_num = job.frames_to_render - REFERENCE_FRAME_OFFSET
                with open(ref_path, 'w') as f:
                    f.write(f"# DRY-RUN SIMULATED REFERENCE IMAGE\n")
                    f.write(f"# Extracted from: {video_path}\n")
                    f.write(f"# Frame number: {frame_num}\n")
                    f.write(f"# Job: {job.job_number}\n")
                    f.write(f"# Created at: {datetime.now().isoformat()}\n")
                
                logger.info(f"🖼️ [DRY-RUN] Simulated extracting reference frame {frame_num} to {ref_path}")
                return True, job.frames_to_render
            
            cmd = [
                "ffprobe",
                "-v", "error",
                "-count_frames",
                "-select_streams", "v:0",
                "-show_entries", "stream=nb_read_frames",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            try:
                frames_rendered = int(result.stdout.strip())
                logger.info(f"Frames rendered for {job.video_output_full_path}: {frames_rendered}")
                return True, frames_rendered
            except ValueError:
                logger.error(f"Failed to parse frame count from ffprobe. stdout: '{result.stdout.strip()}', stderr: '{result.stderr}'")
                return False, 0

            # # # Calculate frame number to extract (frames_to_render - 10)
            # # frame_num = max(1, frames_rendered - REFERENCE_FRAME_OFFSET)

            # # # Use ffmpeg to extract frame
            # # cmd = [
            # #     "ffmpeg",
            # #     "-i", str(video_path),
            # #     "-vf", f"select=eq(n\\,{frame_num})",
            # #     "-vframes", "1",
            # #     "-y",  # Overwrite if exists
            # #     str(ref_path)
            # # ]
            
            # # result = subprocess.run(cmd, capture_output=True, text=True)
            
            # if result.returncode == 0 and ref_path.exists():
            #     logger.info(f"Extracted reference frame {frame_num} to {ref_path}")
            #     return True, frames_rendered
            # else:
            #     logger.error(f"Failed to extract reference: {result.stderr}")
            #     return False, 0
                
        except Exception as e:
            logger.error(f"Error extracting reference image: {e}")
            return False, 0
       
    def save_state(self):
        """Save current execution state for recovery"""
        state = {
            'prompt_name': self.current_prompt_name,
            'completed_jobs': self.completed_jobs,
            'failed_jobs': self.failed_jobs,
            'timestamp': datetime.now().isoformat()
        }
        self.storage.save_state(self.current_prompt_name, state)
    
    def restore_state(self, state: Dict[str, Any]):
        """Restore execution state from saved data"""
        self.completed_jobs = state.get('completed_jobs', [])
        self.failed_jobs = state.get('failed_jobs', [])
        logger.info(f"Restored state: {len(self.completed_jobs)} completed, {len(self.failed_jobs)} failed")