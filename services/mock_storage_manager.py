"""
Mock Storage Manager for dry-run mode - simulates GCS uploads and maintains local file structure
"""
import json
import logging
import shutil
import zipfile
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from services.dry_run_manager import dry_run_manager

logger = logging.getLogger(__name__)


class MockStorageManager:
    """Mock storage manager that simulates GCS operations and maintains local file structure"""
    
    def __init__(self):
        # Use the same directory structure as real StorageManager for consistency
        from config import (
            BASE_OUTPUT_DIR, LATENTS_DIR, VIDEOS_DIR,
            REFERENCES_DIR, COMBINED_DIR, FINAL_DIR, STATE_DIR
        )
        
        self.base_output_dir = BASE_OUTPUT_DIR
        self.latents_dir = LATENTS_DIR
        self.videos_dir = VIDEOS_DIR
        self.references_dir = REFERENCES_DIR
        self.combined_dir = COMBINED_DIR
        self.final_dir = FINAL_DIR
        self.state_dir = STATE_DIR
        
        # Track simulated operations
        self.simulated_uploads = []
        self.simulated_copies = []
        
        logger.info("🗄️ MockStorageManager initialized")
    
    def ensure_directories(self):
        """Create all required directories (same as real implementation)"""
        directories = [
            self.base_output_dir,
            self.latents_dir,
            self.videos_dir,
            self.references_dir,
            self.combined_dir,
            self.final_dir,
            self.state_dir
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            logger.debug(f"[DRY-RUN] Ensured directory exists: {directory}")
    
    def get_video_directory(self, video_name: str, dir_type: str) -> Path:
        """Get directory path for a specific video and type (same as real implementation)"""
        if dir_type == "latents":
            base = self.latents_dir
        elif dir_type == "videos":
            base = self.videos_dir
        elif dir_type == "references":
            base = self.references_dir
        elif dir_type == "combined":
            base = self.combined_dir
        elif dir_type == "final":
            base = self.final_dir
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
        """Save job state for recovery (same as real implementation)"""
        state_file = self.state_dir / f"{state_name}.json"
        
        # Add dry-run metadata
        data["dry_run_metadata"] = {
            "is_dry_run": True,
            "saved_at": datetime.now().isoformat(),
            "temp_directory": str(dry_run_manager.temp_dir) if dry_run_manager.temp_dir else None
        }
        
        with open(state_file, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        logger.info(f"💾 [DRY-RUN] Saved state to {state_file}")
    
    def load_state(self, state_name: str) -> Optional[Dict[str, Any]]:
        """Load job state for recovery"""
        state_file = self.state_dir / f"{state_name}.json"
        if not state_file.exists():
            logger.info(f"[DRY-RUN] No state file found: {state_file}")
            return None
        
        try:
            with open(state_file, 'r') as f:
                data = json.load(f)
            
            # Check if this was a dry-run state
            if data.get("dry_run_metadata", {}).get("is_dry_run"):
                logger.info(f"📂 [DRY-RUN] Loaded dry-run state from {state_file}")
            else:
                logger.info(f"📂 [DRY-RUN] Loaded regular state from {state_file}")
            
            return data
        except Exception as e:
            logger.error(f"[DRY-RUN] Error loading state: {e}")
            return None
    
    def clear_state(self, state_name: str):
        """Clear saved state after successful completion"""
        state_file = self.state_dir / f"{state_name}.json"
        if state_file.exists():
            state_file.unlink()
            logger.info(f"🗑️ [DRY-RUN] Cleared state file {state_file}")
    
    def cleanup_intermediate_files(self, video_name: str, keep_final: bool = True):
        """Simulate cleaning up intermediate files"""
        directories_to_clean = [
            self.get_video_directory(video_name, "latents"),
            self.get_video_directory(video_name, "videos"),
            self.get_video_directory(video_name, "references"),
            self.get_video_directory(video_name, "combined")
        ]
        
        simulated_cleanup = {
            "video_name": video_name,
            "directories_cleaned": [],
            "keep_final": keep_final,
            "timestamp": datetime.now().isoformat()
        }
        
        for directory in directories_to_clean:
            if directory.exists():
                # In dry-run, we simulate cleanup but don't actually delete
                file_count = len(list(directory.rglob('*')))
                simulated_cleanup["directories_cleaned"].append({
                    "path": str(directory),
                    "files_count": file_count
                })
                logger.info(f"🧹 [DRY-RUN] Simulated cleanup of {directory} ({file_count} files)")
        
        if not keep_final:
            final_dir = self.get_video_directory(video_name, "final")
            if final_dir.exists():
                file_count = len(list(final_dir.rglob('*')))
                simulated_cleanup["directories_cleaned"].append({
                    "path": str(final_dir),
                    "files_count": file_count
                })
                logger.info(f"🧹 [DRY-RUN] Simulated cleanup of final directory {final_dir}")
        
        # Save cleanup simulation details
        if dry_run_manager.temp_dir:
            cleanup_file = dry_run_manager.temp_dir / "state" / f"cleanup_{video_name}.json"
            with open(cleanup_file, 'w') as f:
                json.dump(simulated_cleanup, f, indent=2)
    
    def copy_from_comfyui_output(self, source_path: Path, dest_path: Path) -> bool:
        """Simulate copying file from ComfyUI output to our directory structure"""
        try:
            # Create a dummy file to simulate the copy operation
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create a small dummy file instead of actually copying
            with open(dest_path, 'w') as f:
                f.write(f"# DRY-RUN SIMULATED FILE\n")
                f.write(f"# Original source: {source_path}\n")
                f.write(f"# Simulated at: {datetime.now().isoformat()}\n")
                f.write(f"# This file represents: {dest_path.suffix} content\n")
            
            copy_info = {
                "source": str(source_path),
                "destination": str(dest_path),
                "timestamp": datetime.now().isoformat(),
                "simulated": True
            }
            self.simulated_copies.append(copy_info)
            
            logger.info(f"📁 [DRY-RUN] Simulated copy {source_path.name} → {dest_path}")
            return True
            
        except Exception as e:
            logger.error(f"[DRY-RUN] Error simulating file copy: {e}")
            return False
    
    def zip_and_upload_output(self, video_name: str) -> bool:
        """Simulate zipping final output and uploading to GCS"""
        try:
            final_video = self.get_final_path(video_name)
            
            # Create the final video file if it doesn't exist
            if not final_video.exists():
                final_video.parent.mkdir(parents=True, exist_ok=True)
                with open(final_video, 'w') as f:
                    f.write(f"# DRY-RUN SIMULATED FINAL VIDEO\n")
                    f.write(f"# Video name: {video_name}\n")
                    f.write(f"# Created at: {datetime.now().isoformat()}\n")
            
            # Simulate zip creation
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_name = f"{video_name}_{timestamp}.zip"
            zip_path = self.final_dir / zip_name
            
            # Create actual zip for demonstration (small file)
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(final_video, final_video.name)
            
            # Simulate GCS upload
            from config import GCS_BUCKET_PATH
            gcs_path = f"{GCS_BUCKET_PATH}{zip_name}"
            
            upload_info = {
                "video_name": video_name,
                "zip_name": zip_name,
                "local_zip_path": str(zip_path),
                "gcs_path": gcs_path,
                "timestamp": datetime.now().isoformat(),
                "simulated": True,
                "file_size": zip_path.stat().st_size if zip_path.exists() else 0
            }
            
            self.simulated_uploads.append(upload_info)
            
            logger.info(f"☁️ [DRY-RUN] Simulated GCS upload: {zip_name} → {gcs_path}")
            
            # Keep the zip file for inspection
            logger.info(f"📦 [DRY-RUN] Created demonstration zip: {zip_path}")
            
            return True
                
        except Exception as e:
            logger.error(f"[DRY-RUN] Error in simulated zip and upload: {e}")
            return False
    
    def get_disk_usage(self) -> Dict[str, float]:
        """Get disk usage statistics in GB (same as real implementation)"""
        stats = {}
        for name, path in [
            ("latents", self.latents_dir),
            ("videos", self.videos_dir),
            ("references", self.references_dir),
            ("combined", self.combined_dir),
            ("final", self.final_dir),
            ("total", self.base_output_dir)
        ]:
            if path.exists():
                size = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
                stats[name] = size / (1024 ** 3)  # Convert to GB
        
        # Add dry-run specific stats
        if dry_run_manager.temp_dir and dry_run_manager.temp_dir.exists():
            temp_size = sum(f.stat().st_size for f in dry_run_manager.temp_dir.rglob('*') if f.is_file())
            stats["dry_run_temp"] = temp_size / (1024 ** 3)
        
        return stats
    
    def check_disk_space(self, required_gb: float = 10.0) -> bool:
        """Check if sufficient disk space is available"""
        try:
            stat = shutil.disk_usage(self.base_output_dir)
            available_gb = stat.free / (1024 ** 3)
            if available_gb < required_gb:
                logger.warning(f"[DRY-RUN] Low disk space: {available_gb:.1f}GB available, {required_gb:.1f}GB required")
                return False
            logger.info(f"💽 [DRY-RUN] Disk space check: {available_gb:.1f}GB available")
            return True
        except Exception as e:
            logger.error(f"[DRY-RUN] Error checking disk space: {e}")
            return True  # Assume sufficient space on error
    
    def get_simulation_summary(self) -> Dict[str, Any]:
        """Get summary of all simulated operations"""
        return {
            "simulated_uploads": self.simulated_uploads,
            "simulated_copies": self.simulated_copies,
            "total_uploads": len(self.simulated_uploads),
            "total_copies": len(self.simulated_copies)
        }