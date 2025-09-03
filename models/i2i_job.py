"""i2i Job model for image-to-image rendering"""
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class I2IJob:
    """Represents a single i2i rendering job"""
    image_path: str
    cfg_value: float
    render_number: int  # Which render iteration (1 to IMAGE_RENDER_AMOUNT)
    output_filename: str
    seed: Optional[int] = None
    
    def __post_init__(self):
        """Generate random seed if not provided"""
        if self.seed is None:
            self.seed = random.randint(0, 2**32 - 1)
    
    @property
    def job_id(self) -> str:
        """Generate unique job ID"""
        image_name = Path(self.image_path).stem
        return f"{image_name}_cfg{self.cfg_value}_r{self.render_number}"
    
    def __str__(self) -> str:
        return f"I2IJob({self.job_id}, seed={self.seed})"