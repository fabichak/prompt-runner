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
    GCS_BUCKET_PATH, BASE_OUTPUT_DIR, LATENTS_DIR, VIDEOS_DIR,
    REFERENCES_DIR, COMBINED_DIR, FINAL_DIR, STATE_DIR
)

logger = logging.getLogger(__name__)


class StorageManager:
    """Handles file operations, storage, and GCS uploads"""
    
    def __init__(self):
        self.ensure_directories()
    
    def ensure_directories(self):
        """Create all required directories"""
        directories = [
            BASE_OUTPUT_DIR,
            LATENTS_DIR,
            VIDEOS_DIR,
            REFERENCES_DIR,
            COMBINED_DIR,
            FINAL_DIR,
            STATE_DIR
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured directory exists: {directory}")
    
    def get_video_directory(self, video_name: str, dir_type: str) -> Path:
        """Get directory path for a specific video and type"""
        if dir_type == "latents":
            base = LATENTS_DIR
        elif dir_type == "videos":
            base = VIDEOS_DIR
        elif dir_type == "references":
            base = REFERENCES_DIR
        elif dir_type == "combined":
            base = COMBINED_DIR
        elif dir_type == "final":
            base = FINAL_DIR
        else:
            raise ValueError(f"Unknown directory type: {dir_type}")
        
        video_dir = base / video_name
        video_dir.mkdir(parents=True, exist_ok=True)
        return video_dir
    
    def get_latent_path(self, video_name: str, job_number: int) -> Path:
        """Get path for latent file"""
        dir_path = self.get_video_directory(video_name, "latents")
        return dir_path / f"job_{job_number:03d}.latent"
    
    def get_video_path(self, video_name: str, job_number: int) -> Path:
        """Get path for video file"""
        dir_path = self.get_video_directory(video_name, "videos")
        return dir_path / f"job_{job_number:03d}.mp4"
    
    def get_reference_path(self, video_name: str, job_number: int) -> Path:
        """Get path for reference image"""
        dir_path = self.get_video_directory(video_name, "references")
        return dir_path / f"job_{job_number:03d}_ref.png"
    
    def get_combined_path(self, video_name: str, stage: int) -> Path:
        """Get path for combined video at a specific stage"""
        dir_path = self.get_video_directory(video_name, "combined")
        return dir_path / f"combined_{stage:03d}.mp4"
    
    def get_final_path(self, video_name: str) -> Path:
        """Get path for final output video"""
        dir_path = self.get_video_directory(video_name, "final")
        return dir_path / f"{video_name}_final.mp4"
    
    def save_state(self, state_name: str, data: Dict[str, Any]):
        """Save job state for recovery"""
        state_file = STATE_DIR / f"{state_name}.json"
        with open(state_file, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        logger.info(f"Saved state to {state_file}")
    
    def load_state(self, state_name: str) -> Optional[Dict[str, Any]]:
        """Load job state for recovery"""
        state_file = STATE_DIR / f"{state_name}.json"
        if not state_file.exists():
            return None
        
        try:
            with open(state_file, 'r') as f:
                data = json.load(f)
            logger.info(f"Loaded state from {state_file}")
            return data
        except Exception as e:
            logger.error(f"Error loading state: {e}")
            return None
    
    def clear_state(self, state_name: str):
        """Clear saved state after successful completion"""
        state_file = STATE_DIR / f"{state_name}.json"
        if state_file.exists():
            state_file.unlink()
            logger.info(f"Cleared state file {state_file}")
    
    def cleanup_intermediate_files(self, video_name: str, keep_final: bool = True):
        """Clean up intermediate files after successful completion"""
        directories_to_clean = [
            self.get_video_directory(video_name, "latents"),
            self.get_video_directory(video_name, "videos"),
            self.get_video_directory(video_name, "references"),
            self.get_video_directory(video_name, "combined")
        ]
        
        for directory in directories_to_clean:
            if directory.exists():
                shutil.rmtree(directory)
                logger.info(f"Cleaned up {directory}")
        
        if not keep_final:
            final_dir = self.get_video_directory(video_name, "final")
            if final_dir.exists():
                shutil.rmtree(final_dir)
    
    def copy_from_comfyui_output(self, source_path: Path, dest_path: Path) -> bool:
        """Copy file from ComfyUI output to our directory structure"""
        try:
            if source_path.exists():
                shutil.copy2(source_path, dest_path)
                logger.debug(f"Copied {source_path} to {dest_path}")
                return True
            else:
                logger.warning(f"Source file not found: {source_path}")
                return False
        except Exception as e:
            logger.error(f"Error copying file: {e}")
            return False
    
    def zip_and_upload_output(self, video_name: str) -> bool:
        """Zip final output and upload to GCS"""
        try:
            final_video = self.get_final_path(video_name)
            if not final_video.exists():
                logger.error(f"Final video not found: {final_video}")
                return False
            
            # Create zip file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_name = f"{video_name}_{timestamp}.zip"
            zip_path = FINAL_DIR / zip_name
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(final_video, final_video.name)
                logger.info(f"Created zip file: {zip_path}")
            
            # Upload to GCS
            gcs_path = f"{GCS_BUCKET_PATH}{zip_name}"
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
    
    def get_disk_usage(self) -> Dict[str, float]:
        """Get disk usage statistics in GB"""
        stats = {}
        for name, path in [
            ("latents", LATENTS_DIR),
            ("videos", VIDEOS_DIR),
            ("references", REFERENCES_DIR),
            ("combined", COMBINED_DIR),
            ("final", FINAL_DIR),
            ("total", BASE_OUTPUT_DIR)
        ]:
            if path.exists():
                size = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
                stats[name] = size / (1024 ** 3)  # Convert to GB
        return stats
    
    def check_disk_space(self, required_gb: float = 10.0) -> bool:
        """Check if sufficient disk space is available"""
        try:
            stat = shutil.disk_usage(BASE_OUTPUT_DIR)
            available_gb = stat.free / (1024 ** 3)
            if available_gb < required_gb:
                logger.warning(f"Low disk space: {available_gb:.1f}GB available, {required_gb:.1f}GB required")
                return False
            return True
        except Exception as e:
            logger.error(f"Error checking disk space: {e}")
            return True  # Assume sufficient space on error