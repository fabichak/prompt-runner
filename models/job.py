"""Job models for rendering and combining"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from enum import Enum
import uuid


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class RenderJob:
    """Represents a single render job"""
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    job_number: int = 0
    start_frame: int = 0
    seed: int = 0
    frames_to_render: int = 101
    video_input_path: str = ""
    prompt_name: str = ""  # Session identifier for organizing files
    frames_rendered: int = 0
    
    # Input/output paths
    latent_dir_path: Optional[str] = None
    latent_path: Optional[str] = None
    reference_image_path: Optional[str] = None
    video_output_path: Optional[str] = None
    video_output_full_path: Optional[str] = None
    next_reference_image_output_path: Optional[str] = None
    
    # Status tracking
    status: JobStatus = JobStatus.PENDING
    error_message: Optional[str] = None
    retry_count: int = 0
    
    # Prompt data
    positive_prompt: str = ""
    negative_prompt: str = ""
    
    # Note: Paths are now set by calling code (JobPlanner) that knows the promptName and job details

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'job_id': self.job_id,
            'job_number': self.job_number,
            'start_frame': self.start_frame,
            'frames_to_render': self.frames_to_render,
            'video_name': self.video_input_path,
            'latent_path': self.latent_path,
            'reference_image_path': self.reference_image_path,
            'video_output_path': self.video_output_path,
            'status': self.status.value,
            'error_message': self.error_message,
            'retry_count': self.retry_count,
            'positive_prompt': self.positive_prompt,
            'negative_prompt': self.negative_prompt
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RenderJob':
        """Create from dictionary"""
        job = cls()
        job.job_id = data.get('job_id', str(uuid.uuid4()))
        job.job_number = data.get('job_number', 0)
        job.start_frame = data.get('start_frame', 0)
        job.frames_to_render = data.get('frames_to_render', 101)
        job.video_input_path = data.get('video_name', '')
        job.latent_path = data.get('latent_path')
        job.reference_image_path = data.get('reference_image_path')
        job.video_output_path = data.get('video_output_path')
        job.status = JobStatus(data.get('status', 'pending'))
        job.error_message = data.get('error_message')
        job.retry_count = data.get('retry_count', 0)
        job.positive_prompt = data.get('positive_prompt', '')
        job.negative_prompt = data.get('negative_prompt', '')
        return job
    
    def __str__(self) -> str:
        return f"RenderJob(#{self.job_number}, frames {self.start_frame}-{self.start_frame + self.frames_to_render})"


@dataclass
class CombineJob:
    """Represents a video combination job"""
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    combine_number: int = 0
    video_name: str = ""
    prompt_name: str = ""  # Session identifier for organizing files
    
    # Input/output paths
    input_video_path: str = ""
    previous_combined_path: Optional[str] = None
    output_path: str = ""
    
    # Status tracking
    status: JobStatus = JobStatus.PENDING
    error_message: Optional[str] = None
    retry_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'job_id': self.job_id,
            'combine_number': self.combine_number,
            'video_name': self.video_name,
            'input_video_path': self.input_video_path,
            'previous_combined_path': self.previous_combined_path,
            'output_path': self.output_path,
            'status': self.status.value,
            'error_message': self.error_message,
            'retry_count': self.retry_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CombineJob':
        """Create from dictionary"""
        job = cls()
        job.job_id = data.get('job_id', str(uuid.uuid4()))
        job.combine_number = data.get('combine_number', 0)
        job.video_name = data.get('video_name', '')
        job.input_video_path = data.get('input_video_path', '')
        job.previous_combined_path = data.get('previous_combined_path')
        job.output_path = data.get('output_path', '')
        job.status = JobStatus(data.get('status', 'pending'))
        job.error_message = data.get('error_message')
        job.retry_count = data.get('retry_count', 0)
        return job
    
    def __str__(self) -> str:
        return f"CombineJob(#{self.combine_number} for {self.video_name})"