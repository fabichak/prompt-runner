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
    select_every_n_frames: int = 1
    steps: int = 0
    cfg: float = 0
    video_input_path: str = ""
    reference_image_path: str = ""
        
    prompt_name: str = ""  # Session identifier for organizing files
    
    video_output_path: Optional[str] = None
    video_output_full_path: Optional[str] = None
    
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
            'video_output_path': self.video_output_path,
            'status': self.status.value,
            'error_message': self.error_message,
            'retry_count': self.retry_count,
            'positive_prompt': self.positive_prompt,
            'negative_prompt': self.negative_prompt,
            'steps': self.steps,
            'cfg': self.cfg,
            'select_every_n_frames': self.select_every_n_frames
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
        job.video_output_path = data.get('video_output_path')
        job.status = JobStatus(data.get('status', 'pending'))
        job.error_message = data.get('error_message')
        job.retry_count = data.get('retry_count', 0)
        job.positive_prompt = data.get('positive_prompt', '')
        job.negative_prompt = data.get('negative_prompt', '')
        job.steps = data.get('steps', 0)
        job.cfg = data.get('cfg', 0)
        job.select_every_n_frames = data.get('select_every_n_frames', 1)
        return job
    
    def __str__(self) -> str:
        return f"RenderJob(#{self.job_number}, frames {self.start_frame}-{self.start_frame + self.frames_to_render})"