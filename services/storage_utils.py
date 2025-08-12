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
        
    def ensure_directories(self, promptName: str):
        """Create all required directories for a specific prompt"""
        prompt_base = BASE_OUTPUT_DIR / promptName
        directories = [
            prompt_base,
            prompt_base / "latents",
            prompt_base / "videos",
            prompt_base / "references", 
            prompt_base / "combined",
            prompt_base / "final",
            prompt_base / "state"
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured directory exists: {directory}")
    
    def get_directory(self, promptName: str, dir_type: str) -> Path:
        """Get directory path for a specific prompt and type"""
        # Create prompt-specific base directory
        prompt_base = BASE_OUTPUT_DIR / promptName
        
        # Add the subfolder type
        if dir_type == "latents":
            subfolder = prompt_base / "latents"
        elif dir_type == "videos":
            subfolder = prompt_base / "videos"
        elif dir_type == "references":
            subfolder = prompt_base / "references"
        elif dir_type == "combined":
            subfolder = prompt_base / "combined"
        elif dir_type == "final":
            subfolder = prompt_base / "final"
        else:
            raise ValueError(f"Unknown directory type: {dir_type}")
        
        # Ensure directory exists and return it
        subfolder.mkdir(parents=True, exist_ok=True)
        return subfolder
    
    def get_latent_path(self, promptName: str, job_number: int) -> Path:
        """Get path for latent file"""
        dir_path = self.get_directory(promptName, "latents")
        return dir_path / f"job_{job_number:03d}.latent"
    
    def get_video_path(self, promptName: str, job_number: int) -> Path:
        """Get path for video file"""
        dir_path = self.get_directory(promptName, "videos")
        return dir_path / f"job_{job_number:03d}"
    
    def get_video_full_path(self, promptName: str, job_number: int) -> Path:
        return f"{self.get_video_path(promptName, job_number)}_00001.mp4"
    
    def get_reference_path(self, promptName: str, job_number: int) -> Path:
        """Get path for reference image"""
        dir_path = self.get_directory(promptName, "references")
        return dir_path / f"job_{job_number:03d}_ref.png"
    
    def get_combined_path(self, promptName: str, stage: int) -> Path:
        """Get path for combined video at a specific stage"""
        dir_path = self.get_directory(promptName, "combined")
        return dir_path / f"combined_{stage:03d}.mp4"
    
    def get_combined_full_path(self, promptName: str, job_number: int) -> Path:
        return f"{self.get_combined_path(promptName, job_number)}_00001.mp4"
    
    def get_final_path(self, promptName: str) -> Path:
        """Get path for final output video"""
        dir_path = self.get_directory(promptName, "final")
        return dir_path / f"{promptName}_final.mp4"
    
    def save_state(self, promptName: str, state_name: str, data: Dict[str, Any]):
        """Save job state for recovery"""
        prompt_base = BASE_OUTPUT_DIR / promptName
        state_dir = prompt_base / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        
        state_file = state_dir / f"state.json"
        with open(state_file, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        logger.info(f"Saved state to {state_file}")
    
    def load_state(self, promptName: str, state_name: str) -> Optional[Dict[str, Any]]:
        """Load job state for recovery"""
        prompt_base = BASE_OUTPUT_DIR / promptName
        state_file = prompt_base / "state" / f"state.json"
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
    
    def clear_state(self, promptName: str, state_name: str):
        """Clear saved state after successful completion"""
        prompt_base = BASE_OUTPUT_DIR / promptName
        state_file = prompt_base / "state" / f"{state_name}.json"
        if state_file.exists():
            state_file.unlink()
            logger.info(f"Cleared state file {state_file}")
    
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
        
        if not keep_final:
            final_dir = self.get_directory(promptName, "final")
            if final_dir.exists():
                shutil.rmtree(final_dir)
    
    def zip_and_upload_output(self, promptName: str) -> bool:
        """Zip final output and upload to GCS"""
        try:
            final_video = self.get_final_path(promptName)
            if not final_video.exists():
                logger.error(f"Final video not found: {final_video}")
                return False
            
            # Create zip file in the prompt's final directory
            prompt_base = BASE_OUTPUT_DIR / promptName
            final_dir = prompt_base / "final"
            final_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_name = f"{promptName}_{timestamp}.zip"
            zip_path = final_dir / zip_name
            
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
    
    def get_disk_usage(self, promptName: str) -> Dict[str, float]:
        """Get disk usage statistics in GB for a specific prompt"""
        stats = {}
        prompt_base = BASE_OUTPUT_DIR / promptName
        
        for name, subfolder in [
            ("latents", "latents"),
            ("videos", "videos"),
            ("references", "references"),
            ("combined", "combined"),
            ("final", "final"),
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