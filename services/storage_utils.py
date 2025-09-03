"""Storage and file management utilities"""
import os
import shutil
import subprocess
import zipfile
import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from config import (
    GCS_BUCKET_PATH, BASE_OUTPUT_DIR
)

logger = logging.getLogger(__name__)


class StorageManager:
    """Handles file operations, storage, and GCS uploads"""
        
    def ensure_directories(self, promptName: str):
        """Create all required directories for a specific prompt"""
        prompt_base = BASE_OUTPUT_DIR / promptName
        directories = [
            prompt_base,
            prompt_base / "videos",
            prompt_base / "workflows"
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured directory exists: {directory}")
    
    def get_directory(self, promptName: str, dir_type: str) -> Path:
        """Get directory path for a specific prompt and type"""
        # Create prompt-specific base directory
        prompt_base = BASE_OUTPUT_DIR / promptName
        
        # Add the subfolder type
        if dir_type == "videos":
            subfolder = prompt_base / "videos"
        elif dir_type == "workflows":
            subfolder = prompt_base / "workflows"    
        else:
            raise ValueError(f"Unknown directory type: {dir_type}")
        
        # Ensure directory exists and return it
        subfolder.mkdir(parents=True, exist_ok=True)
        return subfolder
     
    def get_video_path(self, promptName: str, job_number: int) -> Path:
        """Get path for video file"""
        dir_path = self.get_directory(promptName, "videos")
        return dir_path / f"job_{job_number:03d}"
    
    def get_video_full_path(self, promptName: str, job_number: int) -> Path:
        return f"{self.get_video_path(promptName, job_number)}_00001.mp4"
       
    def save_runtime_workflow(self, workflow: Dict[str, Any], promptName: str, job_number:int, job_type:str) -> str:
        filename = f"{job_number:03d}_{job_type}.json"
        dir_path = self.get_directory(promptName, "workflows")
        filepath = dir_path / filename
        with open(filepath, 'w') as f:
            json.dump(workflow, f, indent=2, default=str)
        return str(filepath)
        
    def cleanup_intermediate_files(self, promptName: str, keep_final: bool = True):
        """Clean up intermediate files after successful completion"""
        directories_to_clean = [
            self.get_directory(promptName, "latents"),
            self.get_directory(promptName, "videos"),
            self.get_directory(promptName, "references"),
            self.get_directory(promptName, "combined")
        ]
        
        for directory in directories_to_clean:
            if directory.exists():
                shutil.rmtree(directory)
                logger.info(f"Cleaned up {directory}")
    
    def zip_and_upload_output(self, promptName: str) -> bool:
        """Zip the 'combined' folder contents and upload to GCS."""
        try:
            video_dir = self.get_directory(promptName, "videos")
            if not video_dir.exists() or not any(f for f in video_dir.rglob('*') if f.is_file()):
                logger.error(f"'combined' directory is empty or does not exist: {video_dir}")
                return False
            
            # Create zip file in the prompt's base directory
            prompt_base = BASE_OUTPUT_DIR / promptName
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_name_base = f"{promptName}_video_{timestamp}"
            zip_path_base = prompt_base / zip_name_base
            
            # Create zip file of the combined directory
            zip_path_str = shutil.make_archive(
                base_name=str(zip_path_base),
                format='zip',
                root_dir=str(video_dir)
            )
            zip_path = Path(zip_path_str)
            logger.info(f"Created zip file: {zip_path}")
            
            # Upload to GCS
            gcs_path = f"{GCS_BUCKET_PATH}{zip_path.name}"
            cmd = ["gsutil", "cp", str(zip_path), gcs_path]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                logger.info(f"Successfully uploaded to {gcs_path}")
                # Clean up local zip
                zip_path.unlink()
                return True
            else:
                logger.error(f"GCS upload failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error in zip and upload: {e}")
            return False
    
    def get_disk_usage(self, promptName: str) -> Dict[str, float]:
        """Get disk usage statistics in GB for a specific prompt"""
        stats = {}
        prompt_base = BASE_OUTPUT_DIR / promptName
        
        for name, subfolder in [
            ("latents", "latents"),
            ("videos", "videos"),
            ("references", "references"),
            ("combined", "combined"),
            ("state", "state"),
            ("total", "")  # Empty string for the prompt base directory
        ]:
            if subfolder:
                path = prompt_base / subfolder
            else:
                path = prompt_base
                
            if path.exists():
                size = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
                stats[name] = size / (1024 ** 3)  # Convert to GB
            else:
                stats[name] = 0.0
        return stats
    
    def check_disk_space(self, promptName: str, required_gb: float = 10.0) -> bool:
        """Check if sufficient disk space is available for prompt operations"""
        try:
            prompt_base = BASE_OUTPUT_DIR / promptName
            # Ensure prompt directory exists for disk usage check
            prompt_base.mkdir(parents=True, exist_ok=True)
            
            stat = shutil.disk_usage(prompt_base)
            available_gb = stat.free / (1024 ** 3)
            if available_gb < required_gb:
                logger.warning(f"Low disk space for prompt '{promptName}': {available_gb:.1f}GB available, {required_gb:.1f}GB required")
                return False
            return True
        except Exception as e:
            logger.error(f"Error checking disk space for prompt '{promptName}': {e}")
            return True  # Assume sufficient space on error  # Assume sufficient space on error  # Assume sufficient space on error