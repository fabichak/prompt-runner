"""Video-to-video job model"""
from dataclasses import dataclass
from typing import Dict, Any, Optional
from pathlib import Path
import random
import logging

from models.base_job import BaseJob, JobStatus

logger = logging.getLogger(__name__)


@dataclass
class V2VJob(BaseJob):
    """Video-to-video rendering job"""
    video_path: str
    reference_image_path: str
    positive_prompt: str
    negative_prompt: str
    start_frame: int = 0
    total_frames: int = 101
    select_every_n_frames: int = 1
    seed: int = 0

    # Output paths
    video_output_path: Optional[str] = None
    video_output_full_path: Optional[str] = None

    @classmethod
    def from_api_data(cls, api_data: Dict[str, Any]) -> 'V2VJob':
        """Create V2V job from Trello API data"""
        # Generate random seed if not provided
        seed = api_data.get('seed')
        if seed is None:
            seed = random.randint(0, 2**32 - 1)

        return cls(
            job_id=api_data.get('jobId', api_data.get('cardId')),
            card_id=api_data.get('cardId'),
            mode='v2v',
            video_path=api_data.get('videoPath', api_data.get('videoUrl')),
            reference_image_path=api_data.get('imagePath', api_data.get('imageUrl')),
            positive_prompt=api_data.get('positivePrompt', ''),
            negative_prompt=api_data.get('negativePrompt', ''),
            start_frame=api_data.get('startFrame', 0),
            total_frames=api_data.get('totalFrames', 101),
            select_every_n_frames=api_data.get('selectEveryNFrames', 1),
            seed=seed,
            video_output_path=api_data.get('videoOutputPath'),
            video_output_full_path=api_data.get('videoOutputFullPath')
        )

    def to_workflow_params(self) -> Dict[str, Any]:
        """Get parameters for workflow modification"""
        return {
            'video_path': self.video_path,
            'image_path': self.reference_image_path,
            'positive_prompt': self.positive_prompt,
            'negative_prompt': self.negative_prompt,
            'seed': self.seed,
            'total_frames': self.total_frames,
            'start_frame': self.start_frame,
            'select_every_n_frames': self.select_every_n_frames,
            'output_path': self.video_output_path
        }

    def validate(self) -> bool:
        """Validate job parameters"""
        # Check required paths
        if not self.video_path:
            logger.error("Video path is required")
            return False

        if not self.reference_image_path:
            logger.error("Reference image path is required")
            return False

        # Validate frame parameters
        if self.total_frames <= 0:
            logger.error(f"Invalid total_frames: {self.total_frames}")
            return False

        if self.start_frame < 0:
            logger.error(f"Invalid start_frame: {self.start_frame}")
            return False

        if self.select_every_n_frames <= 0:
            logger.error(f"Invalid select_every_n_frames: {self.select_every_n_frames}")
            return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        base_dict = super().to_dict()
        base_dict.update({
            'video_path': self.video_path,
            'reference_image_path': self.reference_image_path,
            'positive_prompt': self.positive_prompt,
            'negative_prompt': self.negative_prompt,
            'start_frame': self.start_frame,
            'total_frames': self.total_frames,
            'select_every_n_frames': self.select_every_n_frames,
            'seed': self.seed,
            'video_output_path': self.video_output_path,
            'video_output_full_path': self.video_output_full_path
        })
        return base_dict

    def __str__(self) -> str:
        return f"V2VJob({self.job_id}, frames {self.start_frame}-{self.start_frame + self.total_frames})"