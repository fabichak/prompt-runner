"""Video-to-video workflow manager"""
import copy
import logging
from typing import Dict, Any
from pathlib import Path

from services.workflows.base_workflow import BaseWorkflowManager
from models.base_job import BaseJob
from models.v2v_job import V2VJob
from config import (
    NODE_HEIGHT, NODE_LOAD_VIDEO_PATH, NODE_PROMPT_NEG, NODE_PROMPT_POS,
    NODE_REF_IMAGES, NODE_SAMPLER, NODE_VIDEO_COMBINE, NODE_VIDEO_COMBINE_NOBG,
    NODE_WIDTH, VIDEO_HEIGHT, VIDEO_WIDTH, JSON_WORKFLOW_FILE
)

logger = logging.getLogger(__name__)


class V2VWorkflowManager(BaseWorkflowManager):
    """Workflow manager for video-to-video jobs"""

    def get_workflow_file(self) -> str:
        """Returns path to v2v workflow JSON file"""
        return JSON_WORKFLOW_FILE  # prompts/v2v.json

    def modify_workflow(self, job: BaseJob) -> Dict[str, Any]:
        """Modifies workflow for v2v job"""
        if not isinstance(job, V2VJob):
            raise ValueError(f"Expected V2VJob, got {type(job)}")

        workflow = copy.deepcopy(self.base_workflow)
        params = job.to_workflow_params()

        # Modify video input nodes
        if str(NODE_LOAD_VIDEO_PATH) in workflow:
            workflow[str(NODE_LOAD_VIDEO_PATH)]["inputs"]["video"] = params['video_path']
            workflow[str(NODE_LOAD_VIDEO_PATH)]["inputs"]["frame_load_cap"] = params['total_frames']
            workflow[str(NODE_LOAD_VIDEO_PATH)]["inputs"]["skip_first_frames"] = params['select_every_n_frames']

        # Set reference image
        if str(NODE_REF_IMAGES) in workflow:
            workflow[str(NODE_REF_IMAGES)]["inputs"]["image"] = params['image_path']

        # Set dimensions
        if str(NODE_WIDTH) in workflow:
            workflow[str(NODE_WIDTH)]["inputs"]["value"] = VIDEO_WIDTH
        if str(NODE_HEIGHT) in workflow:
            workflow[str(NODE_HEIGHT)]["inputs"]["value"] = VIDEO_HEIGHT

        # Set sampler parameters
        if str(NODE_SAMPLER) in workflow:
            workflow[str(NODE_SAMPLER)]["inputs"]["seed"] = params['seed']
            workflow[str(NODE_SAMPLER)]["inputs"]["steps"] = params['steps']
            workflow[str(NODE_SAMPLER)]["inputs"]["cfg"] = params['cfg']

        # Set output path
        if str(NODE_VIDEO_COMBINE) in workflow and params.get('output_path'):
            workflow[str(NODE_VIDEO_COMBINE)]["inputs"]["filename_prefix"] = params['output_path']
            workflow[str(NODE_VIDEO_COMBINE_NOBG)]["inputs"]["filename_prefix"] = params['output_path']+'_nobg'

        # Set prompts
        if str(NODE_PROMPT_POS) in workflow:
            workflow[str(NODE_PROMPT_POS)]["inputs"]["positive_prompt"] = params['positive_prompt']
        if str(NODE_PROMPT_NEG) in workflow:
            workflow[str(NODE_PROMPT_NEG)]["inputs"]["negative_prompt"] = params['negative_prompt']

        logger.info(f"Modified v2v workflow for job {job.job_id}")
        return workflow