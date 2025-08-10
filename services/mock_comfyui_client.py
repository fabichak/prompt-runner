"""
Mock ComfyUI client for dry-run mode - simulates all WebSocket and HTTP operations
"""
import json
import logging
import time
import uuid
from typing import Dict, Any, Optional, Tuple, List

from services.dry_run_manager import dry_run_manager

logger = logging.getLogger(__name__)


class MockComfyUIClient:
    """Mock ComfyUI client that simulates all operations without actual connections"""
    
    def __init__(self, server_address: str = "127.0.0.1:8188"):
        self.server_address = server_address
        self.client_id = str(uuid.uuid4())
        self.ws = None
        self.connected = False
        self.queued_prompts = {}
        self.execution_history = {}
        
        logger.info(f"🎭 MockComfyUIClient initialized for {server_address}")
        
    def connect(self) -> bool:
        """Simulate WebSocket connection"""
        try:
            logger.info(f"🔗 [DRY-RUN] Simulating connection to ComfyUI server at {self.server_address}")
            self.connected = True
            self.ws = "mock_websocket_connection"
            return True
        except Exception as e:
            logger.error(f"[DRY-RUN] Mock connection failed: {e}")
            return False
    
    def disconnect(self):
        """Simulate closing WebSocket connection"""
        if self.ws:
            self.ws = None
            self.connected = False
            logger.info("🔌 [DRY-RUN] Simulated disconnection from ComfyUI server")
    
    def queue_prompt(self, workflow: Dict[str, Any], prompt_id: Optional[str] = None) -> Optional[str]:
        """Simulate queuing a workflow prompt for execution"""
        if not prompt_id:
            prompt_id = str(uuid.uuid4())
        
        try:
            # Simulate the HTTP request payload
            payload = {
                "prompt": workflow,
                "client_id": self.client_id,
                "prompt_id": prompt_id
            }
            
            # Store for simulation
            self.queued_prompts[prompt_id] = {
                "payload": payload,
                "queued_at": time.time(),
                "status": "queued"
            }
            
            # Save workflow to temp folder
            job_info = {
                "type": "render" if "class_type" in str(workflow) else "unknown",
                "prompt_id": prompt_id,
                "client_id": self.client_id,
                "nodes_count": len(workflow) if isinstance(workflow, dict) else 0,
                "modifications": self._detect_modifications(workflow)
            }
            
            workflow_filename = dry_run_manager.save_workflow(workflow, job_info)
            
            logger.info(f"🎬 [DRY-RUN] Simulated queuing prompt {prompt_id[:8]}... → {workflow_filename}")
            return prompt_id
                
        except Exception as e:
            logger.error(f"[DRY-RUN] Error simulating prompt queue: {e}")
            return None
    
    def wait_for_prompt_completion(self, prompt_id: str, timeout: int = 3600) -> Tuple[bool, Optional[str]]:
        """Simulate waiting for a specific prompt to finish execution"""
        if not self.ws:
            logger.error("[DRY-RUN] WebSocket not connected")
            return False, "WebSocket not connected"
        
        logger.info(f"⏳ [DRY-RUN] Simulating wait for prompt {prompt_id[:8]}... completion")
        
        # Simulate execution time (1-3 seconds)
        execution_time = 1.5
        time.sleep(0.1)  # Brief pause for realism
        
        # Simulate successful completion
        if prompt_id in self.queued_prompts:
            self.queued_prompts[prompt_id]["status"] = "completed"
            self.queued_prompts[prompt_id]["completed_at"] = time.time()
            
            # Store execution history
            self.execution_history[prompt_id] = {
                "status": "success",
                "outputs": self._simulate_outputs(prompt_id),
                "execution_time": execution_time
            }
            
            logger.info(f"✅ [DRY-RUN] Prompt {prompt_id[:8]}... completed successfully (simulated)")
            return True, None
        else:
            error_msg = "Prompt not found in queue"
            logger.error(f"❌ [DRY-RUN] Prompt {prompt_id[:8]}... failed: {error_msg}")
            return False, error_msg
    
    def get_history(self, prompt_id: str) -> Optional[Dict[str, Any]]:
        """Simulate getting execution history for a prompt"""
        if prompt_id in self.execution_history:
            history = self.execution_history[prompt_id]
            logger.debug(f"📋 [DRY-RUN] Retrieved history for {prompt_id[:8]}...")
            return history
        else:
            logger.warning(f"[DRY-RUN] No history found for {prompt_id[:8]}...")
            return None
    
    def interrupt_execution(self):
        """Simulate interrupting current execution"""
        logger.info("⏹️ [DRY-RUN] Simulated execution interruption")
    
    def get_queue_status(self) -> Optional[Dict[str, Any]]:
        """Simulate getting current queue status"""
        status = {
            "queue_running": [],
            "queue_pending": []
        }
        
        for prompt_id, prompt_data in self.queued_prompts.items():
            if prompt_data["status"] == "queued":
                status["queue_pending"].append([prompt_id, prompt_data])
            elif prompt_data["status"] == "running":
                status["queue_running"].append([prompt_id, prompt_data])
        
        logger.debug(f"📊 [DRY-RUN] Queue status: {len(status['queue_pending'])} pending, {len(status['queue_running'])} running")
        return status
    
    def clear_queue(self):
        """Simulate clearing the execution queue"""
        cleared_count = len([p for p in self.queued_prompts.values() if p["status"] == "queued"])
        for prompt_data in self.queued_prompts.values():
            if prompt_data["status"] == "queued":
                prompt_data["status"] = "cancelled"
        
        logger.info(f"🗑️ [DRY-RUN] Simulated clearing execution queue ({cleared_count} items)")
    
    def execute_with_retry(self, workflow: Dict[str, Any], max_retries: int = 3) -> Tuple[bool, Optional[str], Optional[str]]:
        """Simulate executing workflow with retry logic"""
        # Ensure connection
        if not self.connected:
            if not self.connect():
                return False, None, "[DRY-RUN] Failed to connect to ComfyUI"
        
        for attempt in range(max_retries):
            prompt_id = self.queue_prompt(workflow)
            if not prompt_id:
                logger.warning(f"[DRY-RUN] Failed to queue prompt, attempt {attempt + 1}/{max_retries}")
                continue
            
            success, error = self.wait_for_prompt_completion(prompt_id)
            if success:
                logger.info(f"🎯 [DRY-RUN] Workflow execution successful after {attempt + 1} attempt(s)")
                return True, prompt_id, None
            
            logger.warning(f"[DRY-RUN] Execution failed (attempt {attempt + 1}/{max_retries}): {error}")
        
        error_msg = f"[DRY-RUN] Failed after {max_retries} attempts"
        logger.error(error_msg)
        return False, None, error_msg
    
    def _detect_modifications(self, workflow: Dict[str, Any]) -> List[str]:
        """Detect what modifications were made to the workflow"""
        modifications = []
        
        if isinstance(workflow, dict):
            for node_id, node in workflow.items():
                if isinstance(node, dict) and "inputs" in node:
                    # Check for common modifications
                    inputs = node["inputs"]
                    
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
        
        return modifications
    
    def _simulate_outputs(self, prompt_id: str) -> Dict[str, Any]:
        """Simulate ComfyUI output generation"""
        return {
            "images": [
                {
                    "filename": f"output_{prompt_id[:8]}.mp4",
                    "type": "video"
                }
            ],
            "latents": [
                {
                    "filename": f"latent_{prompt_id[:8]}.safetensors",
                    "type": "latent"
                }
            ]
        }