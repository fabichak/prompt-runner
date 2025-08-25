"""Job planning logic for calculating render sequences"""
import logging
import math
from typing import List, Tuple
from pathlib import Path

from models.prompt_data import PromptData
from models.job import RenderJob, CombineJob, JobStatus
from config import FRAMES_TO_RENDER, START_FRAME_OFFSET
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
        
        # Calculate number of chunks needed
        num_chunks = math.ceil(total_frames / frames_per_chunk)
        logger.info(f"Planning {num_chunks} jobs for {total_frames} total frames ({frames_per_chunk} per chunk)")
        
        render_jobs = []
        combine_jobs = []
        
        # Create render jobs
        current_frame = 0
        job_number = 1
        
        self.storage.ensure_directories(self.promptName)

        random_seed = 1013166398531279

        for chunk_idx in range(num_chunks):
            # Calculate frames for this chunk
            remaining_frames = total_frames - current_frame
            chunk_frames = min(frames_per_chunk, remaining_frames)
            
            # Get reference image path
            reference_image_path = None
            if job_number == 1:
                # For the first job, check if there's a reference image with same name as prompt file
                source_path = Path(prompt_data.source_file)
                reference_path = source_path.with_suffix(".png")
                if reference_path.exists():
                    reference_image_path = str(reference_path.resolve())
            else:
                # Use the reference from the previous job
                reference_image_path = self.storage.get_reference_path(self.promptName, job_number - 1)
            
            # Create render job
            render_job = RenderJob(
                prompt_name=self.promptName,
                job_number=job_number,
                seed=random_seed,
                start_frame=current_frame,
                frames_to_render=chunk_frames,
                video_input_path=prompt_data.video_name,
                positive_prompt=prompt_data.positive_prompt,
                negative_prompt=prompt_data.negative_prompt,
                latent_path=self.storage.get_latent_path(self.promptName, job_number),
                reference_image_path=reference_image_path,
                next_reference_image_output_path=self.storage.get_reference_path(self.promptName, job_number),
                video_output_path=self.storage.get_video_path(self.promptName, job_number),
                video_output_full_path=self.storage.get_video_full_path(self.promptName, job_number)
            )
            
            logger.info(f"Creating job {render_job.job_number} with frames {current_frame}-{current_frame + chunk_frames}")
            if reference_image_path:
                logger.info(f"  Using reference image: {reference_image_path}")

            render_jobs.append(render_job)
            
            # Create combine job for this render output
            previous_combined_path = None
            if job_number > 1:
                previous_combined_path = self.storage.get_combined_full_path(self.promptName, job_number - 1)
            
            combine_job = CombineJob(
                prompt_name=self.promptName,
                combine_number=job_number,
                video_name=prompt_data.video_name,
                input_video_path=render_job.video_output_full_path,
                previous_combined_path=previous_combined_path,
                output_path=str(self.storage.get_combined_path(self.promptName, job_number))
            )
            combine_jobs.append(combine_job)
            
            # Update for next iteration
            job_number += 1
            current_frame += chunk_frames - START_FRAME_OFFSET
        
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
        total_covered = sum(job.frames_to_render for job in render_jobs)
        expected_coverage = total_frames
        
        # Account for frame overlaps from START_FRAME_OFFSET
        if len(render_jobs) > 1:
            expected_coverage += (len(render_jobs) - 1) * START_FRAME_OFFSET
        
        if abs(total_covered - expected_coverage) > START_FRAME_OFFSET:
            logger.error(f"Frame coverage issue: covered {total_covered} vs expected {expected_coverage}")
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
        
        # Each job depends on the previous job (except the first)
        if job.job_number > 1:
            dependencies.append(job.job_number - 1)
        
        return dependencies
    
    def can_job_run(self, job: RenderJob, completed_jobs: List[int]) -> bool:
        """Check if a job can run based on completed dependencies"""
        dependencies = self.get_job_dependencies(job)
        return all(dep in completed_jobs for dep in dependencies)