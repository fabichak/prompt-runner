"""
Dual Instance Orchestrator
Coordinates job execution across two ComfyUI instances with intelligent scheduling
"""
import logging
import time
import threading
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from typing import List, Dict, Optional, Tuple
from pathlib import Path

from models.job import RenderJob, CombineJob, JobType, JobStatus
from models.job_result import JobResult
from models.prompt_data import PromptData
from models.dual_instance import ComfyUIInstanceConfig, InstanceStatus
from services.job_queue_manager import JobQueueManager
from services.multi_instance_client import MultiInstanceComfyUIClient
from services.workflow_manager import WorkflowManager
from services.service_factory import ServiceFactory
from utils.job_planner import JobPlanner
from config import (
    JSON_WORKFLOW_FILE, COMBINE_WORKFLOW_FILE, 
    ENABLE_DUAL_INSTANCE, COMFYUI_INSTANCES, SINGLE_INSTANCE_CONFIG,
    MAX_RETRIES, RETRY_DELAY
)

logger = logging.getLogger(__name__)


class DualInstanceOrchestrator:
    """
    Orchestrates job execution across dual ComfyUI instances
    
    Features:
    - Parallel execution of HIGH jobs on instance 1, LOW jobs on instance 2
    - Intelligent job interleaving across prompts to maximize utilization
    - Synchronization logic to postpone COMBINE jobs until HIGH/LOW completion
    - Automatic fallback to single instance mode if dual mode fails
    - Comprehensive error handling and recovery
    """
    
    def __init__(self):
        self.setup_instances()
        
        # Initialize workflow manager
        self.workflow_manager = ServiceFactory.create_workflow_manager(
            Path(JSON_WORKFLOW_FILE),
            Path(COMBINE_WORKFLOW_FILE)
        )
        
        # Initialize storage manager
        self.storage = ServiceFactory.create_storage_manager()
        
        # Execution tracking
        self.completed_jobs = []
        self.failed_jobs = []
        self.current_state = {}
        self.shutdown_requested = threading.Event()
        
        logger.info("DualInstanceOrchestrator initialized")
    
    def setup_instances(self):
        """Setup ComfyUI instances based on configuration"""
        if ENABLE_DUAL_INSTANCE and len(COMFYUI_INSTANCES) >= 2:
            # Dual instance mode
            self.dual_mode = True
            configs = [ComfyUIInstanceConfig.from_dict(cfg) for cfg in COMFYUI_INSTANCES]
            
            # Filter enabled instances
            enabled_configs = [cfg for cfg in configs if cfg.enabled]
            
            if len(enabled_configs) < 2:
                logger.warning("Less than 2 enabled instances, falling back to single mode")
                self.dual_mode = False
                configs = [ComfyUIInstanceConfig.from_dict(SINGLE_INSTANCE_CONFIG)]
            else:
                configs = enabled_configs[:2]  # Use first 2 enabled instances
                
        else:
            # Single instance mode
            self.dual_mode = False
            configs = [ComfyUIInstanceConfig.from_dict(SINGLE_INSTANCE_CONFIG)]
        
        self.instance_configs = configs
        self.queue_manager = JobQueueManager(configs)
        self.multi_client = MultiInstanceComfyUIClient(configs)
        
        mode_str = "dual" if self.dual_mode else "single"
        logger.info(f"Setup complete in {mode_str} instance mode with {len(configs)} instances")
    
    def execute_full_pipeline(self, prompt_data: PromptData, prompt_name: str, resume_from_state: Optional[str] = None) -> bool:
        """
        Execute the complete rendering pipeline for a single prompt
        
        Args:
            prompt_data: The prompt data to process
            prompt_name: Name/identifier for organizing this prompt's files
            resume_from_state: Optional state file to resume from
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.current_prompt_name = prompt_name
            
            # Connect to all instances
            connection_results = self.multi_client.connect_all()
            if not any(connection_results.values()):
                logger.error("Failed to connect to any ComfyUI instances")
                return False
            
            # Ensure prompt directories exist
            self.storage.ensure_directories(prompt_name)
            
            # Create job planner
            job_planner = JobPlanner(prompt_name)
            
            # Plan jobs
            render_jobs, combine_jobs = job_planner.calculate_job_sequence(prompt_data)
            
            # Validate job sequence
            if not job_planner.validate_job_sequence(render_jobs, prompt_data.total_frames):
                logger.error("Invalid job sequence")
                return False
            
            # Add jobs to queue manager
            self.queue_manager.add_jobs_for_prompt(render_jobs, combine_jobs, prompt_name)
            
            # Execute pipeline
            success = self._execute_pipeline(render_jobs, combine_jobs)
            
            if success:
                logger.info(f"✅ Successfully completed pipeline for {prompt_data.video_name}")
            else:
                logger.error(f"❌ Pipeline failed for {prompt_data.video_name}")
                self.save_state()
            
            return success
            
        except Exception as e:
            logger.error(f"Pipeline execution error: {e}")
            self.save_state()
            return False
        finally:
            self.multi_client.disconnect_all()
    
    def execute_multi_prompt_pipeline(self, prompt_data_list: List[Tuple[PromptData, str]]) -> bool:
        """
        Execute pipeline for multiple prompts with optimal job interleaving
        
        Args:
            prompt_data_list: List of (PromptData, prompt_name) tuples
            
        Returns:
            True if all prompts succeeded, False otherwise
        """
        try:
            logger.info(f"Starting multi-prompt pipeline with {len(prompt_data_list)} prompts")
            
            # Connect to all instances
            connection_results = self.multi_client.connect_all()
            if not any(connection_results.values()):
                logger.error("Failed to connect to any ComfyUI instances")
                return False
            
            # Plan and queue jobs for all prompts
            all_render_jobs = []
            all_combine_jobs = []
            
            for prompt_data, prompt_name in prompt_data_list:
                # Ensure directories exist
                self.storage.ensure_directories(prompt_name)
                
                # Plan jobs
                job_planner = JobPlanner(prompt_name)
                render_jobs, combine_jobs = job_planner.calculate_job_sequence(prompt_data)
                
                # Validate job sequence
                if not job_planner.validate_job_sequence(render_jobs, prompt_data.total_frames):
                    logger.error(f"Invalid job sequence for prompt {prompt_name}")
                    return False
                
                # Add to queue manager
                self.queue_manager.add_jobs_for_prompt(render_jobs, combine_jobs, prompt_name)
                
                all_render_jobs.extend(render_jobs)
                all_combine_jobs.extend(combine_jobs)
            
            # Execute pipeline with interleaved jobs
            success = self._execute_pipeline(all_render_jobs, all_combine_jobs)
            
            if success:
                logger.info(f"✅ Successfully completed multi-prompt pipeline")
            else:
                logger.error(f"❌ Multi-prompt pipeline failed")
                self.save_state()
            
            return success
            
        except Exception as e:
            logger.error(f"Multi-prompt pipeline error: {e}")
            self.save_state()
            return False
        finally:
            self.multi_client.disconnect_all()
    
    def _execute_pipeline(self, render_jobs: List[RenderJob], combine_jobs: List[CombineJob]) -> bool:
        """Execute the complete pipeline with render and combine phases"""
        
        # Phase 1: Execute render jobs in parallel
        logger.info("=" * 60)
        logger.info("STARTING PARALLEL RENDER JOBS")
        logger.info("=" * 60)
        
        render_success = self._execute_render_jobs_parallel()
        
        if not render_success:
            logger.error("Render jobs phase failed")
            return False
        
        # Phase 2: Wait for combine jobs to be ready and execute them
        logger.info("=" * 60)
        logger.info("STARTING COMBINE JOBS")
        logger.info("=" * 60)
        
        combine_success = self._execute_combine_jobs()
        
        if not combine_success:
            logger.error("Combine jobs phase failed")
            return False
        
        return True
    
    def _execute_render_jobs_parallel(self) -> bool:
        """Execute render jobs in parallel across instances"""
        
        # Create worker threads for each instance that can handle render jobs
        render_instances = [cfg.instance_id for cfg in self.instance_configs 
                           if cfg.enabled and ("HIGH" in cfg.job_types or "LOW" in cfg.job_types)]
        
        if not render_instances:
            logger.error("No instances available for render jobs")
            return False
        
        logger.info(f"Starting {len(render_instances)} render workers")
        
        # Use ThreadPoolExecutor for parallel execution
        with ThreadPoolExecutor(max_workers=len(render_instances)) as executor:
            # Submit worker tasks for each instance
            futures = []
            for instance_id in render_instances:
                future = executor.submit(self._render_worker, instance_id)
                futures.append(future)
            
            # Wait for all workers to complete
            success = True
            for future in as_completed(futures):
                try:
                    worker_success = future.result()
                    if not worker_success:
                        success = False
                        logger.error("Render worker failed")
                except Exception as e:
                    logger.error(f"Render worker exception: {e}")
                    success = False
        
        return success
    
    def _render_worker(self, instance_id: str) -> bool:
        """Worker thread for processing render jobs on a specific instance"""
        logger.info(f"Render worker started for instance {instance_id}")
        
        while not self.shutdown_requested.is_set():
            # Get next job for this instance
            job_data = self.queue_manager.get_next_job(instance_id)
            
            if job_data is None:
                # No more jobs available, check if we should exit
                status = self.queue_manager.get_queue_status()
                if status["high_pending"] == 0 and status["low_pending"] == 0:
                    logger.info(f"No more render jobs, worker {instance_id} exiting")
                    break
                
                # Wait a bit and try again
                time.sleep(0.5)
                continue
            
            job, prompt_name = job_data
            
            # Execute the job
            success = self._execute_single_render_job(instance_id, job)
            
            # Update job tracking
            execution_time = 10.0  # TODO: Track actual execution time
            self.queue_manager.mark_job_completed(job.job_id, success, execution_time)
            
            if success:
                self.completed_jobs.append(job.job_number)
                job.status = JobStatus.COMPLETED
                
                # Extract reference image if this is a LOW job
                if job.job_type == JobType.LOW:
                    ref_success = self.extract_reference_image(job)
                    if not ref_success:
                        logger.warning(f"Failed to extract reference image for job {job.job_number}")
            else:
                self.failed_jobs.append(job.job_number)
                job.status = JobStatus.FAILED
                
                if job.retry_count >= MAX_RETRIES:
                    logger.error(f"Job {job.job_number} failed after {MAX_RETRIES} retries")
                    return False
        
        logger.info(f"Render worker {instance_id} completed")
        return True
    
    def _execute_single_render_job(self, instance_id: str, job: RenderJob) -> bool:
        """Execute a single render job on the specified instance"""
        try:
            logger.info(f"🔄 Executing {job.job_type.value} job {job.job_number} on instance {instance_id}")
            
            # Mark job as started
            self.queue_manager.mark_job_started(job.job_id)
            
            # Modify workflow based on job type
            if job.job_type == JobType.HIGH:
                workflow = self.workflow_manager.modify_for_high_job(job)
            else:
                workflow = self.workflow_manager.modify_for_low_job(job)
            
            # Execute workflow on the specific instance
            success, prompt_id, error = self.multi_client.execute_job(instance_id, workflow)
            
            if success:
                logger.info(f"✅ Job {job.job_number} completed successfully on {instance_id}")
                return True
            else:
                logger.error(f"❌ Job {job.job_number} failed on {instance_id}: {error}")
                job.retry_count += 1
                return False
                
        except Exception as e:
            logger.error(f"❌ Exception executing job {job.job_number} on {instance_id}: {e}")
            job.retry_count += 1
            return False
    
    def _execute_combine_jobs(self) -> bool:
        """Execute combine jobs after all render jobs are complete"""
        
        # Wait for combine jobs to be ready
        logger.info("Waiting for all HIGH and LOW jobs to complete...")
        ready = self.queue_manager.wait_for_combine_ready(timeout=3600)  # 1 hour timeout
        
        if not ready:
            logger.error("Timeout waiting for combine jobs to be ready")
            return False
        
        logger.info("All HIGH and LOW jobs complete. Starting COMBINE jobs...")
        
        # Get an available instance for combine jobs (prefer first instance)
        combine_instance = None
        for instance_id in [cfg.instance_id for cfg in self.instance_configs if cfg.enabled]:
            if self.multi_client.health_status.get(instance_id, False):
                combine_instance = instance_id
                break
        
        if not combine_instance:
            logger.error("No healthy instance available for combine jobs")
            return False
        
        # Execute combine jobs sequentially
        while True:
            combine_data = self.queue_manager.get_next_combine_job()
            if combine_data is None:
                break
            
            combine_job, prompt_name = combine_data
            
            logger.info(f"🔄 Executing COMBINE job {combine_job.job_id} on {combine_instance}")
            
            try:
                # Create combine workflow
                workflow = self.workflow_manager.create_combine_workflow(combine_job)
                
                # Execute workflow
                success, prompt_id, error = self.multi_client.execute_job(combine_instance, workflow)
                
                if success:
                    combine_job.status = JobStatus.COMPLETED
                    logger.info(f"✅ COMBINE job {combine_job.job_id} completed")
                else:
                    combine_job.status = JobStatus.FAILED
                    logger.error(f"❌ COMBINE job {combine_job.job_id} failed: {error}")
                    combine_job.retry_count += 1
                    
                    if combine_job.retry_count >= MAX_RETRIES:
                        logger.error(f"COMBINE job {combine_job.job_id} failed after {MAX_RETRIES} retries")
                        return False
                
            except Exception as e:
                logger.error(f"❌ Exception executing COMBINE job {combine_job.job_id}: {e}")
                combine_job.status = JobStatus.FAILED
                combine_job.retry_count += 1
                
                if combine_job.retry_count >= MAX_RETRIES:
                    return False
        
        logger.info("All COMBINE jobs completed")
        return True
    
    def extract_reference_image(self, job: RenderJob) -> bool:
        """Extract reference image from video output (placeholder implementation)"""
        # This is the same logic as in the original JobOrchestrator
        # TODO: Import and use the actual implementation
        logger.info(f"Extracting reference image for job {job.job_number}")
        return True
    
    def get_execution_status(self) -> Dict:
        """Get current execution status"""
        queue_status = self.queue_manager.get_queue_status()
        instance_status = self.multi_client.get_status_summary()
        
        return {
            "dual_mode": self.dual_mode,
            "queue_status": queue_status,
            "instance_status": instance_status,
            "completed_jobs": len(self.completed_jobs),
            "failed_jobs": len(self.failed_jobs)
        }
    
    def interrupt_execution(self):
        """Interrupt all running jobs"""
        logger.info("Interrupting execution on all instances")
        self.shutdown_requested.set()
        self.multi_client.interrupt_all()
    
    def save_state(self):
        """Save current execution state for recovery"""
        state = {
            'prompt_name': self.current_prompt_name,
            'completed_jobs': self.completed_jobs,
            'failed_jobs': self.failed_jobs,
            'dual_mode': self.dual_mode,
            'timestamp': time.time()
        }
        self.storage.save_state(self.current_prompt_name, state)
        logger.info("Execution state saved")
    
    def restore_state(self, state: Dict):
        """Restore execution state from saved data"""
        self.completed_jobs = state.get('completed_jobs', [])
        self.failed_jobs = state.get('failed_jobs', [])
        logger.info(f"Restored state: {len(self.completed_jobs)} completed, {len(self.failed_jobs)} failed")
    
    def shutdown(self):
        """Shutdown the orchestrator"""
        logger.info("Shutting down DualInstanceOrchestrator")
        self.shutdown_requested.set()
        self.multi_client.disconnect_all()
        self.queue_manager.shutdown()
        logger.info("DualInstanceOrchestrator shutdown complete")