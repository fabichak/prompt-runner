"""Image-to-image job model"""
from dataclasses import dataclass
from typing import Dict, Any
from pathlib import Path
import random
import logging

from models.base_job import BaseJob, JobStatus

logger = logging.getLogger(__name__)


@dataclass
class I2IJob(BaseJob):
    """Image-to-image rendering job"""
    image_path: str
    cfg_value: float
    seed: int
    output_filename: str

    @classmethod
    def from_api_data(cls, api_data: Dict[str, Any]) -> 'I2IJob':
        """Create I2I job from Trello API data"""
        # Generate random seed if not provided
        seed = api_data.get('seed')
        if seed is None:
            seed = random.randint(0, 2**32 - 1)

        # Generate output filename
        image_name = Path(api_data.get('imagePath', '')).stem
        cfg_value = api_data.get('cfg', 7.0)
        output_filename = f"{image_name}_cfg{cfg_value}_{seed}"

        return cls(
            job_id=api_data.get('jobId', api_data.get('cardId')),
            card_id=api_data.get('cardId'),
            mode='i2i',
            image_path=api_data.get('imagePath', api_data.get('imageUrl')),
            cfg_value=cfg_value,
            seed=seed,
            output_filename=output_filename
        )

    def to_workflow_params(self) -> Dict[str, Any]:
        """Get parameters for workflow modification"""
        return {
            'image_path': self.image_path,
            'cfg_value': self.cfg_value,
            'seed': self.seed,
            'output_prefix': self.output_filename
        }

    def validate(self) -> bool:
        """Validate job parameters"""
        # Check required path
        if not self.image_path:
            logger.error("Image path is required")
            return False

        # Validate CFG value
        if self.cfg_value <= 0 or self.cfg_value > 30:
            logger.error(f"Invalid CFG value: {self.cfg_value} (should be between 0 and 30)")
            return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        base_dict = super().to_dict()
        base_dict.update({
            'image_path': self.image_path,
            'cfg_value': self.cfg_value,
            'seed': self.seed,
            'output_filename': self.output_filename
        })
        return base_dict

    @property
    def job_id_display(self) -> str:
        """Generate display-friendly job ID"""
        image_name = Path(self.image_path).stem
        return f"{image_name}_cfg{self.cfg_value}"

    def __str__(self) -> str:
        return f"I2IJob({self.job_id_display}, seed={self.seed})"