"""Job orchestration engine for executing render and combine jobs"""
import logging
from pathlib import Path
from typing import List, Optional

from models.job import RenderJob, JobStatus
from models.job_result import JobResult
from models.prompt_data import PromptData
from services.service_factory import ServiceFactory
from utils.job_planner import JobPlanner
from config import (
    JSON_WORKFLOW_FILE, COMBINE_WORKFLOW_FILE, SERVER_ADDRESS
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
        
        # Track execution state
        self.completed_jobs = []
        self.failed_jobs = []
    
    def execute_full_pipeline(self, prompt_data: PromptData, promptName: str, resume_from_state: Optional[str] = None, dry_run: bool = False) -> bool:
        """Execute the complete rendering pipeline for a prompt
        
        Args:
            prompt_data: The prompt data to process
            promptName: Name/identifier for organizing this prompt's files
            resume_from_state: Optional state file to resume from
            dry_run: If True, skip ComfyUI execution and only generate workflows
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Store promptName for use in storage operations
            self.current_prompt_name = promptName
            self.completed_jobs = []
            self.failed_jobs = []

            # Connect to ComfyUI unless dry-run
            if not dry_run:
                if not self.comfyui_client.connect():
                    logger.error("Failed to connect to ComfyUI")
                    return False
                        
            # Ensure prompt directories exist
            self.storage.ensure_directories(promptName)
            
            # Create job planner for this prompt
            job_planner = JobPlanner(promptName)
            
            # Plan jobs
            render_jobs = job_planner.calculate_job_sequence(prompt_data)
            # DRY RUN: Only generate and save workflows
            if dry_run:
                logger.info("DRY RUN: Generating workflows only; no ComfyUI connection or execution")
                for job in render_jobs:
                    self.workflow_manager.modify_workflow_for_job(job)
                    logger.info(f"DRY RUN: Saved workflow for job {job.job_number}")
                logger.info("DRY RUN: Completed workflow generation")
                return True
                        
            # Execute render jobs
            logger.info("=" * 60)
            logger.info("STARTING RENDER JOB")
            logger.info("=" * 60)
            
            render_results = self.execute_render_jobs(render_jobs)
            
            if not all(r.success for r in render_results):
                logger.error("Some render jobs failed")
                return False
            
            # # Execute combine jobs
            # logger.info("=" * 60)
            # logger.info("STARTING COMBINE JOBS")
            # logger.info("=" * 60)
            
            # combine_results = self.execute_combine_jobs(combine_jobs)
            
            # if not all(r.success for r in combine_results):
            #     logger.error("Some combine jobs failed")
            #     return False
                                    
            logger.info(f"✅ Successfully completed pipeline for {prompt_data.video_name}")

            # Collect outputs for the last render (optional)
            try:
                if render_results:
                    # get history of the last prompt
                    # Note: execute_single_render_job currently does not return prompt_id; we could extend it
                    pass
            except Exception:
                pass
            return True
                        
        except Exception as e:
            logger.error(f"Pipeline execution error: {e}")
            return False
        finally:
            self.comfyui_client.disconnect()
    
    def execute_render_jobs(self, jobs: List[RenderJob]) -> List[JobResult]:
        """Execute all render jobs in sequence"""
        results = []
        
        for job in jobs:           
            logger.info(f"\nExecuting {job.job_id}")
            logger.info("-" * 40)
            
            result = self.execute_single_render_job(job)
            results.append(result)
            
            if result.success:
                self.completed_jobs.append(job.job_number)
                job.status = JobStatus.COMPLETED
            else:
                self.failed_jobs.append(job.job_number)
                job.status = JobStatus.FAILED
                                
                # if job.retry_count >= MAX_RETRIES:
                #     logger.error(f"Job {job.job_number} failed after {MAX_RETRIES} retries")
                #     break
        
        return results
    
    def execute_single_render_job(self, job: RenderJob) -> JobResult:
        """Execute a single render job"""
        result = JobResult(
            job_id=job.job_id,
            job_type="render"
        )
        
        try:
            logger.info(f"🔍 Processing job {job.job_number}")
            
            # Modify workflow for the job using prompt.json
            workflow = self.workflow_manager.modify_workflow_for_job(job)
            
            # Execute workflow with retry
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