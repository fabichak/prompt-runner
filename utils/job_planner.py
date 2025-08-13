"""Job planning logic for calculating render sequences"""
import logging
import math
from typing import List, Tuple, Optional
from pathlib import Path

from models.prompt_data import PromptData
from models.job import RenderJob, CombineJob, JobType, JobStatus
from config import FRAMES_TO_RENDER
from services.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


class JobPlanner:
    """Plans and calculates job sequences for video generation"""
    
    def __init__(self, promptName, frames_per_chunk: int = FRAMES_TO_RENDER):
        self.frames_per_chunk = frames_per_chunk
        self.promptName = promptName        
        self.storage = ServiceFactory.create_storage_manager()
    
    def calculate_job_sequence(self, prompt_data: PromptData) -> Tuple[List[RenderJob], List[CombineJob]]:
        """Calculate the complete job sequence for a prompt
        
        Returns:
            Tuple of (render_jobs, combine_jobs)
        """
        total_frames = prompt_data.total_frames
        frames_per_chunk = self.frames_per_chunk
        
        # Calculate number of job pairs needed
        num_chunks = math.ceil(total_frames / frames_per_chunk)
        logger.info(f"Planning {num_chunks} job pairs for {total_frames} total frames ({frames_per_chunk} per chunk)")
        
        render_jobs = []
        combine_jobs = []
        
        # Create render jobs (alternating HIGH/LOW pairs)
        current_frame = 0
        job_number = 1
        
        self.storage.ensure_directories(self.promptName)

        random_seed = 1013166398531279

        for chunk_idx in range(num_chunks):
            # Calculate frames for this chunk
            remaining_frames = total_frames - current_frame
            chunk_frames = min(frames_per_chunk, remaining_frames)
            
            # Create HIGH job (odd numbers: 1, 3, 5...)
            high_job = RenderJob(
                prompt_name=self.promptName,
                job_type=JobType.HIGH,
                job_number=job_number,
                seed=random_seed,
                start_frame=current_frame,
                frames_to_render=chunk_frames,
                video_name=prompt_data.video_name,
                positive_prompt=prompt_data.positive_prompt,
                negative_prompt=prompt_data.negative_prompt,
                latent_path=self.storage.get_latent_path(self.promptName, job_number),
                reference_image_path= self.storage.get_reference_path(self.promptName, job_number-1) #from job-1 low output, not used in job=1
            )

            render_jobs.append(high_job)
            job_number += 1
            
            # Create LOW job (even numbers: 2, 4, 6...)
            low_job = RenderJob(
                prompt_name=self.promptName,
                job_type=JobType.LOW,
                job_number=job_number,
                start_frame=current_frame,
                seed=random_seed,
                frames_to_render=chunk_frames,
                video_name=prompt_data.video_name,
                positive_prompt=prompt_data.positive_prompt,
                negative_prompt=prompt_data.negative_prompt,
                latent_path=self.storage.get_latent_path(self.promptName, job_number-1), #from the job-1 high output
                reference_image_path= self.storage.get_reference_path(self.promptName, job_number-2), #from job-2 low output, not used in job=2
                video_output_path=self.storage.get_video_path(self.promptName, job_number),
                video_output_full_path=self.storage.get_video_full_path(self.promptName, job_number)
            )
            
            render_jobs.append(low_job)
            job_number += 1
            
            # Update frame position for next chunk
            current_frame += chunk_frames
        
        # Create combine jobs for each LOW job output
        combine_number = 1
        previous_combined_path = None
        
        for job in render_jobs:
            if job.job_type == JobType.LOW:
                combine_job = CombineJob(
                    prompt_name=self.promptName,
                    combine_number=combine_number,
                    video_name=prompt_data.video_name,
                    input_video_path=job.video_output_full_path,
                    previous_combined_path=previous_combined_path,
                    output_path=str(self.storage.get_combined_path(self.promptName, combine_number))
                )
                combine_jobs.append(combine_job)
                
                # Update previous path for next combine
                previous_combined_path = self.storage.get_combined_full_path(self.promptName, combine_number)
                combine_number += 1
        
        # Log job plan summary
        self._log_job_plan(render_jobs, combine_jobs)
        
        return render_jobs, combine_jobs
    
    def _log_job_plan(self, render_jobs: List[RenderJob], combine_jobs: List[CombineJob]):
        """Log a summary of the job plan"""
        logger.info("=" * 60)
        logger.info("JOB EXECUTION PLAN")
        logger.info("=" * 60)
        
        logger.info(f"Total render jobs: {len(render_jobs)}")
        logger.info(f"Total combine jobs: {len(combine_jobs)}")
        
        for job in render_jobs:
            ref_info = f" [ref: {job.reference_image_path}]" if job.reference_image_path else ""
            logger.info(f"  {job}{ref_info}")
        
        logger.info("-" * 40)
        for job in combine_jobs:
            prev_info = f" + {job.previous_combined_path}" if job.previous_combined_path else ""
            logger.info(f"  {job}: {job.input_video_path}{prev_info} -> {job.output_path}")
        
        logger.info("=" * 60)
    
    def validate_job_sequence(self, render_jobs: List[RenderJob], total_frames: int) -> bool:
        """Validate that job sequence covers all required frames"""
        # Check frame coverage
        total_covered = sum(job.frames_to_render for job in render_jobs if job.job_type == JobType.HIGH)
        if total_covered != total_frames:
            logger.error(f"Frame coverage mismatch: {total_covered} != {total_frames}")
            return False
        
        # Check job pairing (should have equal HIGH and LOW jobs)
        high_jobs = [j for j in render_jobs if j.job_type == JobType.HIGH]
        low_jobs = [j for j in render_jobs if j.job_type == JobType.LOW]
        
        if len(high_jobs) != len(low_jobs):
            logger.error(f"Job pairing mismatch: {len(high_jobs)} HIGH != {len(low_jobs)} LOW")
            return False
        
        # Check job numbering
        expected_numbers = list(range(1, len(render_jobs) + 1))
        actual_numbers = [job.job_number for job in render_jobs]
        
        if actual_numbers != expected_numbers:
            logger.error(f"Job numbering error: {actual_numbers}")
            return False
        
        logger.info("Job sequence validation passed")
        return True
    
    def get_job_dependencies(self, job: RenderJob) -> List[int]:
        """Get list of job numbers that must complete before this job can run"""
        dependencies = []
        
        if job.job_type == JobType.LOW:
            # LOW jobs depend on their preceding HIGH job
            dependencies.append(job.job_number - 1)
        
        if job.job_type == JobType.HIGH and job.job_number >= 3:
            # HIGH jobs from 3+ depend on the LOW job two positions back (for reference image)
            dependencies.append(job.job_number - 2)
        
        return dependencies
    
    def can_job_run(self, job: RenderJob, completed_jobs: List[int]) -> bool:
        """Check if a job can run based on completed dependencies"""
        dependencies = self.get_job_dependencies(job)
        return all(dep in completed_jobs for dep in dependencies)