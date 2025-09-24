"""i2i Workflow manager for image-to-image operations"""
import json
import copy
import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

from models.i2i_job import I2IJob
from config import (
    I2I_NODE_IMAGE_PATH, I2I_NODE_OUTPUT, I2I_SAMPLER_NODE
)
from services.storage_utils import StorageManager

logger = logging.getLogger(__name__)


class I2IWorkflowManager:
    """Manages i2i workflow JSON modifications"""
    
    def __init__(self, i2i_workflow_path: Path, storage_manager: StorageManager):
        self.storage = storage_manager
        self.i2i_workflow = self._load_workflow(i2i_workflow_path)
        
        if not self.i2i_workflow:
            raise ValueError(f"Failed to load i2i workflow from {i2i_workflow_path}")
    
    def _load_workflow(self, path: Path) -> Optional[Dict[str, Any]]:
        """Load workflow JSON from file"""
        try:
            with open(path, 'r') as f:
                workflow = json.load(f)
            logger.info(f"Loaded i2i workflow from {path}")
            return workflow
        except Exception as e:
            logger.error(f"Error loading workflow {path}: {e}")
            return None
    
    def modify_workflow_for_i2i_job(self, job: I2IJob) -> Dict[str, Any]:
        """Modify workflow for an i2i job
        
        Modifications:
        - Set input image path
        - Set output filename prefix
        - Set CFG value
        - Set seed
        """
        workflow = copy.deepcopy(self.i2i_workflow)
        
        # Set input image path (absolute path)
        image_path_obj = Path(job.image_path).absolute()
        image_abs_path = str(image_path_obj)

        # If running in WSL, try to convert to a Windows path for ComfyUI on host
        if 'WSL_DISTRO_NAME' in os.environ or 'WSL_INTEROP' in os.environ:
            try:
                # Use wslpath utility to convert the path
                result = subprocess.run(['wslpath', '-w', image_abs_path], capture_output=True, text=True, check=True)
                win_path = result.stdout.strip()
                logger.debug(f"Converted WSL path '{image_abs_path}' to Windows path '{win_path}'")
                image_abs_path = win_path
            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.warning(f"wslpath utility not found or failed. Using original path: {image_abs_path}")


        #workflow["343"]["inputs"]["text"] = job.positive
       # workflow["349"]["inputs"]["text"] = job.negative
        workflow[I2I_NODE_IMAGE_PATH]["inputs"]["image"] = image_abs_path
        
        # Set output filename
        workflow[I2I_NODE_OUTPUT]["inputs"]["filename_prefix"] = job.output_filename
        workflow["373"]["inputs"]["filename_prefix"] = job.output_filename + "-cm"
        
        
        workflow[I2I_SAMPLER_NODE]["inputs"]["cfg"] = job.cfg_value
        workflow[I2I_SAMPLER_NODE]["inputs"]["seed"] = job.seed
        
        self.storage.save_runtime_workflow(workflow, job.job_id, 1, "i2i")
        logger.info(f"Modified workflow for i2i job: {job.job_id}")
        
        return workflow