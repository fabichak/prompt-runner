"""Unified orchestrator for all job types"""
import logging
import time
from typing import Dict, Any, Optional, List
from pathlib import Path
from urllib.request import urlretrieve
from urllib.parse import urlparse

from models.base_job import BaseJob, JobStatus
from models.job_result import JobResult
from services.mode_registry import ModeRegistry
from services.service_factory import ServiceFactory
from services.comfyui_client import ComfyUIClient
from services.storage_utils import StorageManager
from services.trello_client import TrelloApiClient
import config

logger = logging.getLogger(__name__)


class UnifiedOrchestrator:
    """Single orchestrator for all job types"""

    def __init__(self):
        """Initialize the unified orchestrator"""
        self.comfyui_client = ServiceFactory.create_comfyui_client(config.SERVER_ADDRESS)
        self.storage = ServiceFactory.create_storage_manager()
        self.trello_client = TrelloApiClient(config.TRELLO_API_BASE_URL)

        # Track results for reporting
        self.completed_jobs = []
        self.failed_jobs = []

    def process_api_job(self, api_card_data: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        """Process a job from API (Trello card)

        Args:
            api_card_data: Data from Trello API card
            dry_run: If True, simulate execution without running

        Returns:
            Result dictionary with status and outputs
        """
        try:

            if not self.comfyui_client.connect():
                logger.error("Failed to connect to ComfyUI")
                return False
            
            # Determine mode (default to v2v for backward compatibility)
            mode = api_card_data.get('mode', 'v2v')
            card_id = api_card_data.get('cardId')

            logger.info(f"Processing {mode} job from card {card_id}")

            # Get job class and workflow manager from registry
            if not ModeRegistry.is_mode_registered(mode):
                raise ValueError(f"Unsupported mode: {mode}")

            job_class = ModeRegistry.get_job_class(mode)
            workflow_manager = ModeRegistry.get_workflow_manager(mode)

            # Create job from API data
            job = job_class.from_api_data(api_card_data)

            # Validate job
            if not job.validate():
                error_msg = f"Invalid job parameters for mode {mode}"
                logger.error(error_msg)
                job.status = JobStatus.FAILED
                job.error_message = error_msg
                self.failed_jobs.append(job)

                # Report failure to API
                self.trello_client.completed_card(
                    card_id=card_id,
                    result={'status': 'failed', 'error': error_msg}
                )
                return {'status': 'failed', 'error': error_msg}

            if dry_run:
                logger.info(f"DRY RUN: Would execute {mode} job {job.job_id}")
                return {
                    'status': 'dry_run',
                    'job_id': job.job_id,
                    'mode': mode,
                    'message': 'Dry run completed successfully'
                }

            # Download files if they are URLs
            job = self._prepare_job_inputs(job)

            # Execute the job
            result = self._execute_job(job, workflow_manager)

            # Report completion to API
            self.trello_client.completed_card(
                card_id=card_id,
                result={
                    'status': result.status,
                    'outputs': result.outputs,
                    'job_id': job.job_id
                }
            )

            return {
                'status': result.status,
                'job_id': job.job_id,
                'outputs': result.outputs
            }

        except Exception as e:
            logger.error(f"Error processing job: {e}", exc_info=True)

            # Report error to API if we have a card ID
            if 'card_id' in locals() and card_id:
                try:
                    self.trello_client.completed_card(
                        card_id=card_id,
                        result={'status': 'error', 'error': str(e)}
                    )
                except Exception as api_error:
                    logger.error(f"Failed to report error to API: {api_error}")

            return {
                'status': 'error',
                'error': str(e)
            }

    def _prepare_job_inputs(self, job: BaseJob) -> BaseJob:
        """Download remote files if needed"""
        # Handle V2V job inputs
        if hasattr(job, 'video_path') and self._is_url(job.video_path):
            job.video_path = self._download_file(job.video_path, f"{job.job_id}_video.mp4")

        if hasattr(job, 'reference_image_path') and self._is_url(job.reference_image_path):
            job.reference_image_path = self._download_file(job.reference_image_path, f"{job.job_id}_image.png")

        # Handle I2I job inputs
        if hasattr(job, 'image_path') and self._is_url(job.image_path):
            job.image_path = self._download_file(job.image_path, f"{job.job_id}_input.png")

        return job

    def _is_url(self, path: str) -> bool:
        """Check if a path is a URL"""
        try:
            result = urlparse(path)
            return all([result.scheme, result.netloc])
        except:
            return False

    def _download_file(self, url: str, filename: str) -> str:
        """Download file from URL to local storage"""
        # Create inputs directory
        inputs_dir = Path("output") / "prompt-runner" / "inputs"
        inputs_dir.mkdir(parents=True, exist_ok=True)

        local_path = inputs_dir / filename
        logger.info(f"Downloading {url} to {local_path}")

        try:
            urlretrieve(url, local_path)
            return str(local_path.absolute())
        except Exception as e:
            logger.error(f"Failed to download {url}: {e}")
            raise

    def _execute_job(self, job: BaseJob, workflow_manager) -> JobResult:
        """Execute a single job through ComfyUI"""
        try:
            job.status = JobStatus.IN_PROGRESS
            logger.info(f"Executing job {job.job_id} in {job.mode} mode")

            # Modify workflow for this job
            modified_workflow = workflow_manager.modify_workflow(job)

            # Save workflow for debugging if needed
            if hasattr(self.storage, 'save_runtime_workflow'):
                self.storage.save_runtime_workflow(
                    modified_workflow,
                    job.job_id,
                    1,
                    job.mode
                )

            # Queue prompt to ComfyUI
            prompt_id = self.comfyui_client.queue_prompt(modified_workflow, config.CLIENT_ID)
            logger.info(f"Queued prompt {prompt_id} for job {job.job_id}")

            # Wait for completion
            outputs = self._wait_for_completion(prompt_id)

            # Mark job as completed
            job.status = JobStatus.COMPLETED
            self.completed_jobs.append(job)

            logger.info(f"Job {job.job_id} completed successfully")

            return JobResult(
                job_id=job.job_id,
                status='completed',
                outputs=outputs,
                prompt_id=prompt_id
            )

        except Exception as e:
            logger.error(f"Failed to execute job {job.job_id}: {e}")
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            self.failed_jobs.append(job)

            return JobResult(
                job_id=job.job_id,
                status='failed',
                error_message=str(e)
            )

    def _wait_for_completion(self, prompt_id: str, timeout: int = 600) -> List[str]:
        """Wait for ComfyUI to complete the prompt"""
        start_time = time.time()
        outputs = []

        while time.time() - start_time < timeout:
            try:
                # Check if prompt is complete
                history = self.comfyui_client.get_history(prompt_id)

                if prompt_id in history:
                    if 'outputs' in history[prompt_id]:
                        # Collect output files
                        for node_id, node_output in history[prompt_id]['outputs'].items():
                            if 'images' in node_output:
                                for image in node_output['images']:
                                    outputs.append(image['filename'])
                            if 'gifs' in node_output:
                                for gif in node_output['gifs']:
                                    outputs.append(gif['filename'])
                            if 'videos' in node_output:
                                for video in node_output['videos']:
                                    outputs.append(video['filename'])

                        logger.info(f"Prompt {prompt_id} completed with {len(outputs)} outputs")
                        return outputs

            except Exception as e:
                logger.warning(f"Error checking prompt status: {e}")

            time.sleep(2)

        raise TimeoutError(f"Prompt {prompt_id} did not complete within {timeout} seconds")

    def get_status(self) -> Dict[str, Any]:
        """Get orchestrator status and statistics"""
        return {
            'completed_jobs': len(self.completed_jobs),
            'failed_jobs': len(self.failed_jobs),
            'available_modes': ModeRegistry.get_available_modes(),
            'jobs': {
                'completed': [job.to_dict() for job in self.completed_jobs],
                'failed': [job.to_dict() for job in self.failed_jobs]
            }
        }