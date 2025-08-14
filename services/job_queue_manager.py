"""
Job Queue Manager for dual ComfyUI instance coordination
Manages HIGH, LOW, and COMBINE job queues with proper synchronization
"""
import threading
import time
import logging
from queue import Queue, Empty
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from collections import defaultdict

from models.job import RenderJob, CombineJob, JobType, JobStatus
from models.dual_instance import (
    ComfyUIInstanceConfig, JobAssignment, DualInstanceState, 
    InstanceStatus, InstanceMetrics
)

logger = logging.getLogger(__name__)


@dataclass
class QueuedJob:
    """Wrapper for jobs in the queue with metadata"""
    job: RenderJob
    prompt_name: str
    priority: int = 0  # Higher number = higher priority
    queued_at: float = None
    
    def __post_init__(self):
        if self.queued_at is None:
            self.queued_at = time.time()


class JobQueueManager:
    """
    Manages job queues and synchronization for dual ComfyUI instances
    
    Features:
    - Separate queues for HIGH, LOW, and COMBINE jobs
    - Thread-safe job distribution
    - Cross-prompt job interleaving for maximum instance utilization
    - Synchronization logic to postpone COMBINE jobs until HIGH/LOW completion
    """
    
    def __init__(self, instance_configs: List[ComfyUIInstanceConfig]):
        self.instances = {cfg.instance_id: cfg for cfg in instance_configs}
        self.state = DualInstanceState(
            instances=self.instances.copy(),
            assignments={},
            metrics={cfg.instance_id: InstanceMetrics(cfg.instance_id) for cfg in instance_configs}
        )
        
        # Job queues
        self.high_queue = Queue()
        self.low_queue = Queue()
        self.combine_queue = Queue()
        
        # Synchronization primitives
        self.lock = threading.RLock()
        self.combine_ready_event = threading.Event()
        
        # Track job counts per prompt for intelligent interleaving
        self.prompt_job_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: {"HIGH": 0, "LOW": 0, "COMBINE": 0})
        self.prompt_completed_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: {"HIGH": 0, "LOW": 0})
        
        # Active jobs tracking
        self.active_jobs: Dict[str, JobAssignment] = {}  # job_id -> assignment
        
        logger.info(f"JobQueueManager initialized with {len(instance_configs)} instances")
    
    def add_jobs_for_prompt(self, render_jobs: List[RenderJob], combine_jobs: List[CombineJob], prompt_name: str):
        """
        Add all jobs for a single prompt to the appropriate queues
        
        Args:
            render_jobs: List of HIGH and LOW render jobs
            combine_jobs: List of combine jobs (will be queued but not executed until sync point)
            prompt_name: Identifier for the prompt these jobs belong to
        """
        with self.lock:
            high_jobs = [job for job in render_jobs if job.job_type == JobType.HIGH]
            low_jobs = [job for job in render_jobs if job.job_type == JobType.LOW]
            
            # Update prompt job counts
            self.prompt_job_counts[prompt_name]["HIGH"] = len(high_jobs)
            self.prompt_job_counts[prompt_name]["LOW"] = len(low_jobs)
            self.prompt_job_counts[prompt_name]["COMBINE"] = len(combine_jobs)
            
            # Add render jobs to appropriate queues
            for job in high_jobs:
                queued_job = QueuedJob(job, prompt_name, priority=self._calculate_priority(job, prompt_name))
                self.high_queue.put(queued_job)
                self.state.high_jobs_pending += 1
                logger.debug(f"Added HIGH job {job.job_id} for prompt {prompt_name}")
            
            for job in low_jobs:
                queued_job = QueuedJob(job, prompt_name, priority=self._calculate_priority(job, prompt_name))
                self.low_queue.put(queued_job)
                self.state.low_jobs_pending += 1
                logger.debug(f"Added LOW job {job.job_id} for prompt {prompt_name}")
            
            # Add combine jobs (but they won't be processed until sync point)
            for job in combine_jobs:
                self.combine_queue.put((job, prompt_name))
                self.state.combine_jobs_pending += 1
                logger.debug(f"Added COMBINE job {job.job_id} for prompt {prompt_name}")
            
            logger.info(f"Added jobs for prompt {prompt_name}: {len(high_jobs)} HIGH, {len(low_jobs)} LOW, {len(combine_jobs)} COMBINE")
    
    def get_next_job(self, instance_id: str) -> Optional[Tuple[RenderJob, str]]:
        """
        Get the next job for a specific instance
        
        Args:
            instance_id: ID of the ComfyUI instance requesting work
            
        Returns:
            Tuple of (job, prompt_name) or None if no suitable job available
        """
        with self.lock:
            instance = self.instances.get(instance_id)
            if not instance or not instance.enabled:
                return None
            
            # Check if instance can handle HIGH jobs
            if instance.can_handle_job_type(JobType.HIGH):
                try:
                    queued_job = self.high_queue.get_nowait()
                    job = queued_job.job
                    prompt_name = queued_job.prompt_name
                    
                    # Create job assignment
                    assignment = JobAssignment(
                        job_id=job.job_id,
                        job_type=job.job_type,
                        instance_id=instance_id,
                        prompt_name=prompt_name,
                        assigned_at=time.time()
                    )
                    
                    self.active_jobs[job.job_id] = assignment
                    self.state.mark_instance_busy(instance_id)
                    self.state.high_jobs_pending -= 1
                    
                    logger.info(f"Assigned HIGH job {job.job_id} to instance {instance_id}")
                    return (job, prompt_name)
                    
                except Empty:
                    pass
            
            # Check if instance can handle LOW jobs
            if instance.can_handle_job_type(JobType.LOW):
                try:
                    queued_job = self.low_queue.get_nowait()
                    job = queued_job.job
                    prompt_name = queued_job.prompt_name
                    
                    # Create job assignment
                    assignment = JobAssignment(
                        job_id=job.job_id,
                        job_type=job.job_type,
                        instance_id=instance_id,
                        prompt_name=prompt_name,
                        assigned_at=time.time()
                    )
                    
                    self.active_jobs[job.job_id] = assignment
                    self.state.mark_instance_busy(instance_id)
                    self.state.low_jobs_pending -= 1
                    
                    logger.info(f"Assigned LOW job {job.job_id} to instance {instance_id}")
                    return (job, prompt_name)
                    
                except Empty:
                    pass
            
            # No jobs available for this instance
            return None
    
    def get_next_combine_job(self) -> Optional[Tuple[CombineJob, str]]:
        """
        Get the next combine job if ready
        
        Returns:
            Tuple of (combine_job, prompt_name) or None if not ready or no jobs
        """
        with self.lock:
            # Check if we can start combine jobs
            if not self.state.can_start_combine_jobs():
                return None
            
            try:
                combine_job, prompt_name = self.combine_queue.get_nowait()
                self.state.combine_jobs_pending -= 1
                logger.info(f"Retrieved COMBINE job {combine_job.job_id} for prompt {prompt_name}")
                return (combine_job, prompt_name)
            except Empty:
                return None
    
    def mark_job_started(self, job_id: str):
        """Mark a job as started"""
        with self.lock:
            if job_id in self.active_jobs:
                self.active_jobs[job_id].started_at = time.time()
                logger.debug(f"Job {job_id} started")
    
    def mark_job_completed(self, job_id: str, success: bool, execution_time: float = 0.0):
        """
        Mark a job as completed and update metrics
        
        Args:
            job_id: ID of the completed job
            success: Whether the job succeeded
            execution_time: Time taken to execute the job
        """
        with self.lock:
            if job_id not in self.active_jobs:
                logger.warning(f"Attempted to complete unknown job {job_id}")
                return
            
            assignment = self.active_jobs[job_id]
            assignment.completed_at = time.time()
            
            # Update instance status
            self.state.mark_instance_idle(assignment.instance_id)
            
            # Update metrics
            metrics = self.state.metrics[assignment.instance_id]
            metrics.update_job_completion(execution_time, success)
            
            # Update prompt completion counts
            job_type_str = assignment.job_type.value
            self.prompt_completed_counts[assignment.prompt_name][job_type_str] += 1
            
            # Check if this prompt's HIGH and LOW jobs are all complete
            prompt_name = assignment.prompt_name
            high_total = self.prompt_job_counts[prompt_name]["HIGH"]
            low_total = self.prompt_job_counts[prompt_name]["LOW"]
            high_completed = self.prompt_completed_counts[prompt_name]["HIGH"]
            low_completed = self.prompt_completed_counts[prompt_name]["LOW"]
            
            if high_completed >= high_total and low_completed >= low_total:
                logger.info(f"All HIGH/LOW jobs completed for prompt {prompt_name}")
            
            # Check if all HIGH and LOW jobs across all prompts are complete
            if self.state.can_start_combine_jobs() and not self.state.combine_jobs_ready:
                self.state.combine_jobs_ready = True
                self.combine_ready_event.set()
                logger.info("All HIGH and LOW jobs completed. COMBINE jobs are now ready.")
            
            # Remove from active jobs
            del self.active_jobs[job_id]
            
            logger.info(f"Job {job_id} completed successfully: {success}, execution time: {execution_time:.2f}s")
    
    def mark_job_failed(self, job_id: str, error_message: str):
        """Mark a job as failed"""
        self.mark_job_completed(job_id, success=False)
        logger.error(f"Job {job_id} failed: {error_message}")
    
    def wait_for_combine_ready(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for COMBINE jobs to be ready for execution
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if combine jobs are ready, False if timeout
        """
        return self.combine_ready_event.wait(timeout)
    
    def get_queue_status(self) -> Dict[str, int]:
        """Get current queue status"""
        with self.lock:
            return {
                "high_pending": self.state.high_jobs_pending,
                "low_pending": self.state.low_jobs_pending,
                "combine_pending": self.state.combine_jobs_pending,
                "combine_ready": self.state.combine_jobs_ready,
                "active_jobs": len(self.active_jobs)
            }
    
    def get_instance_status(self) -> Dict[str, Dict]:
        """Get status of all instances"""
        with self.lock:
            status = {}
            for instance_id, instance in self.instances.items():
                metrics = self.state.metrics[instance_id]
                status[instance_id] = {
                    "config": instance.to_dict(),
                    "metrics": {
                        "jobs_completed": metrics.jobs_completed,
                        "jobs_failed": metrics.jobs_failed,
                        "success_rate": metrics.success_rate,
                        "avg_execution_time": metrics.avg_execution_time
                    }
                }
            return status
    
    def _calculate_priority(self, job: RenderJob, prompt_name: str) -> int:
        """
        Calculate job priority for intelligent scheduling
        Higher numbers = higher priority
        """
        # Base priority on job number (earlier jobs have higher priority)
        base_priority = 1000 - job.job_number
        
        # Boost priority for prompts that are closer to completion
        # This helps finish entire prompts faster
        total_jobs = (self.prompt_job_counts[prompt_name]["HIGH"] + 
                     self.prompt_job_counts[prompt_name]["LOW"])
        completed_jobs = (self.prompt_completed_counts[prompt_name]["HIGH"] + 
                         self.prompt_completed_counts[prompt_name]["LOW"])
        
        if total_jobs > 0:
            completion_ratio = completed_jobs / total_jobs
            completion_boost = int(completion_ratio * 100)
            base_priority += completion_boost
        
        return base_priority
    
    def shutdown(self):
        """Shutdown the queue manager"""
        with self.lock:
            logger.info("Shutting down JobQueueManager")
            # Clear all queues
            while not self.high_queue.empty():
                try:
                    self.high_queue.get_nowait()
                except Empty:
                    break
            
            while not self.low_queue.empty():
                try:
                    self.low_queue.get_nowait()
                except Empty:
                    break
            
            while not self.combine_queue.empty():
                try:
                    self.combine_queue.get_nowait()
                except Empty:
                    break
            
            self.active_jobs.clear()
            logger.info("JobQueueManager shutdown complete")