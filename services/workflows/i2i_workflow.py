"""Image-to-image workflow manager"""
import copy
import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, Any

from services.workflows.base_workflow import BaseWorkflowManager
from models.base_job import BaseJob
from models.i2i_job import I2IJob
from config import (
    I2I_NODE_IMAGE_PATH, I2I_NODE_OUTPUT, I2I_SAMPLER_NODE,
    I2I_WORKFLOW_FILE
)

logger = logging.getLogger(__name__)


class I2IWorkflowManager(BaseWorkflowManager):
    """Workflow manager for image-to-image jobs"""

    def get_workflow_file(self) -> str:
        """Returns path to i2i workflow JSON file"""
        return I2I_WORKFLOW_FILE  # prompts/i2i.json

    def modify_workflow(self, job: BaseJob) -> Dict[str, Any]:
        """Modifies workflow for i2i job"""
        if not isinstance(job, I2IJob):
            raise ValueError(f"Expected I2IJob, got {type(job)}")

        workflow = copy.deepcopy(self.base_workflow)
        params = job.to_workflow_params()

        # Set input image path (handle WSL path conversion if needed)
        image_path = params['image_path']
        image_path_obj = Path(image_path).absolute()
        image_abs_path = str(image_path_obj)

        # If running in WSL, try to convert to a Windows path for ComfyUI on host
        if 'WSL_DISTRO_NAME' in os.environ or 'WSL_INTEROP' in os.environ:
            try:
                result = subprocess.run(['wslpath', '-w', image_abs_path],
                                     capture_output=True, text=True, check=True)
                win_path = result.stdout.strip()
                logger.debug(f"Converted WSL path '{image_abs_path}' to Windows path '{win_path}'")
                image_abs_path = win_path
            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.warning(f"wslpath utility not found or failed. Using original path: {image_abs_path}")

        # Modify nodes
        if str(I2I_NODE_IMAGE_PATH) in workflow:
            workflow[str(I2I_NODE_IMAGE_PATH)]["inputs"]["image"] = image_abs_path

        if str(I2I_NODE_OUTPUT) in workflow:
            workflow[str(I2I_NODE_OUTPUT)]["inputs"]["filename_prefix"] = params['output_prefix']

        if str(I2I_SAMPLER_NODE) in workflow:
            workflow[str(I2I_SAMPLER_NODE)]["inputs"]["cfg"] = params['cfg_value']
            workflow[str(I2I_SAMPLER_NODE)]["inputs"]["seed"] = params['seed']

        logger.info(f"Modified i2i workflow for job {job.job_id}")
        return workflow