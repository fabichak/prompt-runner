"""
Dry-run mode manager for comprehensive simulation without external connections
"""
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List, Union
from datetime import datetime

from config import BASE_OUTPUT_DIR
from models.job import RenderJob, CombineJob

logger = logging.getLogger(__name__)


class DryRunManager:
    """Manages dry-run mode configuration and temp file generation"""
    
    def __init__(self):
        self.is_dry_run = False
        self.temp_dir = None
        self.workflow_counter = 0
        self.generated_workflows = []
        
    def enable_dry_run(self):
        """Enable dry-run mode and create temp directory"""
        self.is_dry_run = True
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.temp_dir = Path(f"temp_dry_run_{timestamp}")
        self.temp_dir.mkdir(exist_ok=True)
        
        # Create subdirectories for organization
        (self.temp_dir / "workflows").mkdir(exist_ok=True)
        (self.temp_dir / "render_jobs").mkdir(exist_ok=True)
        (self.temp_dir / "combine_jobs").mkdir(exist_ok=True)
        (self.temp_dir / "state").mkdir(exist_ok=True)
        
        logger.info(f"🔄 Dry-run mode enabled - temp directory: {self.temp_dir}")
        
    def save_workflow(self, workflow: Dict[str, Any], job_info: Dict[str, Any]) -> str:
        """Save workflow JSON to temp folder and return filename"""
        if not self.is_dry_run:
            return ""
            
        self.workflow_counter += 1
        filename = f"workflow_{self.workflow_counter:03d}_{job_info.get('type', 'unknown')}.json"
        filepath = self.temp_dir / "workflows" / filename
        
        # Create comprehensive workflow metadata
        workflow_metadata = {
            "workflow_id": self.workflow_counter,
            "timestamp": datetime.now().isoformat(),
            "job_info": job_info,
            "workflow": workflow,
            "original_nodes_count": len(workflow),
            "modifications_applied": job_info.get("modifications", [])
        }
        
        with open(filepath, 'w') as f:
            json.dump(workflow_metadata, f, indent=2)
            
        self.generated_workflows.append({
            "filename": filename,
            "filepath": str(filepath),
            "job_info": job_info,
            "timestamp": datetime.now().isoformat()
        })
        
        logger.info(f"📝 Saved workflow: {filename} ({job_info.get('type', 'unknown')} job)")
        return filename
        
    def save_job_plan(self, job_type: str, jobs: List[Union[RenderJob, CombineJob]], metadata: Dict[str, Any]):
        """Save job execution plan to temp folder"""
        if not self.is_dry_run:
            return
            
        timestamp = datetime.now().strftime("%H%M%S")
        filename = f"{job_type}_jobs_{timestamp}.json"
        filepath = self.temp_dir / f"{job_type}_jobs" / filename
        
        job_plan = {
            "job_type": job_type,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata,
            "total_jobs": len(jobs),
            "jobs": []
        }
        
        for job in jobs:
            job_plan["jobs"].append({
                "job_id": getattr(job, 'job_id', str(uuid.uuid4())),
                "job_number": getattr(job, 'job_number', 0),
                "job_type": str(getattr(job, 'job_type', job_type)),
                "frames_to_render": getattr(job, 'frames_to_render', 0),
                "start_frame": getattr(job, 'start_frame', 0),
                "video_name": getattr(job, 'video_name', 'unknown'),
                "positive_prompt": getattr(job, 'positive_prompt', ''),
                "negative_prompt": getattr(job, 'negative_prompt', ''),
                "latent_input_path": getattr(job, 'latent_input_path', None),
                "reference_image_path": getattr(job, 'reference_image_path', None)
            })
            
        with open(filepath, 'w') as f:
            json.dump(job_plan, f, indent=2)
            
        logger.info(f"📋 Saved {job_type} job plan: {filename} ({len(jobs)} jobs)")
        
    def get_summary(self) -> Dict[str, Any]:
        """Get dry-run execution summary"""
        if not self.is_dry_run:
            return {}
            
        return {
            "dry_run_enabled": True,
            "temp_directory": str(self.temp_dir),
            "workflows_generated": len(self.generated_workflows),
            "workflow_details": self.generated_workflows,
            "execution_time": datetime.now().isoformat()
        }
        
    def cleanup(self):
        """Clean up temp directory (optional)"""
        if self.temp_dir and self.temp_dir.exists():
            logger.info(f"🧹 Temp directory preserved at: {self.temp_dir}")
            # Optionally remove: shutil.rmtree(self.temp_dir)


# Global dry-run manager instance
dry_run_manager = DryRunManager()


def is_dry_run() -> bool:
    """Check if we're in dry-run mode"""
    return dry_run_manager.is_dry_run or os.getenv('DRY_RUN', '').lower() in ('true', '1', 'yes')


def enable_dry_run():
    """Enable dry-run mode"""
    dry_run_manager.enable_dry_run()