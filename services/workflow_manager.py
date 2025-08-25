"""Workflow modification engine for job configurations"""
import json
import copy
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from models.job import RenderJob, CombineJob
from config import (
    COMBINE_NODE_RESCALE, NODE_HEIGHT, NODE_IMAGE_BATCH_SKIP, NODE_LOAD_VIDEO_PATH,
    NODE_LORA, NODE_MODEL, NODE_REF_IMAGES, NODE_SAMPLES_54, COMBINE_NODE_IMAGE_BATCH,
    NODE_SAVE_LATENT, NODE_FRAMES_VALUE, NODE_LOAD_LATENT, NODE_SAVE_VIDEO_PATH, NODE_VIDEO_COMBINE, COMBINE_NODE_OUTPUT_COMBINE_1,
    NODE_START_FRAME, NODE_PROMPT, NODE_VACE, NODE_VIDEO_DECODE, HIGH_STEPS,COMBINE_NODE_LOAD_VIDEO_COMBINE,
    COMBINE_NODE_VIDEOS, COMBINE_NODE_OUTPUT_COMBINE_N, NODE_WIDTH, RESCALE_FACTOR, STEPS, VIDEO_HEIGHT, VIDEO_WIDTH,
    LOW_LORA, LOW_MODEL
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
        
        # Set model and LoRA (using the LOW configurations as the single default)
        if NODE_LORA in workflow:
            workflow[NODE_LORA]["inputs"]["lora"] = LOW_LORA
        
        if NODE_MODEL in workflow:
            workflow[NODE_MODEL]["inputs"]["model"] = LOW_MODEL
        
        # Set frames configuration
        if NODE_FRAMES_VALUE in workflow:
            workflow[NODE_FRAMES_VALUE]["inputs"]["value"] = job.frames_to_render
        
        if NODE_START_FRAME in workflow:
            workflow[NODE_START_FRAME]["inputs"]["value"] = job.start_frame
        
        # Set video input
        if NODE_LOAD_VIDEO_PATH in workflow:
            workflow[NODE_LOAD_VIDEO_PATH]["inputs"]["video"] = job.video_input_path
        
        # Set dimensions
        if NODE_WIDTH in workflow:
            workflow[NODE_WIDTH]["inputs"]["value"] = VIDEO_WIDTH
        
        if NODE_HEIGHT in workflow:
            workflow[NODE_HEIGHT]["inputs"]["value"] = VIDEO_HEIGHT
        
        # Set seed and sampler settings
        if NODE_SAMPLES_54 in workflow:
            workflow[NODE_SAMPLES_54]["inputs"]["seed"] = job.seed
            workflow[NODE_SAMPLES_54]["inputs"]["start_step"] = 0
            workflow[NODE_SAMPLES_54]["inputs"]["end_step"] = -1
            workflow[NODE_SAMPLES_54]["inputs"]["steps"] = STEPS
        
        # Set reference image if available
        if job.reference_image_path and NODE_REF_IMAGES in workflow:
            workflow[NODE_REF_IMAGES]["inputs"]["image"] = job.reference_image_path
        
        # Set output paths
        if job.video_output_path and NODE_VIDEO_COMBINE in workflow:
            workflow[NODE_VIDEO_COMBINE]["inputs"]["filename_prefix"] = job.video_output_path
        
        if job.next_reference_image_output_path and NODE_SAVE_VIDEO_PATH in workflow:
            workflow[NODE_SAVE_VIDEO_PATH]["inputs"]["path"] = job.next_reference_image_output_path
        
        # Set latent path if needed
        if job.latent_path and NODE_SAVE_LATENT in workflow:
            workflow[NODE_SAVE_LATENT]["inputs"]["file_path"] = job.latent_path
        
        # Set prompts
        self._set_prompts(workflow, job.positive_prompt, job.negative_prompt)
        
        # Save runtime workflow for debugging
        self.storage.save_runtime_workflow(workflow, job.prompt_name, job.job_number, "render")
        logger.info(f"Modified workflow for job #{job.job_number}")
        
        return workflow
    
    def create_combine_workflow(self, combine_job: CombineJob) -> Dict[str, Any]:
        """Create workflow for combining videos
        
        Modifications:
        - Set input video path
        - Set output path
        - Configure rescale factor
        """
        workflow = copy.deepcopy(self.combine_workflow)
        
        # Set current video input
        if COMBINE_NODE_VIDEOS in workflow:
            workflow[COMBINE_NODE_VIDEOS]["inputs"]["video"] = combine_job.input_video_path
        
        # Set rescale factor
        if COMBINE_NODE_RESCALE in workflow:
            workflow[COMBINE_NODE_RESCALE]["inputs"]["rescale_factor"] = RESCALE_FACTOR
        
        # Set output file
        if COMBINE_NODE_OUTPUT_COMBINE_1 in workflow:
            workflow[COMBINE_NODE_OUTPUT_COMBINE_1]["inputs"]["filename_prefix"] = combine_job.output_path
        
        # Save runtime workflow for debugging
        self.storage.save_runtime_workflow(workflow, combine_job.prompt_name, combine_job.combine_number, "combine")
        logger.info(f"Created combine workflow for job #{combine_job.combine_number}")
        
        return workflow
    
    def _set_prompts(self, workflow: Dict[str, Any], positive: str, negative: str):
        """Set positive and negative prompts in workflow"""
        # Find prompt nodes (typically nodes with class_type containing "CLIPTextEncode")
        if NODE_PROMPT in workflow:
            workflow[NODE_PROMPT]["inputs"]["positive_prompt"] = positive
            workflow[NODE_PROMPT]["inputs"]["negative_prompt"] = negative
            logger.debug(f"Set positive and negative prompt in node {NODE_PROMPT}")
    
    def validate_workflow(self, workflow: Dict[str, Any]) -> bool:
        """Validate that a workflow has required nodes and structure"""
        if not workflow:
            logger.error("Workflow is empty")
            return False
        
        # Check that each node has required fields
        for node_id, node in workflow.items():
            if not isinstance(node, dict):
                logger.error(f"Node {node_id} is not a dictionary")
                return False
            if "class_type" not in node:
                logger.warning(f"Node {node_id} missing class_type")
        
        return True