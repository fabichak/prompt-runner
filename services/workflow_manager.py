"""Workflow modification engine for job configurations"""
import json
import copy
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from models.job import RenderJob
from config import (
    NODE_HEIGHT, NODE_LOAD_VIDEO_PATH, NODE_REF_IMAGES, NODE_SAMPLES_54, NODE_FRAMES_VALUE, NODE_VIDEO_COMBINE, 
    NODE_START_FRAME, NODE_PROMPT, NODE_WIDTH, STEPS, VIDEO_HEIGHT, VIDEO_WIDTH
)
from services.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


class WorkflowManager:
    """Manages workflow JSON modifications for render and combine jobs"""
    
    def __init__(self, base_workflow_path: Path, combine_workflow_path: Path):
        self.storage = ServiceFactory.create_storage_manager()
        self.base_workflow = self._load_workflow(base_workflow_path)
        self.combine_workflow = self._load_workflow(combine_workflow_path)
        
        if not self.base_workflow:
            raise ValueError(f"Failed to load base workflow from {base_workflow_path}")
        if not self.combine_workflow:
            raise ValueError(f"Failed to load combine workflow from {combine_workflow_path}")
    
    def _load_workflow(self, path: Path) -> Optional[Dict[str, Any]]:
        """Load workflow JSON from file"""
        try:
            with open(path, 'r') as f:
                workflow = json.load(f)
            logger.info(f"Loaded workflow from {path}")
            return workflow
        except Exception as e:
            logger.error(f"Error loading workflow {path}: {e}")
            return None
    
    def modify_workflow_for_job(self, job: RenderJob) -> Dict[str, Any]:
        """Modify workflow for a render job using prompt.json as the base
        
        Modifications:
        - Set frames to render and start frame
        - Set video input path
        - Set reference image if available
        - Set output paths
        - Set prompts
        - Configure model and LoRA
        """
        workflow = copy.deepcopy(self.base_workflow)
                      
        workflow[NODE_FRAMES_VALUE]["inputs"]["value"] = job.frames_to_render
        workflow[NODE_START_FRAME]["inputs"]["value"] = job.start_frame
        
        workflow[NODE_LOAD_VIDEO_PATH]["inputs"]["video"] = job.video_input_path
        workflow[NODE_REF_IMAGES]["inputs"]["image"] = job.reference_image_path
        
        workflow[NODE_WIDTH]["inputs"]["value"] = VIDEO_WIDTH
        workflow[NODE_HEIGHT]["inputs"]["value"] = VIDEO_HEIGHT
        
        workflow[NODE_SAMPLES_54]["inputs"]["seed"] = job.seed
        workflow[NODE_SAMPLES_54]["inputs"]["start_step"] = 0
        workflow[NODE_SAMPLES_54]["inputs"]["end_step"] = -1
        workflow[NODE_SAMPLES_54]["inputs"]["steps"] = STEPS
                    
        workflow[NODE_VIDEO_COMBINE]["inputs"]["filename_prefix"] = job.video_output_path

        workflow[NODE_PROMPT]["inputs"]["positive_prompt"] = job.positive_prompt
        workflow[NODE_PROMPT]["inputs"]["negative_prompt"] = job.negative_prompt
        
        self.storage.save_runtime_workflow(workflow, job.prompt_name, job.job_number, "render")
        logger.info(f"Modified workflow for job #{job.job_number}")
        
        return workflow
    
    # def create_combine_workflow(self, combine_job: CombineJob) -> Dict[str, Any]:
    #     """Create workflow for combining videos
        
    #     Modifications:
    #     - Set input video path
    #     - Set output path
    #     - Configure rescale factor
    #     """
    #     workflow = copy.deepcopy(self.combine_workflow)
        
    #     # Set current video input
    #     if COMBINE_NODE_VIDEOS in workflow:
    #         workflow[COMBINE_NODE_VIDEOS]["inputs"]["video"] = combine_job.input_video_path
        
    #     # Set rescale factor
    #     if COMBINE_NODE_RESCALE in workflow:
    #         workflow[COMBINE_NODE_RESCALE]["inputs"]["rescale_factor"] = RESCALE_FACTOR
        
    #     # Set output file
    #     if COMBINE_NODE_OUTPUT_COMBINE_1 in workflow:
    #         workflow[COMBINE_NODE_OUTPUT_COMBINE_1]["inputs"]["filename_prefix"] = combine_job.output_path
        
    #     # Save runtime workflow for debugging
    #     self.storage.save_runtime_workflow(workflow, combine_job.prompt_name, combine_job.combine_number, "combine")
    #     logger.info(f"Created combine workflow for job #{combine_job.combine_number}")
        
    #     return workflow