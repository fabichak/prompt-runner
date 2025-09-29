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
        elif dir_type == "output":
            # Prompt base directory (entire prompt folder)
            subfolder = prompt_base
        else:
            raise ValueError(f"Unknown directory type: {dir_type}")
        
        # Ensure directory exists and return it
        subfolder.mkdir(parents=True, exist_ok=True)
        return subfolder
     
    def get_video_path(self, promptName: str, job_number: str) -> str:
        """Get path for video file"""
        dir_path = self.get_directory(promptName, "videos")
        return dir_path / f"job_{job_number}"
    
    def get_video_full_path(self, promptName: str, job_number: str) -> str:
        return f"{self.get_video_path(promptName, job_number)}_00001.mp4"
       
    def save_runtime_workflow(self, workflow: Dict[str, Any], promptName: str, job_number:int, job_type:str) -> str:
        logger.debug("saving runtime workflow")
        filename = f"{job_number:03d}_{job_type}.json"
        dir_path = self.get_directory(promptName, "workflows")
        filepath = dir_path / filename
        logger.debug("saving runtime workflow: " + str(filepath.absolute))
        with open(filepath, 'w') as f:
            json.dump(workflow, f, indent=2, default=str, ensure_ascii=False)
        return str(filepath)
        
    def upload_file_to_gcs(self, local_path: str, gcs_dest_path: str) -> bool:
        """Upload a single file to a GCS destination path using gsutil.

        Args:
            local_path: Path to local file to upload
            gcs_dest_path: Full GCS destination (e.g. gs://bucket/folder/file.png)
        """
        try:
            logger.info(f"Trying to upload {local_path} to {gcs_dest_path}")
            local = Path(local_path)
            if not local.exists() or not local.is_file():
                logger.error(f"Local file not found for upload: {local}")
                return False

            cmd = ["gsutil", "cp", str(local), gcs_dest_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                logger.info(f"Uploaded file to {gcs_dest_path}")
                return True
            else:
                logger.error(f"GCS upload failed: {result.stderr}")
                return False
        except FileNotFoundError:
            logger.error("gsutil not found. Install the Google Cloud SDK and run `gcloud init`.")
            return False
        except Exception as e:
            logger.error(f"Error uploading file to GCS: {e}")
            return False