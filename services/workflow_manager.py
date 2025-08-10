"""Workflow modification engine for HIGH/LOW job configurations"""
import json
import copy
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

from models.job import RenderJob, CombineJob, JobType
from config import (
    HIGH_LORA, LOW_LORA, HIGH_MODEL, LOW_MODEL,
    NODE_LORA, NODE_MODEL, NODE_REF_IMAGES, NODE_SAMPLES_54,
    NODE_LATENT_365, NODE_SAMPLES_341, NODE_FRAMES_VALUE,
    NODE_START_FRAME, NODE_VIDEO_OUTPUT,
    COMBINE_NODE_VIDEOS, COMBINE_NODE_IMAGE2, COMBINE_NODE_IMAGES
)

logger = logging.getLogger(__name__)


class WorkflowManager:
    """Manages workflow JSON modifications for different job types"""
    
    def __init__(self, base_workflow_path: Path, combine_workflow_path: Path):
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
    
    def modify_for_high_job(self, job: RenderJob) -> Dict[str, Any]:
        """Modify workflow for HIGH noise job
        
        Modifications:
        - Set LoRA to HIGH model
        - Set model to HIGH noise model
        - Delete/configure reference images based on job number
        - Delete samples nodes (54, 341)
        - Set frames and start frame
        """
        workflow = copy.deepcopy(self.base_workflow)
        
        # Set LoRA to HIGH model (Node 309 and sub-node 298)
        if NODE_LORA in workflow:
            if "inputs" in workflow[NODE_LORA]:
                workflow[NODE_LORA]["inputs"]["lora_name"] = HIGH_LORA
            # Handle sub-node if it exists
            if "298" in workflow[NODE_LORA]:
                workflow[NODE_LORA]["298"]["inputs"]["lora_name"] = HIGH_LORA
        
        # Set model to HIGH noise model
        if NODE_MODEL in workflow:
            if "inputs" in workflow[NODE_MODEL]:
                workflow[NODE_MODEL]["inputs"]["gguf_name"] = HIGH_MODEL
        
        # Handle reference images (delete for jobs 1-2, set for jobs 3+)
        if job.job_number <= 2:
            # Delete reference images node for first two jobs
            if NODE_REF_IMAGES in workflow:
                del workflow[NODE_REF_IMAGES]
                logger.debug(f"Deleted reference images node for job {job.job_number}")
        else:
            # Set reference image path for jobs 3+
            if NODE_REF_IMAGES in workflow and job.reference_image_path:
                if "inputs" in workflow[NODE_REF_IMAGES]:
                    workflow[NODE_REF_IMAGES]["inputs"]["image"] = job.reference_image_path
                    logger.debug(f"Set reference image: {job.reference_image_path}")
        
        # Delete samples nodes for HIGH jobs
        for node_id in [NODE_SAMPLES_54, NODE_SAMPLES_341]:
            if node_id in workflow:
                del workflow[node_id]
                logger.debug(f"Deleted samples node {node_id} for HIGH job")
        
        # Set frames to render
        if NODE_FRAMES_VALUE in workflow:
            if "inputs" in workflow[NODE_FRAMES_VALUE]:
                workflow[NODE_FRAMES_VALUE]["inputs"]["value"] = job.frames_to_render
        
        # Set start frame (skip-n-frames)
        if NODE_START_FRAME in workflow:
            if "inputs" in workflow[NODE_START_FRAME]:
                workflow[NODE_START_FRAME]["inputs"]["start_frame"] = job.start_frame
        
        # Set prompts
        self._set_prompts(workflow, job.positive_prompt, job.negative_prompt)
        
        logger.info(f"Modified workflow for HIGH job #{job.job_number}")
        return workflow
    
    def modify_for_low_job(self, job: RenderJob) -> Dict[str, Any]:
        """Modify workflow for LOW noise job
        
        Modifications:
        - Set LoRA to LOW model
        - Set model to LOW noise model
        - Delete latent node (365)
        - Set latent input from previous HIGH job
        - Set frames and start frame
        """
        workflow = copy.deepcopy(self.base_workflow)
        
        # Set LoRA to LOW model
        if NODE_LORA in workflow:
            if "inputs" in workflow[NODE_LORA]:
                workflow[NODE_LORA]["inputs"]["lora_name"] = LOW_LORA
            # Handle sub-node if it exists
            if "298" in workflow[NODE_LORA]:
                workflow[NODE_LORA]["298"]["inputs"]["lora_name"] = LOW_LORA
        
        # Set model to LOW noise model
        if NODE_MODEL in workflow:
            if "inputs" in workflow[NODE_MODEL]:
                workflow[NODE_MODEL]["inputs"]["gguf_name"] = LOW_MODEL
        
        # Delete latent node for LOW jobs
        if NODE_LATENT_365 in workflow:
            del workflow[NODE_LATENT_365]
            logger.debug(f"Deleted latent node {NODE_LATENT_365} for LOW job")
        
        # Set latent input from previous HIGH job
        if job.latent_input_path:
            # Find the node that needs the latent input
            # This will depend on your specific workflow structure
            # You may need to adjust based on your actual workflow
            for node_id, node in workflow.items():
                if "inputs" in node and "latent" in node["inputs"]:
                    # Set the latent input path
                    node["inputs"]["latent"] = job.latent_input_path
                    logger.debug(f"Set latent input in node {node_id}: {job.latent_input_path}")
                    break
        
        # Set frames to render
        if NODE_FRAMES_VALUE in workflow:
            if "inputs" in workflow[NODE_FRAMES_VALUE]:
                workflow[NODE_FRAMES_VALUE]["inputs"]["value"] = job.frames_to_render
        
        # Set start frame
        if NODE_START_FRAME in workflow:
            if "inputs" in workflow[NODE_START_FRAME]:
                workflow[NODE_START_FRAME]["inputs"]["start_frame"] = job.start_frame
        
        # Set prompts
        self._set_prompts(workflow, job.positive_prompt, job.negative_prompt)
        
        logger.info(f"Modified workflow for LOW job #{job.job_number}")
        return workflow
    
    def create_combine_workflow(self, combine_job: CombineJob) -> Dict[str, Any]:
        """Create workflow for combining videos
        
        Modifications:
        - Set input video path (node 25)
        - Handle previous combined video (node 30)
        - Configure for first vs subsequent combines (node 14)
        """
        workflow = copy.deepcopy(self.combine_workflow)
        
        # Set current video input (node 25)
        if COMBINE_NODE_VIDEOS in workflow:
            if "inputs" in workflow[COMBINE_NODE_VIDEOS]:
                workflow[COMBINE_NODE_VIDEOS]["inputs"]["videos"] = combine_job.input_video_path
                logger.debug(f"Set input video: {combine_job.input_video_path}")
        
        # Handle previous combined video
        if combine_job.combine_number == 1:
            # First combine - remove image_2 node
            if COMBINE_NODE_IMAGE2 in workflow:
                del workflow[COMBINE_NODE_IMAGE2]
                logger.debug("Removed image_2 node for first combine")
            
            # Set node 14 inputs.images to [33, 0] for first combine
            if COMBINE_NODE_IMAGES in workflow:
                if "inputs" in workflow[COMBINE_NODE_IMAGES]:
                    workflow[COMBINE_NODE_IMAGES]["inputs"]["images"] = [33, 0]
                    logger.debug("Set images input to [33, 0] for first combine")
        else:
            # Subsequent combines - set previous combined video
            if COMBINE_NODE_IMAGE2 in workflow and combine_job.previous_combined_path:
                if "inputs" in workflow[COMBINE_NODE_IMAGE2]:
                    workflow[COMBINE_NODE_IMAGE2]["inputs"]["image_2"] = combine_job.previous_combined_path
                    logger.debug(f"Set previous combined: {combine_job.previous_combined_path}")
        
        # Set output path
        self._set_output_path(workflow, combine_job.output_path)
        
        logger.info(f"Created combine workflow for job #{combine_job.combine_number}")
        return workflow
    
    def _set_prompts(self, workflow: Dict[str, Any], positive: str, negative: str):
        """Set positive and negative prompts in workflow"""
        # Find prompt nodes (typically nodes with class_type containing "CLIPTextEncode")
        for node_id, node in workflow.items():
            if "class_type" in node and "CLIPTextEncode" in node.get("class_type", ""):
                if "inputs" in node:
                    # Determine if this is positive or negative based on connections or naming
                    # This is a simplified approach - adjust based on your workflow
                    if "positive" in str(node).lower() or node_id in ["6", "7"]:  # Common positive prompt nodes
                        node["inputs"]["text"] = positive
                        logger.debug(f"Set positive prompt in node {node_id}")
                    elif "negative" in str(node).lower() or node_id in ["8", "9"]:  # Common negative prompt nodes
                        node["inputs"]["text"] = negative
                        logger.debug(f"Set negative prompt in node {node_id}")
    
    def _set_output_path(self, workflow: Dict[str, Any], output_path: str):
        """Set output path in workflow"""
        # Find output nodes (typically SaveVideo, SaveImage, etc.)
        for node_id, node in workflow.items():
            if "class_type" in node:
                class_type = node["class_type"]
                if any(save_type in class_type for save_type in ["SaveVideo", "SaveImage", "VideoSave"]):
                    if "inputs" in node:
                        node["inputs"]["filename_prefix"] = Path(output_path).stem
                        logger.debug(f"Set output path in node {node_id}: {output_path}")
    
    def validate_workflow(self, workflow: Dict[str, Any]) -> bool:
        """Validate that a workflow has required nodes and structure"""
        required_nodes = []  # Add any critical nodes that must exist
        
        for node_id in required_nodes:
            if node_id not in workflow:
                logger.error(f"Required node {node_id} not found in workflow")
                return False
        
        # Check for basic structure
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
    
    def get_output_nodes(self, workflow: Dict[str, Any]) -> List[str]:
        """Get list of output node IDs from workflow"""
        output_nodes = []
        
        for node_id, node in workflow.items():
            if "class_type" in node:
                class_type = node["class_type"]
                if any(save_type in class_type for save_type in ["SaveVideo", "SaveImage", "SaveLatent"]):
                    output_nodes.append(node_id)
        
        return output_nodes