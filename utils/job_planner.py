"""Job planning logic for calculating render sequences"""
import logging
import math
from typing import List, Tuple
from pathlib import Path

from models.prompt_data import PromptData
from models.job import RenderJob, CombineJob, JobStatus
from config import FRAMES_TO_RENDER
from services.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


class JobPlanner:
    """Plans and calculates job sequences for video generation"""
    
    def __init__(self, promptName, frames_per_chunk: int = FRAMES_TO_RENDER):
        self.frames_per_chunk = frames_per_chunk
        self.promptName = promptName        
        self.storage = ServiceFactory.create_storage_manager()
    
    def calculate_job_sequence(self, prompt_data: PromptData) -> List[RenderJob]:
        """Calculate the complete job sequence for a prompt
        
        Returns:
            Tuple of (render_jobs, combine_jobs)
        """
                
        render_jobs = []
        job_number = 1
        
        self.storage.ensure_directories(self.promptName)
        source_path = Path(prompt_data.source_file)
        reference_video_path = str(source_path.with_suffix(".mp4").resolve())
        reference_image_path = str(source_path.with_suffix(".png").resolve())
        random_seed = 1013166398531279
        # Create render job
        render_job = RenderJob(
            prompt_name=self.promptName,
            job_number=job_number,
            seed=random_seed,
            start_frame=0,
            frames_to_render=prompt_data.total_frames,
            video_input_path=reference_video_path,
            reference_image_path=reference_image_path,
            positive_prompt=prompt_data.positive_prompt,
            negative_prompt=prompt_data.negative_prompt,
            video_output_path=self.storage.get_video_path(self.promptName, job_number),
            video_output_full_path=self.storage.get_video_full_path(self.promptName, job_number)
        )
            
        logger.info(f"Creating job {prompt_data.source_file} {render_job.job_number} with frames {render_job.frames_to_render}")
            
        render_jobs.append(render_job)         
       
        return render_jobs