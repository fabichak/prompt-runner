"""
Multi-Instance ComfyUI Client
Manages connections to multiple ComfyUI instances with different ports
"""
import logging
import time
import threading
from typing import Dict, Optional, Tuple, List
from concurrent.futures import ThreadPoolExecutor, Future

from services.comfyui_client import ComfyUIClient
from models.dual_instance import ComfyUIInstanceConfig, InstanceStatus
from config import MAX_RETRIES, RETRY_DELAY

logger = logging.getLogger(__name__)


class MultiInstanceComfyUIClient:
    """
    Manages multiple ComfyUI client instances for parallel execution
    
    Features:
    - Connection management for multiple instances
    - Health monitoring and automatic reconnection
    - Thread-safe job execution across instances
    - Automatic failover and error recovery
    """
    
    def __init__(self, instance_configs: List[ComfyUIInstanceConfig]):
        self.configs = {cfg.instance_id: cfg for cfg in instance_configs}
        self.clients: Dict[str, ComfyUIClient] = {}
        self.connection_locks: Dict[str, threading.Lock] = {}
        self.health_status: Dict[str, bool] = {}
        
        # Initialize clients and locks
        for instance_id, config in self.configs.items():
            self.clients[instance_id] = ComfyUIClient(config.address)
            self.connection_locks[instance_id] = threading.Lock()
            self.health_status[instance_id] = False
            
        logger.info(f"MultiInstanceComfyUIClient initialized with {len(instance_configs)} instances")
    
    def connect_all(self) -> Dict[str, bool]:
        """
        Connect to all configured instances
        
        Returns:
            Dictionary mapping instance_id to connection success status
        """
        results = {}
        
        for instance_id, config in self.configs.items():
            if not config.enabled:
                logger.info(f"Skipping disabled instance {instance_id}")
                results[instance_id] = False
                continue
                
            success = self._connect_instance(instance_id)
            results[instance_id] = success
            
            if success:
                config.status = InstanceStatus.IDLE
                self.health_status[instance_id] = True
                logger.info(f"✅ Connected to instance {instance_id} at {config.address}")
            else:
                config.status = InstanceStatus.ERROR
                self.health_status[instance_id] = False
                logger.error(f"❌ Failed to connect to instance {instance_id} at {config.address}")
        
        connected_count = sum(results.values())
        logger.info(f"Connected to {connected_count}/{len(self.configs)} instances")
        
        return results
    
    def disconnect_all(self):
        """Disconnect from all instances"""
        for instance_id in self.configs.keys():
            self._disconnect_instance(instance_id)
        logger.info("Disconnected from all instances")
    
    def execute_job(self, instance_id: str, workflow: dict, max_retries: int = MAX_RETRIES) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Execute a job on a specific instance
        
        Args:
            instance_id: ID of the instance to execute on
            workflow: ComfyUI workflow to execute
            max_retries: Maximum number of retry attempts
            
        Returns:
            Tuple of (success, prompt_id, error_message)
        """
        if instance_id not in self.configs:
            error_msg = f"Unknown instance ID: {instance_id}"
            logger.error(error_msg)
            return False, None, error_msg
        
        config = self.configs[instance_id]
        if not config.enabled:
            error_msg = f"Instance {instance_id} is disabled"
            logger.error(error_msg)
            return False, None, error_msg
        
        # Ensure connection is established
        if not self.health_status.get(instance_id, False):
            logger.warning(f"Instance {instance_id} not connected, attempting to reconnect...")
            if not self._connect_instance(instance_id):
                error_msg = f"Failed to connect to instance {instance_id}"
                logger.error(error_msg)
                return False, None, error_msg
        
        # Execute with retry logic
        client = self.clients[instance_id]
        
        with self.connection_locks[instance_id]:
            config.status = InstanceStatus.BUSY
            
            try:
                success, prompt_id, error = client.execute_with_retry(workflow, max_retries)
                
                if success:
                    logger.info(f"✅ Job executed successfully on instance {instance_id}, prompt_id: {prompt_id}")
                else:
                    logger.error(f"❌ Job failed on instance {instance_id}: {error}")
                    # Mark instance as potentially unhealthy
                    if "connection" in str(error).lower() or "timeout" in str(error).lower():
                        self.health_status[instance_id] = False
                        config.status = InstanceStatus.ERROR
                
                return success, prompt_id, error
                
            except Exception as e:
                error_msg = f"Exception during job execution on instance {instance_id}: {e}"
                logger.error(error_msg)
                self.health_status[instance_id] = False
                config.status = InstanceStatus.ERROR
                return False, None, error_msg
                
            finally:
                if config.status == InstanceStatus.BUSY:
                    config.status = InstanceStatus.IDLE
    
    def get_available_instances(self, job_type: str = None) -> List[str]:
        """
        Get list of available instance IDs
        
        Args:
            job_type: Optional job type to filter by ("HIGH" or "LOW")
            
        Returns:
            List of available instance IDs
        """
        available = []
        
        for instance_id, config in self.configs.items():
            if (config.enabled and 
                config.status == InstanceStatus.IDLE and
                self.health_status.get(instance_id, False)):
                
                # Filter by job type if specified
                if job_type is None or job_type in config.job_types:
                    available.append(instance_id)
        
        return available
    
    def get_instance_for_job_type(self, job_type: str) -> Optional[str]:
        """
        Get the best available instance for a specific job type
        
        Args:
            job_type: "HIGH" or "LOW"
            
        Returns:
            Instance ID or None if no suitable instance available
        """
        available = self.get_available_instances(job_type)
        
        if not available:
            return None
        
        # For now, return the first available instance
        # Could be enhanced with load balancing logic
        return available[0]
    
    def health_check_all(self) -> Dict[str, bool]:
        """
        Perform health check on all instances
        
        Returns:
            Dictionary mapping instance_id to health status
        """
        results = {}
        
        for instance_id, config in self.configs.items():
            if not config.enabled:
                results[instance_id] = False
                continue
                
            client = self.clients[instance_id]
            
            try:
                # Simple health check - get queue status
                queue_status = client.get_queue_status()
                is_healthy = queue_status is not None
                
                self.health_status[instance_id] = is_healthy
                results[instance_id] = is_healthy
                
                if is_healthy:
                    if config.status == InstanceStatus.ERROR:
                        config.status = InstanceStatus.IDLE
                        logger.info(f"Instance {instance_id} recovered")
                else:
                    config.status = InstanceStatus.ERROR
                    logger.warning(f"Instance {instance_id} health check failed")
                    
            except Exception as e:
                logger.warning(f"Health check failed for instance {instance_id}: {e}")
                self.health_status[instance_id] = False
                results[instance_id] = False
                config.status = InstanceStatus.ERROR
        
        return results
    
    def get_status_summary(self) -> Dict[str, dict]:
        """
        Get comprehensive status summary for all instances
        
        Returns:
            Dictionary with status information for each instance
        """
        summary = {}
        
        for instance_id, config in self.configs.items():
            client = self.clients[instance_id]
            
            try:
                queue_status = client.get_queue_status() if self.health_status.get(instance_id, False) else None
            except:
                queue_status = None
            
            summary[instance_id] = {
                "config": config.to_dict(),
                "healthy": self.health_status.get(instance_id, False),
                "queue_status": queue_status,
                "can_handle_high": config.can_handle_job_type("HIGH"),
                "can_handle_low": config.can_handle_job_type("LOW")
            }
        
        return summary
    
    def interrupt_all(self):
        """Interrupt execution on all instances"""
        for instance_id, config in self.configs.items():
            if config.enabled and self.health_status.get(instance_id, False):
                try:
                    client = self.clients[instance_id]
                    client.interrupt_execution()
                    logger.info(f"Interrupted execution on instance {instance_id}")
                except Exception as e:
                    logger.error(f"Failed to interrupt instance {instance_id}: {e}")
    
    def clear_queues_all(self):
        """Clear execution queues on all instances"""
        for instance_id, config in self.configs.items():
            if config.enabled and self.health_status.get(instance_id, False):
                try:
                    client = self.clients[instance_id]
                    client.clear_queue()
                    logger.info(f"Cleared queue on instance {instance_id}")
                except Exception as e:
                    logger.error(f"Failed to clear queue on instance {instance_id}: {e}")
    
    def _connect_instance(self, instance_id: str) -> bool:
        """Connect to a specific instance"""
        config = self.configs[instance_id]
        client = self.clients[instance_id]
        
        config.status = InstanceStatus.CONNECTING
        
        try:
            success = client.connect()
            if success:
                self.health_status[instance_id] = True
                config.status = InstanceStatus.IDLE
                return True
            else:
                self.health_status[instance_id] = False
                config.status = InstanceStatus.ERROR
                return False
                
        except Exception as e:
            logger.error(f"Exception connecting to instance {instance_id}: {e}")
            self.health_status[instance_id] = False
            config.status = InstanceStatus.ERROR
            return False
    
    def _disconnect_instance(self, instance_id: str):
        """Disconnect from a specific instance"""
        client = self.clients[instance_id]
        config = self.configs[instance_id]
        
        try:
            client.disconnect()
            self.health_status[instance_id] = False
            config.status = InstanceStatus.DISCONNECTED
            logger.debug(f"Disconnected from instance {instance_id}")
        except Exception as e:
            logger.error(f"Error disconnecting from instance {instance_id}: {e}")
    
    def reconnect_failed_instances(self) -> Dict[str, bool]:
        """
        Attempt to reconnect to failed instances
        
        Returns:
            Dictionary mapping instance_id to reconnection success
        """
        results = {}
        
        for instance_id, config in self.configs.items():
            if (config.enabled and 
                config.status == InstanceStatus.ERROR and 
                not self.health_status.get(instance_id, False)):
                
                logger.info(f"Attempting to reconnect to failed instance {instance_id}")
                success = self._connect_instance(instance_id)
                results[instance_id] = success
                
                if success:
                    logger.info(f"✅ Successfully reconnected to instance {instance_id}")
                else:
                    logger.warning(f"❌ Failed to reconnect to instance {instance_id}")
        
        return results