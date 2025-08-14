"""Workflow modification engine for HIGH/LOW job configurations"""
import json
import copy
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

from models.job import RenderJob, CombineJob, JobType
from services.dry_run_manager import is_dry_run, dry_run_manager
from config import (
    COMBINE_NODE_RESCALE, HIGH_LORA, LOW_LORA, HIGH_MODEL, LOW_MODEL, NODE_HEIGHT, NODE_IMAGE_BATCH_SKIP,
    NODE_LORA, NODE_MODEL, NODE_REF_IMAGES, NODE_SAMPLES_54, COMBINE_NODE_IMAGE_BATCH,
    NODE_SAVE_LATENT, NODE_FRAMES_VALUE, NODE_LOAD_LATENT, NODE_VIDEO_COMBINE, COMBINE_NODE_OUTPUT_COMBINE_1,
    NODE_START_FRAME, NODE_PROMPT, NODE_VACE, NODE_VIDEO_DECODE, HIGH_STEPS,COMBINE_NODE_LOAD_VIDEO_COMBINE,
    COMBINE_NODE_VIDEOS, COMBINE_NODE_OUTPUT_COMBINE_N, NODE_WIDTH, RESCALE_FACTOR, STEPS, VIDEO_HEIGHT, VIDEO_WIDTH
)
from services.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


class WorkflowManager:
    """Manages workflow JSON modifications for different job types"""
    
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
        workflow[NODE_LORA]["inputs"]["lora"] = HIGH_LORA
        
        # Set model to HIGH noise model
        workflow[NODE_MODEL]["inputs"]["model"] = HIGH_MODEL
        
        # Handle reference images (delete for jobs 1-2, set for jobs 3+)
        if job.job_number == 1:
            # do not skip any of the generated frames
            workflow[NODE_IMAGE_BATCH_SKIP]["inputs"]["start_index"] = 0
            del workflow[NODE_VACE]["inputs"]["ref_images"]
            logger.debug(f"Deleted reference images node for job {job.job_number}")
        else:
            # Set reference image path for jobs 3+
            workflow[NODE_REF_IMAGES]["inputs"]["image_path"] = job.reference_image_path
            logger.debug(f"Set reference image: {job.reference_image_path}")
        
        # Delete samples nodes for HIGH jobs
        del workflow[NODE_SAMPLES_54]["inputs"]["samples"]
        logger.debug(f"Deleted samples node {NODE_SAMPLES_54} for HIGH job")
        
         # Delete samples nodes for HIGH jobs
        del workflow[NODE_VIDEO_DECODE]["inputs"]["samples"]
        logger.debug(f"Deleted samples node {NODE_VIDEO_DECODE} for HIGH job")

        # Set frames to render
        workflow[NODE_FRAMES_VALUE]["inputs"]["value"] = job.frames_to_render

        #width/height
        workflow[NODE_WIDTH]["inputs"]["value"] = VIDEO_WIDTH
        workflow[NODE_HEIGHT]["inputs"]["value"] = VIDEO_HEIGHT

        #sampler changes
        workflow[NODE_SAMPLES_54]["inputs"]["seed"] = job.seed
        workflow[NODE_SAMPLES_54]["inputs"]["start_step"] = 0
        workflow[NODE_SAMPLES_54]["inputs"]["end_step"] = HIGH_STEPS
        workflow[NODE_SAMPLES_54]["inputs"]["steps"] = STEPS

        # Set start frame (skip-n-frames)
        workflow[NODE_START_FRAME]["inputs"]["value"] = job.start_frame
        
        #define folder to save latent
        workflow[NODE_SAVE_LATENT]["inputs"]["file_path"] = job.latent_path

        # Set prompts
        self._set_prompts(workflow, job.positive_prompt, job.negative_prompt)
        
        logger.info(f"Modified workflow for HIGH job #{job.job_number}")
        self.storage.save_runtime_workflow(workflow, job.prompt_name, job.job_number, "high")
        # Save workflow in dry-run mode
        if is_dry_run():
            job_info = {
                "type": "high_noise_render",
                "job_id": job.job_id,
                "job_number": job.job_number,
                "video_name": job.video_name,
                "frames_to_render": job.frames_to_render,
                "start_frame": job.start_frame,
                "lora_model": HIGH_LORA,
                "noise_model": HIGH_MODEL,
                "has_reference_image": job.reference_image_path is not None,
                "reference_image_path": job.reference_image_path,
                "latent_path": job.latent_path,
                "modifications": [
                    f"LoRA: {HIGH_LORA}",
                    f"Model: {HIGH_MODEL}",
                    f"Frames: {job.frames_to_render}",
                    f"Start: {job.start_frame}"
                ]
            }
            dry_run_manager.save_workflow(workflow, job_info)
        
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
        workflow[NODE_LORA]["inputs"]["lora"] = LOW_LORA
        
        # Set model to LOW noise model
        workflow[NODE_MODEL]["inputs"]["model"] = LOW_MODEL
        
        # Delete latent node for LOW jobs
        del workflow[NODE_SAVE_LATENT]
        logger.debug(f"Deleted latent node {NODE_SAVE_LATENT} for LOW job")

        # set folder to load latent
        workflow[NODE_LOAD_LATENT]["inputs"]["file_path"] = job.latent_path

        # Set frames to render
        workflow[NODE_FRAMES_VALUE]["inputs"]["value"] = job.frames_to_render
        
        # Set start frame
        workflow[NODE_START_FRAME]["inputs"]["value"] = job.start_frame
        
        # Set output path
        workflow[NODE_VIDEO_COMBINE]["inputs"]["filename_prefix"] = job.video_output_path

        #width/height
        workflow[NODE_WIDTH]["inputs"]["value"] = VIDEO_WIDTH
        workflow[NODE_HEIGHT]["inputs"]["value"] = VIDEO_HEIGHT


        #sampler changes
        workflow[NODE_SAMPLES_54]["inputs"]["seed"] = job.seed
        workflow[NODE_SAMPLES_54]["inputs"]["start_step"] = HIGH_STEPS #start where the high stopped
        workflow[NODE_SAMPLES_54]["inputs"]["end_step"] = -1
        workflow[NODE_SAMPLES_54]["inputs"]["steps"] = STEPS

        #load image by setting image_path
        if job.job_number <= 2:
            # Delete reference images node for first two jobs
            del workflow[NODE_VACE]["inputs"]["ref_images"]
            logger.debug(f"Deleted reference images node for job {job.job_number}")
        else:
            workflow[NODE_REF_IMAGES]["inputs"]["image_path"] = job.reference_image_path
            logger.debug(f"Set reference image: {job.reference_image_path}")

        # Set prompts
        self._set_prompts(workflow, job.positive_prompt, job.negative_prompt)
        
        logger.info(f"Modified workflow for LOW job #{job.job_number}")
        self.storage.save_runtime_workflow(workflow, job.prompt_name, job.job_number, "low")
        # Save workflow in dry-run mode
        if is_dry_run():
            job_info = {
                "type": "low_noise_render",
                "job_id": job.job_id,
                "job_number": job.job_number,
                "video_name": job.video_name,
                "frames_to_render": job.frames_to_render,
                "start_frame": job.start_frame,
                "lora_model": LOW_LORA,
                "noise_model": LOW_MODEL,
                "latent_path": job.latent_path,
                "reference_image_path": job.reference_image_path,
                "modifications": [
                    f"LoRA: {LOW_LORA}",
                    f"Model: {LOW_MODEL}",
                    f"Frames: {job.frames_to_render}",
                    f"Start: {job.start_frame}",
                    f"Latent input: {job.latent_path}"
                ]
            }
            dry_run_manager.save_workflow(workflow, job_info)
        
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
        workflow[COMBINE_NODE_VIDEOS]["inputs"]["video"] = combine_job.input_video_path
        logger.debug(f"Set input video: {combine_job.input_video_path}")
        
        workflow[COMBINE_NODE_RESCALE]["inputs"]["rescale_factor"] = RESCALE_FACTOR

        # Handle previous combined video
        if combine_job.combine_number == 1:
            del workflow[COMBINE_NODE_OUTPUT_COMBINE_N]
            del workflow[COMBINE_NODE_LOAD_VIDEO_COMBINE]
            del workflow[COMBINE_NODE_IMAGE_BATCH]
            workflow[COMBINE_NODE_OUTPUT_COMBINE_1]["inputs"]["filename_prefix"] = combine_job.output_path
        else:
            # Subsequent combines - set previous combined video
            workflow[COMBINE_NODE_LOAD_VIDEO_COMBINE]["inputs"]["video"] = combine_job.previous_combined_path
            workflow[COMBINE_NODE_OUTPUT_COMBINE_N]["inputs"]["filename_prefix"] = combine_job.output_path
            del workflow[COMBINE_NODE_OUTPUT_COMBINE_1]

        logger.info(f"Created combine workflow for job #{combine_job.combine_number}")
        self.storage.save_runtime_workflow(workflow, combine_job.prompt_name, combine_job.combine_number, "combine")
        # Save workflow in dry-run mode
        if is_dry_run():
            job_info = {
                "type": "combine",
                "job_id": combine_job.job_id,
                "combine_number": combine_job.combine_number,
                "video_name": combine_job.video_name,
                "input_video_path": combine_job.input_video_path,
                "previous_combined_path": combine_job.previous_combined_path,
                "output_path": combine_job.output_path,
                "is_first_combine": combine_job.combine_number == 1,
                "modifications": [
                    f"Input: {Path(combine_job.input_video_path).name}",
                    f"Output: {Path(combine_job.output_path).name}",
                    f"Previous: {Path(combine_job.previous_combined_path).name if combine_job.previous_combined_path else 'None'}"
                ]
            }
            dry_run_manager.save_workflow(workflow, job_info)
        
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
        # required_nodes = []  # Add any critical nodes that must exist
        
        # for node_id in required_nodes:
        #     if node_id not in workflow:
        #         logger.error(f"Required node {node_id} not found in workflow")
        #         return False
        
        # # Check for basic structure
        # if not workflow:
        #     logger.error("Workflow is empty")
        #     return False
        
        # # Check that each node has required fields
        # for node_id, node in workflow.items():
        #     if not isinstance(node, dict):
        #         logger.error(f"Node {node_id} is not a dictionary")
        #         return False
        #     if "class_type" not in node:
        #         logger.warning(f"Node {node_id} missing class_type")
        
        return True