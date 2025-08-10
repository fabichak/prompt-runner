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
from services.comfyui_client import ComfyUIClient
from services.workflow_manager import WorkflowManager
from services.storage_utils import StorageManager
from utils.job_planner import JobPlanner
from config import (
    NODE_VIDEO_OUTPUT, REFERENCE_FRAME_OFFSET, MAX_RETRIES,
    RETRY_DELAY, JSON_WORKFLOW_FILE, COMBINE_WORKFLOW_FILE
)

logger = logging.getLogger(__name__)


class JobOrchestrator:
    """Orchestrates execution of render and combine jobs"""
    
    def __init__(self):
        self.comfyui_client = ComfyUIClient()
        self.storage = StorageManager()
        self.workflow_manager = WorkflowManager(
            Path(JSON_WORKFLOW_FILE),
            Path(COMBINE_WORKFLOW_FILE)
        )
        self.job_planner = JobPlanner()
        
        # Track execution state
        self.completed_jobs = []
        self.failed_jobs = []
        self.current_state = {}
    
    def execute_full_pipeline(self, prompt_data: PromptData, resume_from_state: Optional[str] = None) -> bool:
        """Execute the complete rendering pipeline for a prompt
        
        Args:
            prompt_data: The prompt data to process
            resume_from_state: Optional state file to resume from
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Connect to ComfyUI
            if not self.comfyui_client.connect():
                logger.error("Failed to connect to ComfyUI")
                return False
            
            # Load or create execution state
            if resume_from_state:
                state = self.storage.load_state(resume_from_state)
                if state:
                    self.restore_state(state)
                    logger.info(f"Resumed from state: {resume_from_state}")
            
            # Plan jobs
            render_jobs, combine_jobs = self.job_planner.calculate_job_sequence(prompt_data)
            
            # Validate job sequence
            if not self.job_planner.validate_job_sequence(render_jobs, prompt_data.total_frames):
                logger.error("Invalid job sequence")
                return False
            
            # Execute render jobs
            logger.info("=" * 60)
            logger.info("STARTING RENDER JOBS")
            logger.info("=" * 60)
            
            render_results = self.execute_render_jobs(prompt_data, render_jobs)
            
            if not all(r.success for r in render_results):
                logger.error("Some render jobs failed")
                self.save_state(prompt_data.video_name)
                return False
            
            # Execute combine jobs
            logger.info("=" * 60)
            logger.info("STARTING COMBINE JOBS")
            logger.info("=" * 60)
            
            combine_results = self.execute_combine_jobs(combine_jobs)
            
            if not all(r.success for r in combine_results):
                logger.error("Some combine jobs failed")
                self.save_state(prompt_data.video_name)
                return False
            
            # Create final output
            final_success = self.create_final_output(prompt_data.video_name, combine_jobs)
            
            if final_success:
                # Clean up intermediate files
                logger.info("Cleaning up intermediate files...")
                self.storage.cleanup_intermediate_files(prompt_data.video_name, keep_final=True)
                
                # Clear saved state
                self.storage.clear_state(prompt_data.video_name)
                
                logger.info(f"✅ Successfully completed pipeline for {prompt_data.video_name}")
                return True
            else:
                logger.error("Failed to create final output")
                return False
                
        except Exception as e:
            logger.error(f"Pipeline execution error: {e}")
            self.save_state(prompt_data.video_name)
            return False
        finally:
            self.comfyui_client.disconnect()
    
    def execute_render_jobs(self, prompt_data: PromptData, jobs: List[RenderJob]) -> List[JobResult]:
        """Execute all render jobs in sequence"""
        results = []
        
        for job in jobs:
            # Check dependencies
            if not self.job_planner.can_job_run(job, self.completed_jobs):
                logger.warning(f"Skipping {job} - dependencies not met")
                job.status = JobStatus.SKIPPED
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
                if job.job_type == JobType.LOW and job.job_number >= 2:
                    ref_success = self.extract_reference_image(job)
                    if not ref_success:
                        logger.warning(f"Failed to extract reference image for job {job.job_number}")
            else:
                self.failed_jobs.append(job.job_number)
                job.status = JobStatus.FAILED
                
                # Save state on failure
                self.save_state(prompt_data.video_name)
                
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
            # Modify workflow based on job type
            if job.job_type == JobType.HIGH:
                workflow = self.workflow_manager.modify_for_high_job(job)
            else:
                workflow = self.workflow_manager.modify_for_low_job(job)
            
            # Execute workflow with retry
            success, prompt_id, error = self.comfyui_client.execute_with_retry(workflow)
            
            if success:
                # Wait for outputs to be written
                time.sleep(2)
                
                # Copy outputs to our directory structure
                if job.job_type == JobType.HIGH:
                    # Save latent output
                    latent_path = self.storage.get_latent_path(job.video_name, job.job_number)
                    # Note: You'll need to adjust this based on how ComfyUI saves latents
                    comfyui_output = Path(f"/workspace/ComfyUI/output/latent_{prompt_id}.safetensors")
                    if self.storage.copy_from_comfyui_output(comfyui_output, latent_path):
                        result.latent_path = str(latent_path)
                        job.latent_output_path = str(latent_path)
                else:
                    # Save video output
                    video_path = self.storage.get_video_path(job.video_name, job.job_number)
                    # Note: Adjust based on actual ComfyUI output naming
                    comfyui_output = Path(f"/workspace/ComfyUI/output/{prompt_id}.mp4")
                    if self.storage.copy_from_comfyui_output(comfyui_output, video_path):
                        result.output_path = str(video_path)
                        job.video_output_path = str(video_path)
                
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
    
    def execute_combine_jobs(self, jobs: List[CombineJob]) -> List[JobResult]:
        """Execute all combine jobs in sequence"""
        results = []
        
        for job in jobs:
            logger.info(f"\nExecuting {job}")
            logger.info("-" * 40)
            
            result = self.execute_single_combine_job(job)
            results.append(result)
            
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
                # Wait for output
                time.sleep(2)
                
                # Copy combined output
                combined_path = self.storage.get_combined_path(job.video_name, job.combine_number)
                comfyui_output = Path(f"/workspace/ComfyUI/output/combined_{prompt_id}.mp4")
                
                if self.storage.copy_from_comfyui_output(comfyui_output, combined_path):
                    result.output_path = str(combined_path)
                    job.output_path = str(combined_path)
                    result.complete(True)
                    logger.info(f"✓ Combine job {job.combine_number} completed")
                else:
                    result.complete(False, "Failed to copy output")
            else:
                result.complete(False, error)
                logger.error(f"✗ Combine job {job.combine_number} failed: {error}")
                job.retry_count += 1
                
        except Exception as e:
            result.complete(False, str(e))
            logger.error(f"✗ Combine job {job.combine_number} exception: {e}")
            job.retry_count += 1
        
        return result
    
    def extract_reference_image(self, job: RenderJob) -> bool:
        """Extract reference image from video output
        
        Extracts frame at position (frames_to_render - 10) from the video
        """
        try:
            if not job.video_output_path:
                logger.error("No video output path for reference extraction")
                return False
            
            video_path = Path(job.video_output_path)
            if not video_path.exists():
                # Try in ComfyUI output directory
                video_path = Path(f"/workspace/ComfyUI/output") / video_path.name
                if not video_path.exists():
                    logger.error(f"Video not found: {video_path}")
                    return False
            
            # Calculate frame number to extract
            frame_num = self.job_planner.calculate_reference_frame(job.frames_to_render)
            
            # Get reference image path
            ref_path = self.storage.get_reference_path(job.video_name, job.job_number)
            
            # Use ffmpeg to extract frame
            cmd = [
                "ffmpeg",
                "-i", str(video_path),
                "-vf", f"select=eq(n\\,{frame_num})",
                "-vframes", "1",
                "-y",  # Overwrite if exists
                str(ref_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0 and ref_path.exists():
                logger.info(f"Extracted reference frame {frame_num} to {ref_path}")
                return True
            else:
                logger.error(f"Failed to extract reference: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error extracting reference image: {e}")
            return False
    
    def create_final_output(self, video_name: str, combine_jobs: List[CombineJob]) -> bool:
        """Create final output video from last combined video"""
        try:
            if not combine_jobs:
                logger.error("No combine jobs to create final output")
                return False
            
            # Get the last combined video
            last_combine = combine_jobs[-1]
            last_combined_path = Path(last_combine.output_path)
            
            if not last_combined_path.exists():
                # Try in ComfyUI output
                last_combined_path = Path(f"/workspace/ComfyUI/output") / last_combined_path.name
                if not last_combined_path.exists():
                    logger.error(f"Last combined video not found: {last_combined_path}")
                    return False
            
            # Copy to final output
            final_path = self.storage.get_final_path(video_name)
            shutil.copy2(last_combined_path, final_path)
            
            logger.info(f"Created final output: {final_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating final output: {e}")
            return False
    
    def save_state(self, video_name: str):
        """Save current execution state for recovery"""
        state = {
            'video_name': video_name,
            'completed_jobs': self.completed_jobs,
            'failed_jobs': self.failed_jobs,
            'timestamp': datetime.now().isoformat()
        }
        self.storage.save_state(video_name, state)
    
    def restore_state(self, state: Dict[str, Any]):
        """Restore execution state from saved data"""
        self.completed_jobs = state.get('completed_jobs', [])
        self.failed_jobs = state.get('failed_jobs', [])
        logger.info(f"Restored state: {len(self.completed_jobs)} completed, {len(self.failed_jobs)} failed")