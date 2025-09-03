"""Prompt data model"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class PromptData:
    """Represents parsed prompt file data"""
    video_name: str
    start_frame: int
    total_frames: int
    positive_prompt: str
    negative_prompt: str
    source_file: Optional[str] = None
    
    def validate(self) -> bool:
        """Validate prompt data integrity"""
        if not self.video_name:
            raise ValueError("Video name cannot be empty")
        if self.total_frames <= 0:
            raise ValueError("Total frames must be positive")
        if not self.positive_prompt:
            raise ValueError("Positive prompt cannot be empty")
        return True
    
    def __str__(self) -> str:
        return f"PromptData(video={self.video_name}, frames={self.total_frames})"