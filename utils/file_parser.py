"""Parse prompt files in the new v2 format"""
import logging
from pathlib import Path
from typing import Optional

from models.prompt_data import PromptData

logger = logging.getLogger(__name__)


class PromptFileParser:
    """Parser for v2 prompt file format
    
    Format:
    Line 1: video_name
    Line 2: (empty)
    Line 3: total_frames
    Line 4: (empty)
    Line 5+: positive_prompt
    Line N: (empty)
    Line N+1+: negative_prompt
    """
    
    @staticmethod
    def parse_prompt_file(file_path: Path) -> Optional[PromptData]:
        """Parse a prompt file and return PromptData object"""
        try:
            if not file_path.exists():
                logger.error(f"Prompt file not found: {file_path}")
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Split by double newlines (empty lines)
            parts = content.split('\n\n')
            
            if len(parts) < 4:
                logger.error(f"Invalid prompt file format - expected 4 parts, got {len(parts)}")
                return None
            
            # Parse each part
            video_name = parts[0].strip()
            if not video_name:
                logger.error("Video name is empty")
                return None
            
            # Remove file extension if present
            if video_name.endswith('.mp4'):
                video_name = video_name[:-4]
            
            try:
                total_frames = int(parts[1].strip())
                if total_frames <= 0:
                    raise ValueError("Total frames must be positive")
            except (ValueError, IndexError) as e:
                logger.error(f"Invalid total frames: {e}")
                return None
            
            positive_prompt = parts[2].strip()
            if not positive_prompt:
                logger.error("Positive prompt is empty")
                return None
            
            # Negative prompt can be empty
            negative_prompt = parts[3].strip() if len(parts) > 3 else ""
            
            # Create and validate PromptData
            prompt_data = PromptData(
                video_name=video_name,
                total_frames=total_frames,
                positive_prompt=positive_prompt,
                negative_prompt=negative_prompt,
                source_file=str(file_path)
            )
            
            prompt_data.validate()
            
            logger.info(f"Successfully parsed prompt file: {prompt_data}")
            return prompt_data
            
        except Exception as e:
            logger.error(f"Error parsing prompt file {file_path}: {e}")
            return None
    
    @staticmethod
    def validate_prompt_directory(directory: Path) -> list:
        """Validate and list all prompt files in a directory"""
        if not directory.exists():
            logger.error(f"Prompt directory not found: {directory}")
            return []
        
        prompt_files = []
        for file_path in directory.glob("*.txt"):
            if file_path.is_file():
                prompt_data = PromptFileParser.parse_prompt_file(file_path)
                if prompt_data:
                    prompt_files.append((file_path, prompt_data))
                else:
                    logger.warning(f"Skipping invalid prompt file: {file_path}")
        
        logger.info(f"Found {len(prompt_files)} valid prompt files")
        return prompt_files
    
    @staticmethod
    def create_sample_prompt_file(file_path: Path):
        """Create a sample prompt file for testing"""
        sample_content = """test_video

101

A beautiful sunset over the ocean with waves crashing on the shore, golden hour lighting, cinematic

blurry, low quality, distorted"""
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(sample_content)
        
        logger.info(f"Created sample prompt file: {file_path}")