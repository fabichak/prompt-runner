"""ComfyUI WebSocket client for communication"""
import websocket
from websocket import create_connection
import json
import urllib.request
import urllib.parse
import uuid
import time
from typing import Dict, Any, Optional, Tuple, List
import logging

from config import SERVER_ADDRESS, MAX_RETRIES, RETRY_DELAY

logger = logging.getLogger(__name__)


class ComfyUIClient:
    """Handles WebSocket communication with ComfyUI server"""
    
    def __init__(self, server_address: str = SERVER_ADDRESS):
        self.server_address = server_address
        self.client_id = str(uuid.uuid4())
        self.ws = None
        
    def connect(self) -> bool:
        """Establish WebSocket connection"""
        try:
            ws_url = f"ws://{self.server_address}/ws?clientId={self.client_id}"
            # Use create_connection with timeout for RunPod environment stability
            self.ws = create_connection(ws_url, timeout=30)
            logger.info(f"Connected to ComfyUI server at {self.server_address}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to ComfyUI: {e}")
            logger.error(f"WebSocket URL: {ws_url}")
            return False
    
    def disconnect(self):
        """Close WebSocket connection"""
        if self.ws:
            self.ws.close()
            self.ws = None
            logger.info("Disconnected from ComfyUI server")
    
    def queue_prompt(self, workflow: Dict[str, Any], prompt_id: Optional[str] = None) -> Optional[str]:
        """Queue a workflow prompt for execution"""
        if not prompt_id:
            prompt_id = str(uuid.uuid4())
        
        try:
            payload = {
                "prompt": workflow,
                "client_id": self.client_id,
                "prompt_id": prompt_id
            }
            data = json.dumps(payload, indent=2, default=str).encode('utf-8')
            req = urllib.request.Request(
                f"http://{self.server_address}/prompt",
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read())
                logger.info(f"Queued prompt {prompt_id}")
                return prompt_id
                
        except Exception as e:
            logger.error(f"Error queuing prompt: {e}")
            return None
    
    def wait_for_prompt_completion(self, prompt_id: str, timeout: int = 3600) -> Tuple[bool, Optional[str]]:
        """Wait for a specific prompt to finish execution"""
        if not self.ws:
            logger.error("WebSocket not connected")
            return False, "WebSocket not connected"
        
        logger.info(f"Waiting for prompt {prompt_id} to complete...")
        start_time = time.time()
        
        while True:
            if time.time() - start_time > timeout:
                logger.error(f"Timeout waiting for prompt {prompt_id}")
                return False, "Timeout"
            
            try:
                message = self.ws.recv()
                if isinstance(message, str):
                    data = json.loads(message)
                    
                    if data.get('type') == 'executing':
                        node_id = data['data'].get('node')
                        if node_id is None and data['data'].get('prompt_id') == prompt_id:
                            logger.info(f"Prompt {prompt_id} completed successfully")
                            return True, None
                    
                    elif data.get('type') == 'execution_error':
                        if data['data'].get('prompt_id') == prompt_id:
                            error_msg = data['data'].get('exception_message', 'Unknown error')
                            logger.error(f"Prompt {prompt_id} failed: {error_msg}")
                            return False, error_msg
                    
                    elif data.get('type') == 'progress':
                        if data['data'].get('prompt_id') == prompt_id:
                            value = data['data'].get('value', 0)
                            max_val = data['data'].get('max', 100)
                            node = data['data'].get('node')
                            logger.debug(f"Progress {node}: {value}/{max_val}")
                            
            except websocket.WebSocketTimeoutException:
                continue
            except websocket.WebSocketConnectionClosedException:
                logger.error(f"WebSocket connection closed unexpectedly")
                return False, "Connection closed"
            except Exception as e:
                logger.error(f"Error receiving message: {e}")
                return False, str(e)
    
    def get_history(self, prompt_id: str) -> Optional[Dict[str, Any]]:
        """Get execution history for a prompt"""
        try:
            url = f"http://{self.server_address}/history/{prompt_id}"
            with urllib.request.urlopen(url) as response:
                history = json.loads(response.read())
                return history.get(prompt_id)
        except Exception as e:
            logger.error(f"Error getting history for {prompt_id}: {e}")
            return None

    def get_prompt_outputs(self, prompt_id: str) -> List[Dict[str, str]]:
        """Return list of output files for a completed prompt as URLs and metadata

        Each item: { filename, subfolder, type, url }
        """
        outputs: List[Dict[str, str]] = []
        history = self.get_history(prompt_id)
        if not history:
            return outputs

        try:
            items = history.get("outputs", {})
            for _node, data in items.items():
                images = data.get("images") or []
                for img in images:
                    filename = img.get("filename", "")
                    subfolder = img.get("subfolder", "")
                    ftype = img.get("type", "output")
                    # Build a direct view URL
                    q_fn = urllib.parse.quote(filename)
                    q_sf = urllib.parse.quote(subfolder)
                    q_tp = urllib.parse.quote(ftype)
                    url = f"http://{self.server_address}/view?filename={q_fn}&subfolder={q_sf}&type={q_tp}"
                    outputs.append({
                        "filename": filename,
                        "subfolder": subfolder,
                        "type": ftype,
                        "url": url,
                    })
        except Exception as e:
            logger.error(f"Error parsing outputs for {prompt_id}: {e}")
        return outputs
    
    def interrupt_execution(self):
        """Interrupt current execution"""
        try:
            req = urllib.request.Request(
                f"http://{self.server_address}/interrupt",
                data=b'',
                method='POST'
            )
            urllib.request.urlopen(req)
            logger.info("Interrupted execution")
        except Exception as e:
            logger.error(f"Error interrupting execution: {e}")
    
    def get_queue_status(self) -> Optional[Dict[str, Any]]:
        """Get current queue status"""
        try:
            url = f"http://{self.server_address}/queue"
            with urllib.request.urlopen(url) as response:
                return json.loads(response.read())
        except Exception as e:
            logger.error(f"Error getting queue status: {e}")
            return None
    
    def clear_queue(self):
        """Clear the execution queue"""
        try:
            payload = {"clear": True}
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                f"http://{self.server_address}/queue",
                data=data,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            urllib.request.urlopen(req)
            logger.info("Cleared execution queue")
        except Exception as e:
            logger.error(f"Error clearing queue: {e}")
    
    def execute_with_retry(self, workflow: Dict[str, Any], max_retries: int = MAX_RETRIES) -> Tuple[bool, Optional[str], Optional[str]]:
        """Execute workflow with retry logic"""
        for attempt in range(max_retries):
            prompt_id = self.queue_prompt(workflow)
            if not prompt_id:
                logger.warning(f"Failed to queue prompt, attempt {attempt + 1}/{max_retries}")
                time.sleep(RETRY_DELAY)
                continue
            
            success, error = self.wait_for_prompt_completion(prompt_id)
            if success:
                return True, prompt_id, None
            
            logger.warning(f"Execution failed (attempt {attempt + 1}/{max_retries}): {error}")
            if attempt < max_retries - 1:
                time.sleep(RETRY_DELAY)
        
        return False, None, f"Failed after {max_retries} attempts"