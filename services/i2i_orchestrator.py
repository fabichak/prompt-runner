"""i2i Orchestrator for managing image-to-image rendering workflow"""
import time
import logging
from pathlib import Path
from typing import List, Optional

from models.i2i_job import I2IJob
from services.image_scanner import ImageScanner
from services.image_tracker import ImageTracker
from services.i2i_workflow_manager import I2IWorkflowManager
from config import (
    I2I_CFG_VALUES, I2I_IMAGE_RENDER_AMOUNT, I2I_PROCESSED_FILE, 
    I2I_FAILED_FILE, I2I_POLL_INTERVAL, I2I_INPUT_DIR,
    I2I_WORKFLOW_FILE, SERVER_ADDRESS
)
from services.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


class I2IOrchestrator:
    """Orchestrates the i2i rendering workflow"""
    
    def __init__(self):
        self.comfyui_client = ServiceFactory.create_comfyui_client(SERVER_ADDRESS)
        self.storage = ServiceFactory.create_storage_manager()
        
        # Initialize components
        self.scanner = ImageScanner(I2I_INPUT_DIR)
        self.tracker = ImageTracker(I2I_PROCESSED_FILE, I2I_FAILED_FILE)
        self.workflow_manager = I2IWorkflowManager(
            Path(I2I_WORKFLOW_FILE),
             self.storage
        )
        
        # Validate CFG values are configured
        if not I2I_CFG_VALUES:
            raise ValueError("I2I_CFG_VALUES is empty. Please configure CFG values in config.py")
        
        logger.info(f"I2I Orchestrator initialized")
        logger.info(f"CFG values: {I2I_CFG_VALUES}")
        logger.info(f"Renders per CFG: {I2I_IMAGE_RENDER_AMOUNT}")
        logger.info(f"Total renders per image: {len(I2I_CFG_VALUES) * I2I_IMAGE_RENDER_AMOUNT}")
    
    def run(self, continuous: bool = True):
        """Run the i2i orchestrator"""
        logger.info("Starting I2I Orchestrator...")
        
         # Connect to ComfyUI
        if not self.comfyui_client.connect():
            logger.error("Failed to connect to ComfyUI")
            return False

        try:
            while True:
                # Get tracking stats
                stats = self.tracker.get_stats()
                logger.info(f"Tracking stats - Processed: {stats['processed']}, Failed: {stats['failed']}")
                
                # Scan for new images
                all_tracked = self.tracker.processed_images.union(self.tracker.failed_images)
                new_images = self.scanner.find_new_images(all_tracked)
                
                if new_images:
                    logger.info(f"Processing {len(new_images)} new images")
                    for image_path in new_images:
                        self.process_image(image_path)
                else:
                    logger.info("No new images to process")
                
                if not continuous:
                    logger.info("Single run mode - exiting")
                    break
                
                logger.info(f"Waiting {I2I_POLL_INTERVAL} seconds before next scan...")
                time.sleep(I2I_POLL_INTERVAL)
                
        except KeyboardInterrupt:
            logger.info("I2I Orchestrator stopped by user")
        except Exception as e:
            logger.error(f"Error in I2I Orchestrator: {e}")
            raise
    
    def process_image(self, image_path: Path):
        """Process a single image with all CFG values and render amounts"""
        logger.info(f"Processing image: {image_path.name}")
        
        try:
            image_processed = False
            total_renders = len(I2I_CFG_VALUES) * I2I_IMAGE_RENDER_AMOUNT
            current_render = 0
            
            for cfg_value in I2I_CFG_VALUES:
                for render_num in range(1, I2I_IMAGE_RENDER_AMOUNT + 1):
                    current_render += 1
                    
                    # Create output filename
                    image_stem = image_path.stem
                    output_filename = f"{image_stem}_cfg{cfg_value}_render{render_num}"
                    
                    # Create job
                    job = I2IJob(
                        image_path=str(image_path),
                        cfg_value=cfg_value,
                        render_number=render_num,
                        output_filename=output_filename
                    )
                    
                    logger.info(f"  Render {current_render}/{total_renders}: {job.job_id}")
                    
                    # Modify workflow
                    workflow = self.workflow_manager.modify_workflow_for_i2i_job(job)
                    
                    # Queue and execute
                    success = self._execute_job(workflow, job)
                    
                    if not success:
                        logger.error(f"  Failed to execute job: {job.job_id}")
                        # Mark as failed and stop processing this image
                        self.tracker.mark_failed(str(image_path.absolute()))
                        return
            
            # Mark as processed after all renders complete
            self.tracker.mark_processed(str(image_path.absolute()))
            logger.info(f"Successfully processed all renders for: {image_path.name}")
            
        except Exception as e:
            logger.error(f"Error processing image {image_path}: {e}")
            self.tracker.mark_failed(str(image_path.absolute()))
    
    def _execute_job(self, workflow: dict, job: I2IJob) -> bool:
        """Execute a single rendering job"""
        try:
            prompt_id = self.comfyui_client.queue_prompt(workflow)
            if not prompt_id:
                logger.error(f"Failed to queue prompt for {job.job_id}")
                return False
            
            logger.info(f"    Queued prompt: {prompt_id}")
            
            # Wait for completion
            success = self.comfyui_client.wait_for_prompt_completion(prompt_id, timeout=300)
            
            if success:
                logger.info(f"    ✓ Completed: {job.output_filename}")
            else:
                logger.error(f"    ✗ Timeout or error: {job.output_filename}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error executing job {job.job_id}: {e}")
            return False
    
    def get_status(self) -> dict:
        """Get current orchestrator status"""
        stats = self.tracker.get_stats()
        all_images = self.scanner.scan_for_images()
        
        return {
            "mode": "i2i",
            "processed": stats["processed"],
            "failed": stats["failed"],
            "total_found": len(all_images),
            "pending": len(all_images) - stats["total"],
            "cfg_values": I2I_CFG_VALUES,
            "renders_per_cfg": I2I_IMAGE_RENDER_AMOUNT
        }