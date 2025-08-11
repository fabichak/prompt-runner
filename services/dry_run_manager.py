"""
Dry-run mode manager for comprehensive simulation without external connections
Enhanced to save complete ComfyUI workflow JSON payloads for analysis
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


class PathJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that converts Path objects to strings"""
    
    def default(self, obj):
        if isinstance(obj, Path):
            return str(obj)
        return super().default(obj)


class DryRunManager:
    """Manages dry-run mode configuration and temp file generation"""
    
    def __init__(self):
        self.is_dry_run = False
        self.temp_dir = None
        self.workflow_counter = 0
        self.generated_workflows = []
        self.http_payloads = []  # Store complete HTTP payloads for analysis
        self.current_video_name = None
        
    def enable_dry_run(self):
        """Enable dry-run mode and create output directory structure"""
        self.is_dry_run = True
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Use output/dry-run/ directory instead of temp directories
        base_dry_run_dir = Path("output/dry-run")
        base_dry_run_dir.mkdir(parents=True, exist_ok=True)
        
        # Create timestamped subdirectory for this dry-run session
        self.temp_dir = base_dry_run_dir / f"session_{timestamp}"
        self.temp_dir.mkdir(exist_ok=True)
        
        # Create subdirectories for organization
        (self.temp_dir / "workflows").mkdir(exist_ok=True)
        (self.temp_dir / "payloads").mkdir(exist_ok=True)
        (self.temp_dir / "render_jobs").mkdir(exist_ok=True)
        (self.temp_dir / "combine_jobs").mkdir(exist_ok=True)
        (self.temp_dir / "state").mkdir(exist_ok=True)
        (self.temp_dir / "logs").mkdir(exist_ok=True)  # Add logs directory
        
        logger.info(f"🔄 Dry-run mode enabled - output directory: {self.temp_dir}")
        logger.info(f"📁 Created directories: workflows/, payloads/, render_jobs/, combine_jobs/, state/, logs/")
        
    def set_current_video_name(self, video_name: str):
        """Set the current video name for organized file storage"""
        self.current_video_name = video_name
        if self.is_dry_run and self.temp_dir:
            # Create video-specific directory
            video_dir = self.temp_dir / "workflows" / video_name
            video_dir.mkdir(exist_ok=True)
            logger.debug(f"📂 Created video directory: {video_dir}")

    
    def get_logs_directory(self) -> Optional[Path]:
        """Get the logs directory for dry-run mode"""
        if self.is_dry_run and self.temp_dir:
            return self.temp_dir / "logs"
        return None
    
    def save_complete_comfyui_payload(self, 
                                    http_payload: Dict[str, Any], 
                                    job_info: Dict[str, Any], 
                                    server_address: str) -> str:
        """Save complete HTTP payload that would be sent to ComfyUI
        
        Args:
            http_payload: Complete HTTP payload with prompt, client_id, prompt_id
            job_info: Job metadata (job_id, job_type, video_name, etc.)
            server_address: ComfyUI server address
            
        Returns:
            Filename of saved payload
        """
        if not self.is_dry_run:
            return ""
            
        self.workflow_counter += 1
        
        # Generate descriptive filename
        job_type = job_info.get('job_type', 'unknown')
        job_number = job_info.get('job_number', 0)
        prompt_id_short = job_info.get('prompt_id', '')[:8]
        video_name = job_info.get('video_name', 'unknown')
        
        if job_type == 'render':
            filename = f"render_job_{job_number:03d}_{prompt_id_short}.json"
        elif job_type == 'combine':
            filename = f"combine_job_{job_number:03d}_{prompt_id_short}.json"
        else:
            filename = f"workflow_{self.workflow_counter:03d}_{job_type}_{prompt_id_short}.json"
        
        # Determine save path
        if video_name and video_name != 'unknown':
            video_dir = self.temp_dir / "workflows" / video_name
            video_dir.mkdir(exist_ok=True)
            filepath = video_dir / filename
        else:
            filepath = self.temp_dir / "workflows" / filename
        
        # Create comprehensive workflow document
        complete_document = {
            "timestamp": datetime.now().isoformat(),
            "workflow_id": self.workflow_counter,
            "job_info": {
                **job_info,
                "dry_run_sequence": self.workflow_counter,
                "video_name": video_name
            },
            "comfyui_http_payload": http_payload,
            "workflow_metadata": {
                "nodes_count": len(http_payload.get('prompt', {})) if isinstance(http_payload.get('prompt'), dict) else 0,
                "workflow_size_bytes": len(json.dumps(http_payload.get('prompt', {}))),
                "modifications_applied": self._detect_workflow_modifications(http_payload.get('prompt', {})),
                "estimated_execution_time_seconds": self._estimate_execution_time(job_info, http_payload.get('prompt', {}))
            },
            "execution_context": {
                "server_address": server_address,
                "dry_run_mode": True,
                "client_version": "prompt_runner_v2",
                "system_timestamp": time.time(),
                "temp_directory": str(self.temp_dir)
            }
        }
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(complete_document, f, indent=2, ensure_ascii=False)
                
            # Store for summary
            self.generated_workflows.append({
                "filename": filename,
                "filepath": str(filepath),
                "job_info": job_info,
                "timestamp": datetime.now().isoformat(),
                "payload_size_bytes": len(json.dumps(http_payload))
            })
            
            # Store HTTP payload for aggregated analysis
            self.http_payloads.append({
                "sequence": self.workflow_counter,
                "timestamp": datetime.now().isoformat(),
                "job_info": job_info,
                "payload": http_payload
            })
            
            logger.info(f"💾 Saved complete ComfyUI payload: {filepath}")
            logger.info(f"📊 Payload size: {len(json.dumps(http_payload))} bytes, Nodes: {complete_document['workflow_metadata']['nodes_count']}")
            
            # Save aggregated payloads file
            self._save_aggregated_payloads()
            
            return filename
            
        except Exception as e:
            logger.error(f"❌ Failed to save ComfyUI payload: {e}")
            return ""
    
    def _detect_workflow_modifications(self, workflow: Dict[str, Any]) -> List[str]:
        """Detect modifications made to the workflow"""
        modifications = []
        
        if isinstance(workflow, dict):
            for node_id, node in workflow.items():
                if isinstance(node, dict) and "inputs" in node:
                    inputs = node["inputs"]
                    
                    # Detect common modifications
                    if "lora_name" in inputs:
                        modifications.append(f"LoRA: {inputs['lora_name']}")
                    if "gguf_name" in inputs:
                        modifications.append(f"Model: {inputs['gguf_name']}")
                    if "value" in inputs and node_id in ["19"]:  # Frames node
                        modifications.append(f"Frames: {inputs['value']}")
                    if "start_frame" in inputs:
                        modifications.append(f"Start frame: {inputs['start_frame']}")
                    if "image" in inputs:
                        modifications.append(f"Reference image: {inputs['image']}")
                    if "text" in inputs and len(str(inputs['text'])) > 20:
                        text_preview = str(inputs['text'])[:50] + "..." if len(str(inputs['text'])) > 50 else str(inputs['text'])
                        modifications.append(f"Prompt: {text_preview}")
        
        return modifications
    
    def _estimate_execution_time(self, job_info: Dict[str, Any], workflow: Dict[str, Any]) -> int:
        """Estimate workflow execution time in seconds"""
        base_time = 60  # Base execution time
        
        # Adjust based on job type
        job_type = job_info.get('job_type', 'unknown')
        if job_type == 'render':
            base_time = 180  # Render jobs typically take longer
        elif job_type == 'combine':
            base_time = 120  # Combine jobs are medium duration
        
        # Adjust based on frames
        frames = job_info.get('frames_to_render', 101)
        base_time += int(frames * 0.5)  # ~0.5 seconds per frame
        
        # Adjust based on workflow complexity
        if isinstance(workflow, dict):
            node_count = len(workflow)
            base_time += int(node_count * 0.2)  # Additional time for complex workflows
        
        return base_time
    
    def _save_aggregated_payloads(self):
        """Save aggregated HTTP payloads for sequence analysis"""
        if not self.http_payloads:
            return
            
        aggregated_file = self.temp_dir / "payloads" / f"complete_http_sequence_{datetime.now().strftime('%H%M%S')}.json"
        
        try:
            aggregated_data = {
                "created_at": datetime.now().isoformat(),
                "total_payloads": len(self.http_payloads),
                "video_name": self.current_video_name,
                "sequence": self.http_payloads
            }
            
            with open(aggregated_file, 'w', encoding='utf-8') as f:
                json.dump(aggregated_data, f, indent=2, ensure_ascii=False)
                
            logger.debug(f"📚 Updated aggregated payloads: {aggregated_file}")
            
        except Exception as e:
            logger.error(f"❌ Failed to save aggregated payloads: {e}")

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
            json.dump(workflow_metadata, f, indent=2, cls=PathJSONEncoder)
            
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
            # Fix: Use .value for enum serialization instead of str()
            job_type_value = getattr(job, 'job_type', job_type)
            if hasattr(job_type_value, 'value'):
                job_type_str = job_type_value.value
            else:
                job_type_str = str(job_type_value)
                
            job_plan["jobs"].append({
                "job_id": getattr(job, 'job_id', str(uuid.uuid4())),
                "job_number": getattr(job, 'job_number', 0),
                "job_type": job_type_str,
                "frames_to_render": getattr(job, 'frames_to_render', 0),
                "start_frame": getattr(job, 'start_frame', 0),
                "video_name": getattr(job, 'video_name', 'unknown'),
                "positive_prompt": getattr(job, 'positive_prompt', ''),
                "negative_prompt": getattr(job, 'negative_prompt', ''),
                "latent_path": getattr(job, 'latent_path', None),
                "reference_image_path": getattr(job, 'reference_image_path', None)
            })
            
        with open(filepath, 'w') as f:
            json.dump(job_plan, f, indent=2, cls=PathJSONEncoder)        
    def get_summary(self) -> Dict[str, Any]:
        """Get dry-run execution summary"""
        if not self.is_dry_run:
            return {}
        
        # Calculate total payload size
        total_payload_size = sum(wf.get('payload_size_bytes', 0) for wf in self.generated_workflows)
        
        return {
            "dry_run_enabled": True,
            "output_directory": str(self.temp_dir),
            "session_type": "organized_dry_run",
            "current_video": self.current_video_name,
            "workflows_generated": len(self.generated_workflows),
            "http_payloads_saved": len(self.http_payloads),
            "total_payload_size_bytes": total_payload_size,
            "total_payload_size_mb": round(total_payload_size / (1024 * 1024), 2),
            "workflow_details": self.generated_workflows,
            "execution_time": datetime.now().isoformat(),
            "directories_created": [
                str(self.temp_dir / "workflows"),
                str(self.temp_dir / "payloads"), 
                str(self.temp_dir / "render_jobs"),
                str(self.temp_dir / "combine_jobs"),
                str(self.temp_dir / "state"),
                str(self.temp_dir / "logs")
            ]
        }
        
    def cleanup(self):
        """Clean up dry-run directory (optional)"""
        if self.temp_dir and self.temp_dir.exists():
            logger.info(f"🗂️ Dry-run files preserved at: {self.temp_dir}")
            logger.info(f"📊 Session contained {len(self.generated_workflows)} workflows and {len(self.http_payloads)} HTTP payloads")
            
            # Show directory size for reference
            try:
                total_size = sum(f.stat().st_size for f in self.temp_dir.rglob('*') if f.is_file())
                size_mb = total_size / (1024 * 1024)
                logger.info(f"💾 Total dry-run output size: {size_mb:.2f} MB")
            except Exception as e:
                logger.debug(f"Could not calculate directory size: {e}")
        else:
            logger.info("🧹 No dry-run directory to clean up")            # Optionally remove: shutil.rmtree(self.temp_dir)


# Global dry-run manager instance
dry_run_manager = DryRunManager()


def is_dry_run() -> bool:
    """Check if we're in dry-run mode"""
    return dry_run_manager.is_dry_run or os.getenv('DRY_RUN', '').lower() in ('true', '1', 'yes')


def enable_dry_run():
    """Enable dry-run mode"""
    dry_run_manager.enable_dry_run()