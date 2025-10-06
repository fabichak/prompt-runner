"""VastAI instance management utilities"""
import os
import subprocess
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class VastManager:
    """Handles VastAI instance lifecycle"""
    
    @staticmethod
    def get_pod_id() -> Optional[str]:
        """Get the current VastAI instance ID (kept name for API symmetry)"""
        try:
            pod_id = os.environ.get('VAST_INSTANCE_ID')
            if pod_id:
                logger.info(f"VastAI Instance ID: {pod_id}")
                return pod_id
            else:
                logger.warning("VAST_INSTANCE_ID environment variable not found")
                return None
        except Exception as e:
            logger.error(f"Error getting VastAI instance ID: {e}")
            return None
    
    @staticmethod
    def shutdown_instance(force: bool = False) -> bool:
        """Shutdown the VastAI instance"""
        try:
            pod_id = VastManager.get_pod_id()
            if not pod_id:
                logger.warning("Cannot shutdown - no pod ID found")
                return False
            
            if not force:
                logger.info("Shutdown requested but not forced, skipping...")
                return False
            
            logger.info(f"Shutting down VastAI instance {pod_id}")
            
            # Use vastai CLI to stop the instance
            # Note: this assumes `vastai` is installed and authenticated.
            cmd = ["vastai", "stop", "instance", pod_id]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("VastAI instance shutdown initiated")
                return True
            else:
                logger.error(f"Failed to shutdown: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error shutting down VastAI instance: {e}")
            return False
    
    @staticmethod
    def shutdown_current_pod() -> bool:
        """Convenience method to shutdown the current VastAI instance (name kept for API symmetry)"""
        return VastManager.shutdown_instance(force=True)
    
    @staticmethod
    def check_instance_health() -> bool:
        """Check if the VastAI instance is healthy"""
        try:
            # Check if we're running on VastAI
            if not os.environ.get('VAST_INSTANCE_ID'):
                logger.info("Not running on VastAI")
                return True  # Consider healthy if not on RunPod (local dev)
            
            # Check basic system resources
            import psutil
            
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            logger.info(f"System health - CPU: {cpu_percent}%, RAM: {memory.percent}%, Disk: {disk.percent}%")
            
            # Check if any critical thresholds are exceeded
            if cpu_percent > 95:
                logger.warning(f"High CPU usage: {cpu_percent}%")
                return False
            if memory.percent > 95:
                logger.warning(f"High memory usage: {memory.percent}%")
                return False
            if disk.percent > 95:
                logger.warning(f"High disk usage: {disk.percent}%")
                return False
            
            return True
            
        except ImportError:
            logger.warning("psutil not available for health check")
            return True
        except Exception as e:
            logger.error(f"Error checking VastAI instance health: {e}")
            return True
    
    @staticmethod
    def get_instance_info() -> Dict[str, Any]:
        """Get information about the VastAI instance"""
        info = {
            'instance_id': os.environ.get('VAST_INSTANCE_ID', 'N/A'),
            'hostname': os.environ.get('VAST_HOSTNAME', os.environ.get('HOSTNAME', 'N/A')),
            'gpu_count': os.environ.get('VAST_GPU_COUNT', 'N/A'),
            'cpu_count': os.environ.get('VAST_CPU_COUNT', 'N/A'),
            'mem_gb': os.environ.get('VAST_MEM_GB', 'N/A'),
            'public_ip': os.environ.get('VAST_PUBLIC_IP', 'N/A'),
            'api_key': 'SET' if os.environ.get('VAST_API_KEY') else 'NOT SET'
        }
        
        logger.info(f"VastAI instance info: {info}")
        return info